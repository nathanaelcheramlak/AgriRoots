"""Explicit model fixtures plus actual application APIs, persistent checkpoints and local HTTP."""

import asyncio
from copy import deepcopy
import json
from uuid import uuid4

from google.genai import types
import pytest
from sqlalchemy import select, func, text

from tests.test_workspace import office
from tests.test_connectors_rest import rest_fixture, connection, register, soil_spec, test_and_publish
from src.integrations.jobs import process_job
from src.integrations.llm.companion_model import encode, decode, function_response, GeminiCompanionModel
from src.db.session import SessionLocal
from src.db.models.connectors import Integration, RegisteredSkill, ConnectorJob, ToolInvocation
from src.db.models.workspace import WorkspaceRecord
from src.config.settings import get_settings


def published_skill(client, o, capability="soil.profile", optional=None):
    headers = o["users"]["admin"]["headers"]
    r = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "name": "soil_explanation",
            "description": "Explain fixture evidence",
            "instructions": "Explain mapped soil values, units and missing metadata with actual evidence IDs.",
            "required_capabilities": [capability],
            "optional_capabilities": optional or [],
        },
    )
    assert r.status_code == 201, r.text
    skill = r.json()
    exact = {"version": skill["version"], "digest": skill["digest"], "request_key": uuid4().hex}
    r = client.post(f"/api/v1/skills/{skill['id']}/test", headers=headers, json=exact)
    assert r.status_code == 202 and r.json()["status"] == "succeeded", r.text
    assert r.json()["result"]["model_request_executed"] is False
    r = client.post(f"/api/v1/skills/{skill['id']}/approve", headers=headers, json=exact)
    assert r.status_code == 200, r.text
    r = client.patch(
        f"/api/v1/skills/{skill['id']}/enabled",
        headers=headers,
        json={"version": skill["version"], "expected_revision": r.json()["revision"], "enabled": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


def queue(client, o, skill):
    r = client.post(
        f"/api/v1/skills/{skill['id']}/runs",
        headers=o["headers"],
        json={
            "task": "Explain this synthetic soil profile",
            "plot_ids": [o["plot"]["id"]],
            "request_key": uuid4().hex,
            "authorize_network": True,
            "authorize_model": True,
        },
    )
    assert r.status_code == 202, r.text
    return r.json()


class ExplicitModelFixture:
    def __init__(self, *, malicious=False, unsupported_number=False):
        self.turn = 0
        self.seen = []
        self.malicious = malicious
        self.unsupported_number = unsupported_number

    def configuration(self):
        return {"provider": "explicit-test-fixture", "model_request_executed": False}

    async def generate(self, contents, tools, system):
        self.turn += 1
        self.seen.append(deepcopy(tools))
        assert "Never approve" in system
        if self.turn == 1:
            name = "approve_advisory" if self.malicious else tools[0]["alias"]
            call = {"name": name, "arguments": {}, "id": "fixture-call-1"}
            content = types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(name=name, args={}, id="fixture-call-1"),
                        thought_signature=b"opaque-signature",
                    )
                ],
            )
            return {
                "calls": [call],
                "text": "",
                "content": encode(content.model_dump(mode="python", exclude_none=True)),
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        responses = [
            decode(part)["function_response"]
            for content in contents
            for part in content.get("parts", [])
            if "function_response" in part
        ]
        assert responses[-1]["id"] == "fixture-call-1"
        ids = responses[-1]["response"].get("evidence_ids", [])
        text = f"Mapped pH is {'12.9' if self.unsupported_number else '6.8'}. Observation date is unavailable."
        if ids:
            text += " Evidence: " + ids[0]
        return {"calls": [], "text": text, "content": {"role": "model", "parts": [{"text": text}]}, "usage": {}}


def prepared(client, o, origin, *, optional=None):
    conn = connection(client, o, origin)
    spec = soil_spec()
    spec["context_bindings"] = {"latitude": "plot.latitude", "longitude": "plot.longitude"}
    tool = register(client, o, conn, spec)
    assert test_and_publish(client, o, conn, tool, {})["status"] == "succeeded"
    return conn, tool, published_skill(client, o, optional=optional)


def test_registry_driven_graph_uses_manual_calls_and_persistent_evidence(
    client, office, rest_fixture, monkeypatch, tmp_path
):
    origin, calls = rest_fixture
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    _, tool, skill = prepared(client, office, origin)
    job = queue(client, office, skill)
    model = ExplicitModelFixture()
    assert asyncio.run(process_job(job["id"], model=model))
    result = client.get(job["status_url"], headers=office["headers"]).json()
    assert result["status"] == "succeeded", json.dumps(result, indent=2)
    assert result["result"]["model"]["provider"] == "explicit-test-fixture"
    assert "6.8" in result["result"]["answer"] and len(result["result"]["evidence_ids"]) == 1
    assert model.seen[0][0]["version_id"] == tool["version_id"]
    assert model.seen[0][0]["input_schema"]["properties"] == {}
    with SessionLocal() as db:
        if db.bind.dialect.name == "postgresql":
            assert db.scalar(text("SELECT count(*) FROM checkpoints WHERE thread_id = :id"), {"id": job["id"]}) > 0
        else:
            assert (tmp_path / "checkpoints.sqlite").is_file()
    before = len(calls)
    assert asyncio.run(process_job(job["id"], model=model)) is False
    assert len(calls) == before


def test_new_approved_tool_appears_only_in_new_snapshots_without_restart(client, office, rest_fixture):
    origin, _ = rest_fixture
    conn, _, skill = prepared(client, office, origin, optional=["weather.forecast"])
    old_job = queue(client, office, skill)
    extra = soil_spec("weather_fixture")
    extra["capability_tags"] = ["weather.forecast"]
    second = register(client, office, conn, extra)
    assert test_and_publish(client, office, conn, second)["status"] == "succeeded"
    new_job = queue(client, office, skill)
    with SessionLocal() as db:
        old = db.get(ConnectorJob, old_job["id"])
        new = db.get(ConnectorJob, new_job["id"])
        assert len(old.snapshot["tools"]) == 1 and len(new.snapshot["tools"]) == 2
        assert old.snapshot["generation"] < new.snapshot["generation"]


def test_unknown_model_tool_is_audited_and_never_dispatched(client, office, rest_fixture, monkeypatch, tmp_path):
    origin, calls = rest_fixture
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    _, _, skill = prepared(client, office, origin)
    before = len(calls)
    job = queue(client, office, skill)
    asyncio.run(process_job(job["id"], model=ExplicitModelFixture(malicious=True)))
    result = client.get(job["status_url"], headers=office["headers"]).json()
    assert result["status"] == "partial", result
    assert "Insufficient" in result["result"]["answer"]
    assert len(calls) == before
    with SessionLocal() as db:
        rejected = list(db.scalars(select(ToolInvocation).where(ToolInvocation.job_id == job["id"])))
        assert len(rejected) == 1 and rejected[0].status == "POLICY_DENIED"


def test_unsupported_model_numbers_are_rejected(client, office, rest_fixture, monkeypatch, tmp_path):
    origin, _ = rest_fixture
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    _, _, skill = prepared(client, office, origin)
    job = queue(client, office, skill)
    asyncio.run(process_job(job["id"], model=ExplicitModelFixture(unsupported_number=True)))
    result = client.get(job["status_url"], headers=office["headers"]).json()
    assert result["status"] == "failed" and result["error"]["code"] == "OUTPUT_VALIDATION_FAILED"


def test_disabled_skill_and_missing_gemini_configuration_are_honest_blockers(client, office, rest_fixture, monkeypatch):
    origin, _ = rest_fixture
    _, _, skill = prepared(client, office, origin)
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    job = queue(client, office, skill)
    asyncio.run(process_job(job["id"]))
    blocked = client.get(job["status_url"], headers=office["headers"]).json()
    assert blocked["error"]["code"] == "AUTH_REQUIRED" and blocked["status"] == "failed"
    headers = office["users"]["admin"]["headers"]
    r = client.patch(
        f"/api/v1/skills/{skill['id']}/enabled",
        headers=headers,
        json={"enabled": False, "expected_revision": skill["revision"]},
    )
    assert r.status_code == 200
    r = client.post(
        f"/api/v1/skills/{skill['id']}/runs",
        headers=office["headers"],
        json={"task": "Explain the soil", "request_key": uuid4().hex},
    )
    assert r.status_code == 409


@pytest.mark.parametrize("behavior", ["success", "second_empty", "oversized"])
def test_model_repair_is_bounded_and_usage_is_retained(client, office, rest_fixture, monkeypatch, tmp_path, behavior):
    origin, calls = rest_fixture
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    _, _, skill = prepared(client, office, origin)

    class RepairFixture(ExplicitModelFixture):
        requests = 0

        async def generate(self, contents, tools, system):
            self.requests += 1
            if self.requests == 1 or behavior == "second_empty" and self.requests == 3:
                return {
                    "calls": [],
                    "text": "",
                    "content": {"role": "model", "parts": []},
                    "usage": {"input_tokens": 2},
                }
            output = await super().generate(contents, tools, system)
            if behavior == "oversized" and self.requests == 2:
                output["calls"] *= 5
            return output

    model = RepairFixture()
    job = queue(client, office, skill)
    before = len(calls)
    asyncio.run(process_job(job["id"], model=model))
    result = client.get(job["status_url"], headers=office["headers"]).json()
    if behavior == "success":
        assert result["status"] == "succeeded", result
        assert len(result["result"]["model_usage"]) == 3
        assert result["result"]["model_usage"][0]["input_tokens"] == 2
    elif behavior == "second_empty":
        assert result["error"]["code"] == "INVALID_MODEL_OUTPUT" and model.requests == 3
    else:
        assert result["error"]["code"] == "BUDGET_EXCEEDED" and len(calls) == before


def test_plugin_install_is_atomic_disabled_and_idempotent(client, office, rest_fixture):
    origin, calls = rest_fixture
    headers = office["users"]["admin"]["headers"]
    manifest = {
        "name": "fixture_pack",
        "version": 1,
        "description": "Explicit fixture configuration pack",
        "connections": [
            {
                "template_id": "soil",
                "configuration": {
                    "name": "Soil",
                    "adapter_type": "rest",
                    "base_url": origin,
                    "egress_data_classes": ["plot_coordinates"],
                },
                "tools": [soil_spec()],
            }
        ],
        "skills": [
            {
                "name": "soil",
                "description": "Explain fixture values",
                "instructions": "Preserve limitations.",
                "required_capabilities": ["soil.profile"],
            }
        ],
    }
    r = client.post("/api/v1/plugins", headers=headers, json=manifest)
    assert r.status_code == 201, r.text
    pack = r.json()
    r = client.post(f"/api/v1/plugins/{pack['id']}/install", headers=headers, json={"digest": pack["digest"]})
    assert r.status_code == 200, r.text
    installed = r.json()
    assert installed["installed"] and installed["resources"]["connections"] and not calls
    conn = client.get("/api/v1/integrations/" + installed["resources"]["connections"][0], headers=headers).json()
    assert not conn["enabled"]
    skill = client.get("/api/v1/skills/" + installed["resources"]["skills"][0], headers=headers).json()
    assert not skill["enabled"] and not skill["approved"]
    again = client.post(f"/api/v1/plugins/{pack['id']}/install", headers=headers, json={"digest": pack["digest"]})
    assert again.json()["resources"] == installed["resources"]
    r = client.patch(
        f"/api/v1/plugins/{pack['id']}/enabled", headers=headers, json={"digest": pack["digest"], "enabled": False}
    )
    assert r.status_code == 200 and not r.json()["enabled"]


def test_failed_pack_install_rolls_back_all_created_resources(client, office, rest_fixture):
    origin, _ = rest_fixture
    headers = office["users"]["admin"]["headers"]
    data = {
        "name": "invalid_pack",
        "version": 1,
        "description": "Atomic failure fixture",
        "connections": [
            {"template_id": "valid", "configuration": {"name": "Valid", "adapter_type": "rest", "base_url": origin}},
            {
                "template_id": "invalid",
                "configuration": {"name": "Invalid", "adapter_type": "rest", "base_url": "http://169.254.169.254"},
            },
        ],
    }
    pack = client.post("/api/v1/plugins", headers=headers, json=data).json()
    r = client.post(f"/api/v1/plugins/{pack['id']}/install", headers=headers, json={"digest": pack["digest"]})
    assert r.status_code == 403
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Integration)) == 0


