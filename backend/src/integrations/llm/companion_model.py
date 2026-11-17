"""Application-controlled Gemini function calling; no automatic Python execution."""

import base64
import json
from typing import Protocol
from google import genai
from google.genai import types
from pydantic import Field

from src.config.settings import get_settings
from src.integrations.contracts import Strict, ConnectorError


def encode(value):
    if isinstance(value, bytes):
        return {"__agrilo_bytes__": base64.b64encode(value).decode()}
    if isinstance(value, dict):
        return {key: encode(val) for key, val in value.items()}
    if isinstance(value, list):
        return [encode(val) for val in value]
    return value


def decode(value):
    if isinstance(value, dict) and set(value) == {"__agrilo_bytes__"}:
        return base64.b64decode(value["__agrilo_bytes__"], validate=True)
    if isinstance(value, dict):
        return {key: decode(val) for key, val in value.items()}
    if isinstance(value, list):
        return [decode(val) for val in value]
    return value


def function_response(name, result, call_id=None):
    def minimized(value):
        if isinstance(value, dict):
            withheld = {
                "latitude",
                "longitude",
                "lat",
                "lon",
                "coordinates",
                "source_coordinates",
                "requested_coordinates",
                "geometry",
                "polygon",
                "phone",
                "phone_number",
                "email",
                "full_name",
                "household_id",
                "farmer_user_id",
                "image_sha256",
                "image_asset_id",
            }
            return {key: minimized(item) for key, item in value.items() if key.lower() not in withheld}
        if isinstance(value, list):
            return [minimized(item) for item in value]
        if isinstance(value, str) and value.startswith(("https://", "http://")):
            from urllib.parse import urlsplit, urlunsplit

            parsed = urlsplit(value)
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        return value

    result = minimized(result)
    return encode(
        types.Content(
            role="user",
            parts=[types.Part(function_response=types.FunctionResponse(name=name, id=call_id, response=result))],
        ).model_dump(mode="python", exclude_none=True)
    )


class CompanionModel(Protocol):
    async def generate(self, contents, tools, system) -> dict: ...
    def configuration(self) -> dict: ...


class GeminiCompanionModel:
    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ConnectorError("AUTH_REQUIRED", "Configure GEMINI_API_KEY in the backend's ignored environment")
        if not settings.gemini_model or "gemini_model" not in settings.model_fields_set:
            raise ConnectorError(
                "AUTH_REQUIRED", "Set an explicit verified GEMINI_MODEL; this companion does not guess a model ID"
            )
        self.model = settings.gemini_model
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=settings.gemini_timeout_seconds * 1000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

    async def generate(self, contents, tools, system):
        if not get_settings().live_model_tests_enabled:
            raise ConnectorError(
                "POLICY_DENIED", "Enable LIVE_MODEL_TESTS_ENABLED before authorizing a real Gemini request"
            )
        if len(json.dumps(contents).encode()) + len(json.dumps(tools).encode()) > 65536:
            raise ConnectorError("BUDGET_EXCEEDED", "Gemini context exceeds the 64 KiB application limit")
        declarations = [
            types.FunctionDeclaration(
                name=tool["alias"], description=tool["description"], parameters_json_schema=tool["input_schema"]
            )
            for tool in tools
        ]
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[types.Content.model_validate(decode(content)) for content in contents],
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    tools=[types.Tool(function_declarations=declarations)] if declarations else None,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    temperature=0.1,
                    max_output_tokens=1400,
                ),
            )
        except Exception as error:
            code = getattr(error, "code", None)
            if code in (401, 403):
                raise ConnectorError("AUTH_INVALID", "Gemini rejected the configured key or model access") from None
            if code == 429:
                raise ConnectorError("RATE_LIMITED", "Gemini quota reached", retryable=True) from None
            if code == 400:
                raise ConnectorError(
                    "UNSUPPORTED_SCHEMA", "Gemini rejected a declaration/configuration; constraints were not removed"
                ) from None
            raise ConnectorError(
                "UPSTREAM_ERROR", "Gemini request failed; no automatic retry or model fallback"
            ) from None
        if not response.candidates or not response.candidates[0].content:
            raise ConnectorError("INVALID_MODEL_OUTPUT", "Gemini returned no usable candidate")
        content = response.candidates[0].content
        # Keep the original function-call parts and opaque signatures. Do not rebuild
        # them from text or drop call IDs. Hidden thought text is never a user result.
        calls = [
            {"name": part.function_call.name, "arguments": part.function_call.args or {}, "id": part.function_call.id}
            for part in content.parts or []
            if part.function_call
        ]
        text = "".join(part.text for part in content.parts or [] if part.text and not part.thought)
        safe_parts = [part for part in content.parts or [] if not part.thought or part.function_call]
        stored = types.Content(role=content.role, parts=safe_parts)
        usage = response.usage_metadata
        return {
            "content": encode(stored.model_dump(mode="python", exclude_none=True)),
            "calls": calls,
            "text": text,
            "usage": {
                "input_tokens": usage.prompt_token_count,
                "output_tokens": usage.candidates_token_count,
                "total_tokens": usage.total_token_count,
            }
            if usage
            else {},
        }

    def configuration(self):
        return {
            "provider": "gemini",
            "model": self.model,
            "sdk": "google-genai==1.74.0",
            "automatic_function_execution": False,
            "max_output_tokens": 1400,
            "cloud_fallback": False,
        }

    async def aclose(self):
        await self.client.aio.aclose()
        self.client.close()


class ProposedCall(Strict):
    name: str = Field(max_length=64)
    arguments: dict


class LocalTurn(Strict):
    calls: list[ProposedCall] = Field(default_factory=list, max_length=4)
    text: str = Field(default="", max_length=8000)


class LocalCompanionModel:
    def __init__(self):
        from src.integrations.llm.local_adapter import LocalModel

        self.model = LocalModel()

    async def generate(self, contents, tools, system):
        output, usage = await self.model.complete(
            system,
            {
                "conversation": contents,
                "approved_tools": tools,
                "instruction": "Return calls using only listed aliases, or text explaining the cited tool evidence.",
            },
            LocalTurn,
        )
        calls = [{**call.model_dump(), "id": None} for call in output.calls]
        return {
            "content": {"role": "model", "parts": [{"text": output.model_dump_json()}]},
            "calls": calls,
            "text": output.text,
            "usage": usage,
        }

    def configuration(self):
        return self.model.configuration()


def model_provider():
    return GeminiCompanionModel() if get_settings().llm_provider == "gemini" else LocalCompanionModel()
