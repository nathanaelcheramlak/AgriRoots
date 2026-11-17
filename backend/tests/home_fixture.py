"""Reusable explicitly labelled Home test setup; never imported by production code."""
import json

from google.genai import types

from src.integrations.llm.companion_model import encode


class HomeModelFixture:
    def configuration(self):
        return {"provider": "explicit-home-model-fixture", "model": "fixture-only-no-cloud-request", "model_request_executed": False}

    async def generate(self, contents, tools, system):
        responses = [p["function_response"]["response"] for content in contents for p in content.get("parts", []) if "function_response" in p]
        if not responses:
            # Explicit fixture proposal copies only public schema fields from the
            # actual task context. This is not a claim of real-model reasoning.
            task = json.loads(contents[0]["parts"][0]["text"])
            parameters = task.get("parameters", {})
            calls = [{"name": tool["alias"], "arguments": {k: v for k, v in parameters.items() if k in tool["input_schema"].get("properties", {})}, "id": "fixture-" + str(i)} for i, tool in enumerate(tools)]
            content = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=c["name"], args=c["arguments"], id=c["id"])) for c in calls])
            return {"calls": calls, "content": encode(content.model_dump(mode="python", exclude_none=True)), "text": "", "usage": {}}
        ids = [ident for response in responses for ident in response.get("evidence_ids", [])]
        incomplete = any(response.get("execution_outcome") != "SUCCESS" for response in responses)
        text = ("Fixture investigation: provider evidence is incomplete. Inspect the recorded provider error; no successful soil result is assumed. Evidence: " if incomplete else "Fixture investigation: inspect the recorded forecast and mapped soil evidence, units and dates. These fixtures do not establish field conditions. Evidence: ") + ", ".join(ids)
        return {"calls": [], "content": {"role": "model", "parts": [{"text": text}]}, "text": text, "usage": {}}


def prepare_home(client, office, origin, monkeypatch):
    from uuid import uuid4

    from src.providers.factory import HANDLERS, template
    from tests.test_connectors_rest import connection, register, soil_spec, test_and_publish

    soil_connection = connection(client, office, origin)
    spec = soil_spec()
    spec["context_bindings"] = {"latitude": "plot.latitude", "longitude": "plot.longitude"}
    soil = register(client, office, soil_connection, spec)
    assert test_and_publish(client, office, soil_connection, soil, {})["status"] == "succeeded"
    monkeypatch.setitem(HANDLERS, "open_meteo.forecast", {**HANDLERS["open_meteo.forecast"], "base_url": origin})
    provider = template("open_meteo.forecast")
    headers = office["users"]["admin"]["headers"]
    r = client.post("/api/v1/integrations", headers=headers, json=provider["connection"])
    assert r.status_code == 201, r.text
    weather_connection = r.json()
    weather = register(client, office, weather_connection, provider["operations"][0])
    assert test_and_publish(client, office, weather_connection, weather, {})["status"] == "succeeded"
    manifest = {"name": "home_fixture_combined", "description": "Explicit fixture weather and mapped-soil investigation", "instructions": "Use both required tools and cite their actual evidence IDs. All data and model outputs here are fixtures, not live field observations.", "required_capabilities": ["weather.forecast", "soil.profile"], "optional_capabilities": []}
    r = client.post("/api/v1/skills", headers=headers, json=manifest)
    assert r.status_code == 201, r.text
    skill = r.json()
    exact = {"version": skill["version"], "digest": skill["digest"], "request_key": uuid4().hex}
    r = client.post(f"/api/v1/skills/{skill['id']}/test", headers=headers, json=exact)
    assert r.status_code == 202, r.text
    r = client.post(f"/api/v1/skills/{skill['id']}/approve", headers=headers, json=exact)
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/v1/skills/{skill['id']}/enabled", headers=headers, json={"enabled": True, "version": skill["version"], "expected_revision": r.json()["revision"]})
    assert r.status_code == 200, r.text
    return r.json()
