"""Real authenticated jobs/registry/executor with labelled provider and model fixtures."""

# ruff: noqa: F401,F811 -- imported pytest fixtures
import asyncio
import json
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.integrations.jobs import process_job
from src.providers.factory import HANDLERS, template
from tests.home_fixture import HomeModelFixture
from tests.test_connectors_rest import exact, register
from tests.test_farm_registry import setup_registry
from tests.test_verified_integration import private_test_storage, upload
from tests.test_workspace import office


@pytest.fixture
def demo_http(monkeypatch):
    calls, periods = [], {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def dispatch(self):
            path = urlsplit(self.path).path
            calls.append(path)
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if path.endswith("identification"):
                payload = {
                    "result": {
                        "crop": {"suggestions": [{"name": "maize", "probability": 0.9}]},
                        "disease": {"suggestions": [{"name": "leaf blight", "probability": 0.7}]},
                    }
                }
            elif path.endswith("submitDataRequest/"):
                query = parse_qs(urlsplit(self.path).query)
                from datetime import datetime

                periods["start"] = datetime.strptime(query["begintime"][0], "%m/%d/%Y").date()
                periods["end"] = datetime.strptime(query["endtime"][0], "%m/%d/%Y").date()
                periods["geometry"] = json.loads(query["geometry"][0])
                payload = ["fixture-monthly-request-123456"]
            elif path.endswith("getDataRequestProgress/"):
                payload = [100]
            elif path.endswith("getDataFromRequest/"):
                payload = {
                    "data": [
                        {
                            "date": (periods["start"] + timedelta(days=i)).strftime("%m/%d/%Y"),
                            "value": {"avg": float(i % 5)},
                        }
                        for i in range((periods["end"] - periods["start"]).days + 1)
                    ]
                }
            else:
                self.send_error(404)
                return
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = dispatch
        do_POST = dispatch

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    origin = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_settings(), "connector_fixture_origins", [origin])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield origin, calls, periods
    server.shutdown()
    server.server_close()
    thread.join()


def setup_demo(client, office, demo_http, monkeypatch, kind):
    origin, _, _ = demo_http
    handler = "kindwise.diagnosis" if kind == "photo" else "chirps.rainfall_history"
    monkeypatch.setitem(HANDLERS, handler, {**HANDLERS[handler], "base_url": origin})
    h = office["users"]["admin"]["headers"]
    provider = template(handler)
    c = client.post("/api/v1/integrations", headers=h, json=provider["connection"]).json()
    if kind == "photo":
        r = client.put(
            f"/api/v1/integrations/{c['id']}/credential",
            headers=h,
            json={"value": "explicit-fixture-key", "principal_scope": "fixture"},
        )
        assert r.status_code == 200, r.text
    tool = register(client, office, c, provider["operations"][0])
    asset = upload(client, office) if kind == "photo" else None
    args = {"image_asset_id": asset} if asset else {"start": "2025-07-01", "end": "2025-07-31"}
    prefix = f"/api/v1/integrations/{c['id']}"
    r = client.post(
        prefix + f"/tools/{tool['id']}/test",
        headers=h,
        json={
            **exact(tool),
            "arguments": args,
            "plot_ids": [] if asset else [office["plot"]["id"]],
            "authorize_network": True,
            "authorize_credit_use": bool(asset),
            "request_key": uuid4().hex,
        },
    )
    assert r.status_code == 202, r.text
    asyncio.run(process_job(r.json()["id"]))
    job = client.get(r.json()["status_url"], headers=h).json()
    assert job["status"] == "succeeded", job
    r = client.post(prefix + f"/tools/{tool['id']}/approve", headers=h, json=exact(tool))
    assert r.status_code == 200, r.text
    r = client.patch(
        prefix + f"/tools/{tool['id']}/enabled",
        headers=h,
        json={"enabled": True, "expected_revision": r.json()["revision"], "version": tool["version"]},
    )
    assert r.status_code == 200, r.text
    c = client.get(prefix, headers=h).json()
    r = client.patch(
        prefix + "/enabled",
        headers=h,
        json={"enabled": True, "expected_revision": c["revision"], "version": tool["connection_revision"]},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/v1/skills",
        headers=h,
        json={
            "name": "fixture_" + kind,
            "description": "Explicit fixture",
            "instructions": "Explain source evidence and uncertainty.",
            "required_capabilities": [provider["operations"][0]["capability_tags"][0]],
        },
    )
    assert r.status_code == 201, r.text
    skill = r.json()
    path = "/api/v1/skills/" + skill["id"]
    e = {"version": skill["version"], "digest": skill["digest"], "request_key": uuid4().hex}
    assert client.post(path + "/test", headers=h, json=e).status_code == 202
    r = client.post(path + "/approve", headers=h, json=e)
    assert r.status_code == 200, r.text
    r = client.patch(
        path + "/enabled",
        headers=h,
        json={"enabled": True, "expected_revision": r.json()["revision"], "version": skill["version"]},
    )
    assert r.status_code == 200, r.text
    return skill, asset


