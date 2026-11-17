"""Actual loopback HTTP fixtures. These tests do not claim agricultural provider availability."""

import asyncio
from copy import deepcopy
from datetime import timedelta, datetime, timezone
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlsplit
from threading import Thread
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select

from tests.test_workspace import office
from src.config.settings import get_settings
from src.db.models.connectors import (
    ConnectionCredential,
    ToolInvocation,
    InvocationAttempt,
    ExecutionBudget,
    ConnectorJob,
    ToolVersion,
)
from src.db.models.workspace import WorkspaceEvent
from src.db.session import SessionLocal
from src.integrations.jobs import process_job
from src.integrations.contracts import now
from src.tools.executor import ToolExecutor
from src.tools.policy import principal_for


@pytest.fixture
def rest_fixture(monkeypatch):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_request(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            calls.append(
                {"method": self.command, "path": self.path, "body": body.decode(), "headers": dict(self.headers)}
            )
            path = self.path.split("?")[0]
            status = 200
            content_type = "application/json"
            payload = {"data": {"ph": 6.8, "depth_cm": 20}, "metadata": {}}
            if path == "/search":
                payload = {
                    "rows": [{"crop": json.loads(body)["crop"], "price": 100}],
                    "period": json.loads(body)["period"],
                }
            elif path == "/v1/forecast":
                today = datetime.now(timezone(timedelta(hours=3))).date()
                payload = {
                    "latitude": 9.03,
                    "longitude": 38.74,
                    "daily": {
                        "time": [(today + timedelta(days=i)).isoformat() for i in range(3)],
                        "temperature_2m_max": [25, 26, 27],
                        "precipitation_sum": [0, 2, 3],
                        "et0_fao_evapotranspiration": [4, 5, 6],
                        "wind_speed_10m_max": [10, 11, 12],
                    },
                    "daily_units": {
                        "temperature_2m_max": "°C",
                        "precipitation_sum": "mm",
                        "et0_fao_evapotranspiration": "mm",
                        "wind_speed_10m_max": "km/h",
                    },
                }
            elif path == "/login":
                payload = {"access_token": "explicit-fixture-short-lived-token", "token_type": "bearer"}
            elif path == "/isdasoil/v2/layers":
                payload = {
                    "property": {
                        prop: {"depths": {"values": ["0-20"]}, "unit": unit}
                        for prop, unit in [("ph", "pH"), ("carbon_organic", "g/kg")]
                    }
                }
            elif path == "/isdasoil/v2/soilproperty":
                prop = parse_qs(urlsplit(self.path).query)["property"][0]
                payload = {
                    "property": {
                        prop: [
                            {
                                "depth": {"value": "0-20", "unit": "cm"},
                                "value": {
                                    "value": 6.8 if prop == "ph" else 12.5,
                                    "unit": "pH" if prop == "ph" else "g/kg",
                                },
                                "uncertainty": {
                                    "confidence_interval": "90%",
                                    "lower_bound": 6 if prop == "ph" else 10,
                                    "upper_bound": 7.2 if prop == "ph" else 15,
                                },
                            }
                        ]
                    }
                }
            elif path == "/api/submitDataRequest/":
                payload = ["00000000-0000-4000-8000-000000000001"]
                content_type = "text/plain"
            elif path == "/api/getDataRequestProgress/":
                payload = [100]
                content_type = "text/html"
            elif path == "/api/getDataFromRequest/":
                payload = {"data": [{"date": "07/01/2025", "value": {"avg": 7.8}}]}
                content_type = "text/plain"
            elif path == "/empty":
                status = 204
                payload = None
            elif path == "/html":
                content_type = "text/html"
                payload = "<html>Log in</html>"
            elif path == "/missing":
                payload = {"data": {"depth_cm": 20}}
            elif path == "/invalid":
                payload = {"data": {"ph": "unknown", "depth_cm": 20}}
            elif path == "/echo-secret":
                payload = {"data": {"ph": 6.8, "depth_cm": 20}, "echo": self.headers.get("X-API-Key")}
            elif path == "/retry" and sum(c["path"].split("?")[0] == "/retry" for c in calls) == 1:
                status = 429
                payload = {"error": "rate limit"}
            elif path == "/auth":
                status = 401
                payload = {"error": "authentication rejected", "echo": self.headers.get("X-API-Key")}
            elif path == "/redirect":
                status = 302
            elif path == "/huge":
                payload = {"padding": "x" * 100000}
            content = (
                b""
                if payload is None
                else json.dumps(payload).encode()
                if content_type == "application/json" or isinstance(payload, (dict, list, int, float, bool))
                else payload.encode()
            )
            if path == "/huge":
                content = gzip.compress(content)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            if status == 429:
                self.send_header("Retry-After", "0")
            if path == "/huge":
                self.send_header("Content-Encoding", "gzip")
            if status == 302:
                self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
            self.wfile.write(content)

        do_GET = handle_request
        do_POST = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "connector_fixture_origins", [origin])
    monkeypatch.setattr(settings, "secret_encryption_key", Fernet.generate_key().decode())
    yield origin, calls
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def soil_spec(name="soil_profile", path="/soil"):
    return {
        "name": name,
        "description": "Retrieve a fixture soil profile; not real agricultural observations.",
        "capability_tags": ["soil.profile"],
        "input_json_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
            },
            "required": ["latitude", "longitude"],
            "additionalProperties": False,
        },
        "required_data_classes": ["plot_coordinates"],
        "request": {
            "method": "GET",
            "path": path,
            "query": {
                "lat": {"source": "argument", "pointer": "/latitude"},
                "lon": {"source": "argument", "pointer": "/longitude"},
            },
        },
        "response": {
            "field_mapping": {
                "ph": {"source": "response", "pointer": "/data/ph"},
                "depth_cm": {"source": "response", "pointer": "/data/depth_cm"},
                "observation_date": {"source": "response", "pointer": "/metadata/date", "required": False},
            },
            "normalized_output_json_schema": {
                "type": "object",
                "properties": {
                    "ph": {"type": "number", "minimum": 0, "maximum": 14},
                    "depth_cm": {"type": "number"},
                    "observation_date": {"type": ["string", "null"]},
                },
                "required": ["ph", "depth_cm"],
                "additionalProperties": False,
            },
        },
        "evidence_semantics": {"value_kind": "predicted_soil_property", "units": {"ph": "pH", "depth_cm": "cm"}},
    }