def test_gemini_sdk_preserves_ids_signatures_and_manual_execution(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "explicit-fixture-key-not-a-live-key")
    monkeypatch.setattr(settings, "gemini_model", "test-model")
    monkeypatch.setattr(settings, "live_model_tests_enabled", True)
    model = GeminiCompanionModel()
    captured = {}

    async def generate(**kwargs):
        captured.update(kwargs)
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(name="tool_fixture", args={}, id="call-123"),
                                thought_signature=b"opaque",
                            )
                        ],
                    )
                )
            ]
        )

    monkeypatch.setattr(model.client.aio.models, "generate_content", generate)

    async def verify():
        result = await model.generate(
            [{"role": "user", "parts": [{"text": "Explicit model SDK fixture"}]}],
            [
                {
                    "alias": "tool_fixture",
                    "description": "fixture",
                    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                }
            ],
            "system",
        )
        assert result["calls"][0]["id"] == "call-123"
        assert decode(result["content"])["parts"][0]["thought_signature"] == b"opaque"
        assert captured["config"].automatic_function_calling.disable is True
        followup = function_response("tool_fixture", {"ok": True}, "call-123")
        assert decode(followup)["parts"][0]["function_response"]["id"] == "call-123"
        await model.aclose()

    asyncio.run(verify())
