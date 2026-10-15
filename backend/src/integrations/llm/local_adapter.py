"""Local-only schema-constrained model interface; never falls back to Gemini."""
import ipaddress
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
import httpx
from pydantic import BaseModel
from src.config.settings import get_settings


class StructuredModel(Protocol):
    async def complete(self, system: str, data: dict, schema: type[BaseModel]) -> tuple[BaseModel, dict]: ...


class LocalModel:
    def __init__(self):
        self.settings = get_settings()
        url = urlsplit(self.settings.advisory_model_url)
        if (url.scheme != "http" or url.username or url.password or url.query or url.fragment
                or url.path not in ("", "/") or not url.hostname):
            raise ValueError("Local model endpoint must be an HTTP loopback origin")
        try:
            if not ipaddress.ip_address(url.hostname).is_loopback:
                raise ValueError("Cloud model endpoints are forbidden for advisory runs")
        except ValueError:
            raise ValueError("Model host must be a literal loopback address") from None
        self.url = self.settings.advisory_model_url.rstrip("/")

    async def complete(self, system, data, schema):
        encoded = json.dumps(data, ensure_ascii=False)
        output_schema = schema.model_json_schema()
        if schema.__name__ == "Candidates":
            # Constrain identifiers to the actual run context during decoding,
            # then independently validate their relationships before saving.
            properties = output_schema["$defs"]["Candidate"]["properties"]
            properties["plot_id"]["enum"] = [p["id"] for p in data["plots"]]
            properties["crop"]["enum"] = sorted({p["season"]["crop"] for p in data["plots"]})
            properties["proposed_date"]["enum"] = [data["today"]]
            properties["evidence_ids"]["prefixItems"] = [
                {"type": "string", "enum": [e["id"] for e in data["evidence"] if e["kind"] == kind]}
                for kind in ("history", "weather", "guidance", "calendar", "public_document")]
            properties["evidence_ids"]["items"] = {"type": "string"}
            if data.get("eligible_actions"):
                properties["action_code"]["enum"] = data["eligible_actions"]
            output_schema["properties"]["recommendations"].update(minItems=1, maxItems=1)
        if len(encoded) > 24000:
            raise ValueError("Model context exceeds the configured limit; select a smaller cluster")
        key = Path(self.settings.advisory_model_key_file).read_text().strip()
        if not key:
            raise ValueError("Configure the local model API key file")
        async with httpx.AsyncClient(timeout=self.settings.advisory_model_timeout, trust_env=False,
                                     headers={"Authorization": "Bearer " + key},
                                     follow_redirects=False) as client:
            models = await client.get(self.url + "/v1/models"); models.raise_for_status()
            if self.settings.advisory_model_id not in {m["id"] for m in models.json()["data"]}:
                raise ValueError("Served model identity does not match the configured pinned model")
            response = await client.post(self.url + "/v1/chat/completions", json={
                "model": self.settings.advisory_model_id,
                "messages": [{"role": "system", "content": system + " /no_think"},
                             {"role": "user", "content": encoded}],
                "response_format": {"type": "json_schema", "json_schema": {"name": schema.__name__,
                    "strict": True, "schema": output_schema}},
                "temperature": 0, "seed": 42, "max_tokens": 1400,
                "chat_template_kwargs": {"enable_thinking": False},
            })
            response.raise_for_status()
            result = response.json()
            if result["choices"][0].get("finish_reason") == "length":
                raise ValueError("Model output exceeded the token limit")
            return schema.model_validate_json(result["choices"][0]["message"]["content"]), result.get("usage", {})

    def configuration(self):
        return {"provider": "local-llama.cpp", "model": self.settings.advisory_model_id,
                "revision": self.settings.advisory_model_revision, "temperature": 0, "seed": 42,
                "compute_cost_per_hour_usd": self.settings.advisory_compute_cost_per_hour,
                "cost_status": "estimated" if self.settings.advisory_compute_cost_per_hour else "unpriced",
                "max_tokens": 1400, "context_characters": 24000, "cloud_fallback": False}
