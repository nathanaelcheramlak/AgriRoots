"""Actual APIs, durable LangGraph, office boundaries and two HTTP provider fixtures."""
# ruff: noqa: F401,F811 -- pytest imports fixtures by name
import asyncio
from uuid import uuid4

from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.integrations.jobs import process_job
from src.skills.service import SkillService
from src.tools.policy import principal_for
from tests.home_fixture import HomeModelFixture, prepare_home
from tests.test_connectors_rest import rest_fixture
from tests.test_workspace import office


def test_home_context_is_authenticated_office_scoped_and_has_no_secrets(client, office, monkeypatch):
    assert client.get("/api/v1/companion/context").status_code == 401
    assert client.get("/api/v1/companion/context", headers=office["users"]["outsider"]["headers"]).status_code == 403
    monkeypatch.setattr(get_settings(), "gemini_api_key", "fixture-secret-that-must-not-leak")
    monkeypatch.setattr(get_settings(), "live_model_tests_enabled", False)
    r = client.get("/api/v1/companion/context?office_id=untrusted-office", headers=office["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["office_id"] == office["id"] and data["plots"][0]["id"] == office["plot"]["id"]
    assert data["plots"][0]["synthetic"] and data["plots"][0]["crop"] is None
    assert not data["model"]["execution_enabled"] and not data["model"]["reachability_verified"]
    assert "fixture-secret-that-must-not-leak" not in r.text
    assert "phone_number" not in r.text and "household_id" not in r.text


def test_home_resolves_enabled_version_even_when_new_draft_exists(client, office, rest_fixture, monkeypatch):
    origin, _ = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    with SessionLocal() as db:
        ss = SkillService(db, principal_for(db, office["users"]["admin"]["id"]))
        row, version = ss.version(skill["id"])
        manifest = {**version.manifest, "description": "An unapproved draft"}
        ss.create_skill(manifest, expected_revision=row.revision)
    data = client.get("/api/v1/companion/context", headers=office["headers"]).json()
    current = next(k for k in data["skills"] if k["id"] == skill["id"])
    assert current["available"] and current["version"] == 1 and current["description"] != "An unapproved draft"
    assert len(current["tools"]) == 2 and all(t["input_schema"]["properties"] == {} for t in current["tools"])


def test_home_question_runs_two_providers_and_retrieves_real_persisted_evidence(client, office, rest_fixture, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    origin, calls = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    payload = {"task": "Investigate this farm's forecast and soil. Explain the evidence and limitations.", "plot_ids": [office["plot"]["id"]], "parameters": {}, "request_key": uuid4().hex, "authorize_network": True, "authorize_model": True}
    r = client.post(f"/api/v1/skills/{skill['id']}/runs", headers=office["headers"], json=payload)
    assert r.status_code == 202, r.text
    queued = r.json()
    same = client.post(f"/api/v1/skills/{skill['id']}/runs", headers=office["headers"], json=payload)
    assert same.json()["id"] == queued["id"]
    assert asyncio.run(process_job(queued["id"], model=HomeModelFixture()))
    r = client.get(queued["status_url"] + "?include_progress=true", headers=office["headers"])
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "succeeded" and len(job["progress"]["calls"]) == 2
    assert len(job["result"]["evidence_ids"]) == 2
    for ident in job["result"]["evidence_ids"]:
        evidence = client.get("/api/v1/evidence/" + ident, headers=office["headers"])
        assert evidence.status_code == 200
        assert evidence.json()["data"]["classification"] == "fixture"
        assert ident in job["result"]["answer"]
        assert client.get("/api/v1/evidence/" + ident, headers=office["users"]["outsider"]["headers"]).status_code == 403
    assert client.get(queued["status_url"], headers=office["users"]["outsider"]["headers"]).status_code == 403
    assert len(calls) == 4  # two exact-version checks plus two runtime operations
    assert asyncio.run(process_job(queued["id"], model=HomeModelFixture())) is False


def test_home_foreign_plot_rejected_and_cancel_is_a_backend_operation(client, office, rest_fixture, monkeypatch):
    origin, _ = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    payload = {"task": "Inspect forecast and soil", "plot_ids": [str(uuid4())], "request_key": uuid4().hex, "authorize_model": True, "authorize_network": True}
    prefix = f"/api/v1/skills/{skill['id']}/runs"
    assert client.post(prefix, headers=office["headers"], json=payload).status_code == 403
    payload["plot_ids"] = [office["plot"]["id"]]
    queued = client.post(prefix, headers=office["headers"], json=payload).json()
    r = client.post(f"/api/v1/runs/{queued['id']}/cancel", headers=office["headers"])
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert not asyncio.run(process_job(queued["id"], model=HomeModelFixture()))