def connection(client, o, origin, auth=None):
    r = client.post(
        "/api/v1/integrations",
        headers=o["users"]["admin"]["headers"],
        json={
            "name": "Explicit local fixture",
            "adapter_type": "rest",
            "base_url": origin,
            "authentication": auth or {"type": "none"},
            "egress_data_classes": ["public_environment", "plot_coordinates"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def register(client, o, conn, spec):
    r = client.post(f"/api/v1/integrations/{conn['id']}/tools", json=spec, headers=o["users"]["admin"]["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def exact(tool):
    return {key: tool[key] for key in ("version", "connection_revision", "digest")}


def test_and_publish(client, o, conn, tool, arguments=None):
    headers = o["users"]["admin"]["headers"]
    prefix = f"/api/v1/integrations/{conn['id']}"
    args = {"latitude": 9.03, "longitude": 38.74} if arguments is None else arguments
    r = client.post(
        prefix + f"/tools/{tool['id']}/test",
        headers=headers,
        json={
            **exact(tool),
            "arguments": args,
            "plot_ids": [o["plot"]["id"]] if o.get("plot") else [],
            "authorize_network": True,
            "request_key": uuid4().hex,
        },
    )
    assert r.status_code == 202, r.text
    asyncio.run(process_job(r.json()["id"]))
    result = client.get(r.json()["status_url"], headers=headers).json()
    if result["status"] == "succeeded":
        r = client.post(prefix + f"/tools/{tool['id']}/approve", json=exact(tool), headers=headers)
        assert r.status_code == 200, r.text
        tool = r.json()
        r = client.patch(
            prefix + f"/tools/{tool['id']}/enabled",
            headers=headers,
            json={"enabled": True, "expected_revision": tool["revision"], "version": tool["version"]},
        )
        assert r.status_code == 200, r.text
        current = client.get(prefix, headers=headers).json()
        r = client.patch(
            prefix + "/enabled",
            headers=headers,
            json={"enabled": True, "expected_revision": current["revision"], "version": tool["connection_revision"]},
        )
        assert r.status_code == 200, r.text
    return result


def runtime(o, tool, arguments=None, *, budget_id=None, request_key=None):
    with SessionLocal() as db:
        principal = principal_for(db, o["users"]["officer"]["id"])
        if not budget_id:
            budget = ExecutionBudget(office_id=o["id"], deadline=now() + timedelta(seconds=30))
            db.add(budget)
            db.flush()
            budget_id = budget.id
            db.commit()
    return asyncio.run(
        ToolExecutor().execute(
            tool["version_id"],
            {"latitude": 9.03, "longitude": 38.74} if arguments is None else arguments,
            principal,
            budget_id=budget_id,
            request_key=request_key or uuid4().hex,
            plot_ids=[o["plot"]["id"]],
            authorize_network=True,
        )
    )


test_and_publish.__test__ = False


def test_two_rest_tools_are_registered_and_executed_without_code_changes(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn = connection(client, office, origin)
    first = register(client, office, conn, soil_spec())
    before = len(calls)
    r = client.post(
        f"/api/v1/integrations/{conn['id']}/tools/{first['id']}/preview",
        headers=office["users"]["admin"]["headers"],
        json={
            **exact(first),
            "arguments": {"latitude": 9.03, "longitude": 38.74},
            "plot_ids": [office["plot"]["id"]],
            "request_key": uuid4().hex,
        },
    )
    assert r.status_code == 200, r.text
    assert len(calls) == before
    assert test_and_publish(client, office, conn, first)["status"] == "succeeded"
    result = runtime(office, first)
    assert result["data"] == {"ph": 6.8, "depth_cm": 20, "observation_date": None}
    assert result["classification"] == "fixture"
    assert result["source"]["url"].endswith("/soil")
    assert "lat=9.03" in calls[-1]["path"]
    assert result["limitations"] and result["source"].get("observed_at") is None
    spec = {
        "name": "market_search",
        "description": "Search the explicitly synthetic fixture market.",
        "capability_tags": ["market.search"],
        "input_json_schema": {
            "type": "object",
            "properties": {"crop": {"type": "string", "enum": ["maize"]}},
            "required": ["crop"],
            "additionalProperties": False,
        },
        "request": {
            "method": "POST",
            "path": "/search",
            "body": {"crop": {"source": "argument", "pointer": "/crop"}, "period": {"source": "literal", "value": 7}},
        },
        "response": {"normalized_output_json_schema": {"type": "object", "required": ["rows", "period"]}},
    }
    second = register(client, office, conn, spec)
    assert test_and_publish(client, office, conn, second, {"crop": "maize"})["status"] == "succeeded"
    assert runtime(office, second, {"crop": "maize"})["data"]["period"] == 7
    assert json.loads(calls[-1]["body"]) == {"crop": "maize", "period": 7}


@pytest.mark.parametrize(
    "arguments,code",
    [
        ({"latitude": "9.03", "longitude": 38.74}, "INPUT_VALIDATION_FAILED"),
        ({"latitude": 91, "longitude": 38.74}, "INPUT_VALIDATION_FAILED"),
        ({"latitude": 9.03, "longitude": 38.74, "url": "http://evil.test"}, "INPUT_VALIDATION_FAILED"),
        ({"latitude": 7.06, "longitude": 38.48}, "POLICY_DENIED"),
    ],
)
def test_invalid_arguments_never_reach_network(client, office, rest_fixture, arguments, code):
    origin, calls = rest_fixture
    conn = connection(client, office, origin)
    tool = register(client, office, conn, soil_spec())
    assert test_and_publish(client, office, conn, tool)["status"] == "succeeded"
    before = len(calls)
    result = runtime(office, tool, arguments)
    assert result["execution_outcome"] == code, result
    assert len(calls) == before


@pytest.mark.parametrize(
    "path,outcome",
    [
        ("/html", "OUTPUT_VALIDATION_FAILED"),
        ("/invalid", "OUTPUT_VALIDATION_FAILED"),
        ("/missing", "OUTPUT_VALIDATION_FAILED"),
        ("/auth", "AUTH_INVALID"),
        ("/redirect", "EGRESS_BLOCKED"),
        ("/empty", "SUCCESS"),
        ("/huge", "RESPONSE_TOO_LARGE"),
    ],
)
def test_provider_failure_and_no_data_are_distinct(client, office, rest_fixture, path, outcome):
    origin, _ = rest_fixture
    conn = connection(client, office, origin)
    spec = soil_spec(path=path)
    if path == "/huge":
        spec["policy"] = {"max_response_bytes": 1024}
    tool = register(client, office, conn, spec)
    result = test_and_publish(client, office, conn, tool)
    assert result["result"]["execution_outcome"] == outcome, result
    if path == "/empty":
        assert result["result"]["data_outcome"] == "NO_DATA" and not result["result"]["evidence_ids"]


def test_header_credentials_are_encrypted_and_redacted(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn = connection(client, office, origin, {"type": "api_key_header", "header_name": "X-API-Key"})
    secret = "fixture-secret-" + uuid4().hex
    r = client.put(
        f"/api/v1/integrations/{conn['id']}/credential",
        headers=office["users"]["admin"]["headers"],
        json={"value": secret, "principal_scope": "fixture-account:read"},
    )
    assert r.status_code == 200 and secret not in r.text
    tool = register(client, office, conn, soil_spec(path="/echo-secret"))
    assert test_and_publish(client, office, conn, tool)["status"] == "succeeded"
    result = runtime(office, tool)
    assert calls[-1]["headers"]["X-API-Key"] == secret
    with SessionLocal() as db:
        cred = db.scalar(select(ConnectionCredential))
        assert secret not in cred.ciphertext
        for cls in [ToolInvocation, ConnectorJob, ToolVersion, WorkspaceEvent]:
            for row in db.scalars(select(cls)):
                assert secret not in str({c.name: getattr(row, c.name) for c in cls.__table__.columns})
    assert secret not in json.dumps(result)


def test_revocation_blocks_pinned_runs_and_cache_hits(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn = connection(client, office, origin)
    spec = soil_spec()
    spec["policy"] = {"cache_ttl_seconds": 3600}
    tool = register(client, office, conn, spec)
    assert test_and_publish(client, office, conn, tool)["status"] == "succeeded"
    first = runtime(office, tool)
    before = len(calls)
    second = runtime(office, tool)
    assert second["cache_hit"] and second["retrieved_at"] == first["retrieved_at"] and len(calls) == before
    headers = office["users"]["admin"]["headers"]
    current = client.get(f"/api/v1/integrations/{conn['id']}", headers=headers).json()
    r = client.patch(
        f"/api/v1/integrations/{conn['id']}/enabled",
        headers=headers,
        json={"enabled": False, "expected_revision": current["revision"]},
    )
    assert r.status_code == 200
    assert runtime(office, tool)["execution_outcome"] == "TOOL_REVOKED"
    assert len(calls) == before


def test_safe_reads_retry_within_shared_request_budget(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn = connection(client, office, origin)
    tool = register(client, office, conn, soil_spec(path="/retry"))
    result = test_and_publish(client, office, conn, tool)
    assert result["status"] == "succeeded", result
    assert len(calls) == 2
    with SessionLocal() as db:
        assert db.scalar(select(ExecutionBudget)).requests == 2
        assert len(list(db.scalars(select(InvocationAttempt)))) == 2


def test_scope_and_configuration_cannot_grant_network_exceptions(client, office, rest_fixture):
    _, calls = rest_fixture
    headers = office["users"]["admin"]["headers"]
    for url in [
        "http://127.0.0.1",
        "https://169.254.169.254",
        "https://api.open-meteo.com.evil.test",
        "https://user:password@api.open-meteo.com",
        "https://api.open-meteo.com//override",
    ]:
        r = client.post(
            "/api/v1/integrations", headers=headers, json={"name": "Unsafe", "adapter_type": "rest", "base_url": url}
        )
        assert r.status_code in (403, 422), r.text
    r = client.post(
        "/api/v1/integrations",
        headers=headers,
        json={"name": "Code", "adapter_type": "mcp", "base_url": "https://example.com", "command": "python evil.py"},
    )
    assert r.status_code == 422
    assert not calls