@pytest.mark.parametrize("kind", ["photo", "rainfall"])
def test_evidence_then_ai_uses_saved_results_without_more_provider_requests(
    client, office, demo_http, monkeypatch, kind
):
    monkeypatch.setattr(get_settings(), "cloud_model_data_policy", "environment_only")
    t, _assignment, _farmer, plot, _ = setup_registry(client, office, monkeypatch)
    skill, asset = setup_demo(client, office, demo_http, monkeypatch, kind)
    h = office["users"]["admin"]["headers"]
    path = "/api/v1/skills/" + skill["id"]
    body = {"request_key": uuid4().hex, "authorize_network": True}
    body.update(
        {"image_asset_id": asset, "authorize_credit_use": True, "plot_ids": [plot["id"]]}
        if asset
        else {"territory_id": t["id"], "start": "2025-07-01", "end": "2025-07-31"}
    )
    before = len(demo_http[1])
    r = client.post(path + "/evidence-runs", headers=h, json=body)
    assert r.status_code == 202, r.text
    ident = r.json()["id"]
    asyncio.run(process_job(ident))
    job = client.get(r.json()["status_url"], headers=h).json()
    assert job["status"] == "succeeded", job
    assert job["result"]["model"]["model_request_executed"] is False
    assert job["result"]["outcomes"][0]["classification"] == "fixture"
    if asset:
        assert len(demo_http[1]) == before, "completed exact-version photo assessment is reused without a second credit"
    else:
        assert job["result"]["outcomes"][0]["data"]["summary"]["day_count"] == 31
        assert job["result"]["outcomes"][0]["data"]["summary"]["total_mm"] == 60
        evidence = client.get("/api/v1/evidence/" + job["result"]["evidence_ids"][0], headers=h).json()
        assert evidence["data"]["territory_id"] == t["id"] and not evidence["data"]["permitted_plot_ids"]
    before = len(demo_http[1])
    r = client.post(
        path + "/explanations",
        headers=h,
        json={
            "evidence_job_id": ident,
            "task": "Explain the evidence and general crop care.",
            "authorize_model": True,
            "request_key": uuid4().hex,
        },
    )
    assert r.status_code == 202, r.text

    class NoToolsModel(HomeModelFixture):
        async def generate(self, contents, tools, system):
            assert tools == []
            assert "Test Farmer" not in json.dumps(contents) and "Private sensitive" not in json.dumps(contents)
            return await super().generate(contents, tools, system)

    asyncio.run(process_job(r.json()["id"], model=NoToolsModel()))
    explanation = client.get(r.json()["status_url"], headers=h).json()
    assert explanation["status"] == "succeeded", explanation
    assert len(demo_http[1]) == before
    assert explanation["result"]["evidence_ids"] == job["result"]["evidence_ids"]
    assert (
        client.get("/api/v1/connector-jobs/" + ident, headers=office["users"]["outsider"]["headers"]).status_code == 403
    )


def test_rainfall_scope_and_input_consent_are_enforced(client, office, demo_http, monkeypatch):
    t, assignment, _, _, _ = setup_registry(client, office, monkeypatch)
    skill, _ = setup_demo(client, office, demo_http, monkeypatch, "rainfall")
    path = "/api/v1/skills/" + skill["id"] + "/evidence-runs"
    h = office["headers"]
    good = {
        "territory_id": t["id"],
        "start": "2025-07-01",
        "end": "2025-07-31",
        "authorize_network": True,
        "request_key": uuid4().hex,
    }
    for change in (
        {"authorize_network": False},
        {"end": "2025-07-05"},
        {"plot_ids": [office["plot"]["id"]]},
        {"latitude": 5},
    ):
        assert client.post(path, headers=h, json={**good, **change}).status_code in (403, 422)
    assert client.post(path, headers=office["users"]["farmer"]["headers"], json=good).status_code == 403
    r = client.post(path, headers=h, json=good)
    assert r.status_code == 202, r.text
    before = len(demo_http[1])
    assert (
        client.delete(
            "/api/v1/registry/assignments/" + assignment["id"] + "?expected_revision=1",
            headers=office["users"]["admin"]["headers"],
        ).status_code
        == 200
    )
    asyncio.run(process_job(r.json()["id"]))
    assert len(demo_http[1]) == before
    assert client.get(r.json()["status_url"], headers=h).status_code == 403
    assert client.post(path, headers=h, json={**good, "request_key": uuid4().hex}).status_code == 403


def test_explanation_requires_model_consent_and_completed_source(client, office, demo_http, monkeypatch):
    skill, asset = setup_demo(client, office, demo_http, monkeypatch, "photo")
    h = office["users"]["admin"]["headers"]
    path = "/api/v1/skills/" + skill["id"]
    body = {"image_asset_id": asset, "request_key": uuid4().hex, "authorize_network": True}
    assert client.post(path + "/evidence-runs", headers=h, json=body).status_code == 403
    r = client.post(path + "/evidence-runs", headers=h, json={**body, "authorize_credit_use": True})
    assert r.status_code == 202
    explanation = {
        "evidence_job_id": r.json()["id"],
        "task": "Explain the saved photo evidence.",
        "request_key": uuid4().hex,
    }
    assert client.post(path + "/explanations", headers=h, json=explanation).status_code == 403
    assert (
        client.post(path + "/explanations", headers=h, json={**explanation, "authorize_model": True}).status_code == 422
    )


def test_uncertainty_words_do_not_authorize_confirmed_diagnoses():
    from src.agent.companion.graph import validate_claims
    from src.integrations.contracts import ConnectorError

    ident = str(uuid4())
    outcomes = [{"evidence_ids": [ident], "data": {}}]
    validate_claims("This is not a confirmed diagnosis. Evidence: " + ident, outcomes)
    validate_claims("These candidates are **not** a confirmed diagnosis. Evidence: " + ident, outcomes)
    with pytest.raises(ConnectorError):
        validate_claims("This is a confirmed diagnosis. Evidence: " + ident, outcomes)
