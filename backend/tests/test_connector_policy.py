"""Tenant isolation, hot revocation, budgets and egress with operator-owned fixtures."""

# ruff: noqa: F401, F811 -- pytest discovers imported fixtures by name
import asyncio
from datetime import timedelta
import json
import socket
import time
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from tests.test_workspace import office  # noqa: F401
from tests.test_connectors_rest import rest_fixture, connection, register, soil_spec, exact, test_and_publish, runtime  # noqa: F401
from src.config.settings import get_settings, Settings
from src.db.models.connectors import (
    Integration,
    ConnectionCredential,
    ExecutionBudget,
    ToolInvocation,
    InvocationAttempt,
    ConnectorCache,
    ConnectorJob,
)
from src.db.models.workspace import Administrator
from src.db.session import SessionLocal
from src.integrations.contracts import ConnectorError, now, digest
from src.integrations.jobs import process_job, claim
from src.integrations.safe_http import destination
from src.tools.executor import ToolExecutor, DispatchGate
from src.tools.policy import principal_for


def budget(o, *, calls=24, requests=80):
    with SessionLocal() as db:
        row = ExecutionBudget(
            office_id=o["id"], max_calls=calls, max_requests=requests, deadline=now() + timedelta(seconds=30)
        )
        db.add(row)
        db.flush()
        ident = row.id
        db.commit()
    return ident


def publish(client, o, origin, *, auth=None, ttl=0, roles=None):
    conn = connection(client, o, origin, auth)
    if auth:
        r = client.put(
            f"/api/v1/integrations/{conn['id']}/credential",
            headers=o["users"]["admin"]["headers"],
            json={"value": "explicit-fixture-key-a", "principal_scope": "fixture-account-a"},
        )
        assert r.status_code == 200, r.text
    spec = soil_spec()
    spec["policy"] = {"cache_ttl_seconds": ttl}
    if roles:
        spec["allowed_roles"] = roles
    tool = register(client, o, conn, spec)
    assert test_and_publish(client, o, conn, tool)["status"] == "succeeded"
    return conn, tool


def test_cross_office_management_jobs_credentials_and_evidence_denied(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin)
    result = runtime(office, tool)
    with SessionLocal() as db:
        db.add(Administrator(user_id=office["users"]["outsider"]["id"]))
        db.commit()
    other_headers = office["users"]["outsider"]["headers"]
    r = client.post("/api/workspace/offices", headers=other_headers, json={"name": "Second synthetic office"})
    assert r.status_code == 201, r.text
    before = len(calls)
    prefix = f"/api/v1/integrations/{conn['id']}"
    requests = [
        ("GET", prefix, None),
        ("GET", prefix + "/tools", None),
        ("GET", prefix + "/tests", None),
        ("PUT", prefix + "/credential", {"value": "owned-by-second-office", "principal_scope": "second"}),
        ("POST", prefix + f"/tools/{tool['id']}/test", {**exact(tool), "arguments": {}, "request_key": uuid4().hex}),
        ("GET", f"/api/v1/evidence/{result['evidence_ids'][0]}", None),
    ]
    with SessionLocal() as db:
        job = db.scalar(select(ConnectorJob))
        requests.append(("GET", f"/api/v1/runs/{job.id}/results", None))
    for method, path, body in requests:
        response = client.request(method, path, headers=other_headers, json=body)
        assert response.status_code == 404, (path, response.text)
    assert client.get("/api/v1/integrations", headers=other_headers).json()["items"] == []
    assert len(calls) == before


def test_per_tool_role_is_checked_at_dispatch(client, office, rest_fixture):
    origin, calls = rest_fixture
    _, tool = publish(client, office, origin, roles=["office_admin"])
    before = len(calls)
    assert runtime(office, tool)["execution_outcome"] == "POLICY_DENIED"
    assert len(calls) == before


def test_credential_rotation_invalidates_approval_cache_and_pinned_replay(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin, auth={"type": "api_key_header", "header_name": "X-API-Key"}, ttl=3600)
    key, run_budget = uuid4().hex, budget(office)
    original = runtime(office, tool, budget_id=run_budget, request_key=key)
    assert original["execution_outcome"] == "SUCCESS"
    before = len(calls)
    headers = office["users"]["admin"]["headers"]
    r = client.put(
        f"/api/v1/integrations/{conn['id']}/credential",
        headers=headers,
        json={"value": "explicit-fixture-key-b", "principal_scope": "fixture-account-a"},
    )
    assert r.status_code == 200 and r.json()["retest_required"]
    view = client.get(f"/api/v1/integrations/{conn['id']}", headers=headers).json()
    r = client.patch(
        f"/api/v1/integrations/{conn['id']}/enabled",
        headers=headers,
        json={"enabled": True, "expected_revision": view["revision"], "version": 1},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "APPROVAL_REQUIRED"
    denied = runtime(office, tool, budget_id=run_budget, request_key=key)
    assert denied["execution_outcome"] == "TOOL_REVOKED" and len(calls) == before
    with SessionLocal() as db:
        stored = db.get(ToolInvocation, original["invocation_id"])
        assert stored.status == "SUCCESS" and stored.result == original
        assert db.get(ToolInvocation, denied["invocation_id"]).input_metadata["replay_of"] == stored.id
    assert test_and_publish(client, office, conn, tool)["status"] == "succeeded"
    before = len(calls)
    fresh = runtime(office, tool)
    # The fresh authorized test may populate the new scope's cache; the old
    # credential's evidence must never be reused after rotation.
    assert fresh["execution_outcome"] == "SUCCESS" and fresh["retrieved_at"] != original["retrieved_at"]
    assert len(calls) == before and calls[-1]["headers"]["X-API-Key"] == "explicit-fixture-key-b"


def test_finished_cache_invocation_replay_preserves_original_retrieval(client, office, rest_fixture):
    origin, calls = rest_fixture
    _, tool = publish(client, office, origin, ttl=3600)
    original = runtime(office, tool)
    key, run_budget = uuid4().hex, budget(office)
    cached = runtime(office, tool, budget_id=run_budget, request_key=key)
    before = len(calls)
    replay = runtime(office, tool, budget_id=run_budget, request_key=key)
    assert replay["idempotency_replay"] and cached["cache_hit"]
    assert replay["retrieved_at"] == original["retrieved_at"] and len(calls) == before


def test_followup_reuses_success_in_same_budget_without_another_remote_call(client, office, rest_fixture):
    origin, calls = rest_fixture
    _, tool = publish(client, office, origin)
    run_budget = budget(office)
    first = runtime(office, tool, budget_id=run_budget)
    before = len(calls)
    second = runtime(office, tool, budget_id=run_budget)
    assert second["same_run_reuse"] and second["reused_invocation_id"] == first["invocation_id"]
    assert second["retrieved_at"] == first["retrieved_at"] and len(calls) == before


@pytest.mark.parametrize("kind", ["calls", "requests"])
def test_parallel_calls_consume_one_shared_atomic_budget(client, office, rest_fixture, kind):
    origin, calls = rest_fixture
    _, tool = publish(client, office, origin)
    run_budget = budget(office, calls=1 if kind == "calls" else 24, requests=1 if kind == "requests" else 80)
    with SessionLocal() as db:
        actor = principal_for(db, office["users"]["officer"]["id"])
    before = len(calls)

    async def parallel():
        return await asyncio.gather(
            *(
                ToolExecutor().execute(
                    tool["version_id"],
                    {"latitude": 9.03, "longitude": 38.74},
                    actor,
                    budget_id=run_budget,
                    request_key=uuid4().hex,
                    plot_ids=[office["plot"]["id"]],
                    authorize_network=True,
                )
                for _ in range(2)
            )
        )

    results = asyncio.run(parallel())
    assert sorted(item["execution_outcome"] for item in results) == ["BUDGET_EXCEEDED", "SUCCESS"], results
    assert len(calls) == before + 1
    with SessionLocal() as db:
        stored = db.get(ExecutionBudget, run_budget)
        assert stored.requests == 1 and stored.active == 0


def test_emergency_revocation_between_reservation_and_final_gate_blocks_http(client, office, rest_fixture, monkeypatch):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin)
    original = DispatchGate.reserve_http

    def reserve_then_revoke(self, method, endpoint):
        ident = original(self, method, endpoint)
        with SessionLocal() as db:
            db.get(Integration, conn["id"]).enabled = False
            db.commit()
        return ident

    monkeypatch.setattr(DispatchGate, "reserve_http", reserve_then_revoke)
    before = len(calls)
    assert runtime(office, tool)["execution_outcome"] == "TOOL_REVOKED"
    assert len(calls) == before
    with SessionLocal() as db:
        assert db.scalars(select(InvocationAttempt).where(InvocationAttempt.outcome == "TOOL_REVOKED")).first()


def test_wrong_digest_and_new_configuration_do_not_inherit_approval(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin)
    headers = office["users"]["admin"]["headers"]
    prefix = f"/api/v1/integrations/{conn['id']}"
    r = client.post(prefix + f"/tools/{tool['id']}/approve", headers=headers, json={**exact(tool), "digest": "0" * 64})
    assert r.status_code == 409
    view = client.get(prefix, headers=headers).json()
    config = {
        "name": "Changed configuration",
        "adapter_type": "rest",
        "base_url": origin,
        "egress_data_classes": ["plot_coordinates", "public_environment"],
    }
    r = client.post(
        prefix + "/versions", headers=headers, json={"expected_revision": view["revision"], "configuration": config}
    )
    assert r.status_code == 201, r.text
    r = client.patch(
        prefix + "/enabled",
        headers=headers,
        json={"enabled": True, "expected_revision": r.json()["revision"], "version": 2},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "APPROVAL_REQUIRED"


def test_platform_jwt_and_gemini_key_cannot_be_provider_credentials(client, office, rest_fixture, monkeypatch):
    origin, calls = rest_fixture
    conn = connection(client, office, origin, {"type": "bearer"})
    monkeypatch.setattr(get_settings(), "gemini_api_key", "fixture-model-key-do-not-forward")
    headers = office["users"]["admin"]["headers"]
    values = [
        headers["Authorization"].split(" ")[1],
        get_settings().gemini_api_key,
        get_settings().jwt_secret_key,
        {"nested": get_settings().gemini_api_key},
    ]
    for value in values:
        r = client.put(
            f"/api/v1/integrations/{conn['id']}/credential",
            headers=headers,
            json={"value": value, "principal_scope": "forbidden"},
        )
        assert r.status_code == 403, r.text
        assert str(value) not in r.text
    with SessionLocal() as db:
        assert db.scalar(select(ConnectionCredential)) is None
    assert not calls


def test_runtime_expiry_cache_partition_and_cancelled_job(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin, ttl=1)
    first = runtime(office, tool)
    time.sleep(1.1)
    before = len(calls)
    fresh = runtime(office, tool)
    assert not fresh["cache_hit"] and fresh["retrieved_at"] != first["retrieved_at"] and len(calls) == before + 1
    headers = office["users"]["admin"]["headers"]
    response = client.post(
        f"/api/v1/integrations/{conn['id']}/tools/{tool['id']}/test",
        headers=headers,
        json={
            **exact(tool),
            "arguments": {"latitude": 9.03, "longitude": 38.74},
            "plot_ids": [office["plot"]["id"]],
            "authorize_network": True,
            "request_key": uuid4().hex,
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    assert client.post(f"/api/v1/runs/{job_id}/cancel", headers=headers).json()["status"] == "cancelled"
    before = len(calls)
    assert asyncio.run(process_job(job_id)) is False and len(calls) == before


def test_expired_lease_is_fenced_before_provider_dispatch(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin)
    headers = office["users"]["admin"]["headers"]
    request = {
        **exact(tool),
        "arguments": {"latitude": 9.03, "longitude": 38.74},
        "plot_ids": [office["plot"]["id"]],
        "authorize_network": True,
        "request_key": uuid4().hex,
    }
    response = client.post(f"/api/v1/integrations/{conn['id']}/tools/{tool['id']}/test", headers=headers, json=request)
    assert response.status_code == 202
    ident = response.json()["id"]
    old = claim(ident)
    with SessionLocal() as db:
        job = db.get(ConnectorJob, ident)
        job.lease_until = now() - timedelta(seconds=1)
        run_budget = job.budget_id
        actor = principal_for(db, job.principal_id)
        db.commit()
    current = claim(ident)
    assert current and current != old
    before = len(calls)
    denied = asyncio.run(
        ToolExecutor().execute(
            tool["version_id"],
            request["arguments"],
            actor,
            budget_id=run_budget,
            request_key=uuid4().hex,
            job_id=ident,
            mode="test",
            plot_ids=request["plot_ids"],
            authorize_network=True,
            lease_token=old,
        )
    )
    assert denied["execution_outcome"] == "CANCELLED" and len(calls) == before


def test_recovered_job_does_not_repeat_an_ambiguous_dispatched_operation(client, office, rest_fixture):
    origin, calls = rest_fixture
    conn, tool = publish(client, office, origin)
    headers = office["users"]["admin"]["headers"]
    arguments = {"latitude": 9.03, "longitude": 38.74}
    response = client.post(
        f"/api/v1/integrations/{conn['id']}/tools/{tool['id']}/test",
        headers=headers,
        json={
            **exact(tool),
            "arguments": arguments,
            "plot_ids": [office["plot"]["id"]],
            "authorize_network": True,
            "request_key": uuid4().hex,
        },
    )
    assert response.status_code == 202
    ident = response.json()["id"]
    assert claim(ident)
    with SessionLocal() as db:
        job = db.get(ConnectorJob, ident)
        job.lease_until = now() - timedelta(seconds=1)
        # Explicit crash fixture: the old worker recorded dispatch but died before
        # recording the remote outcome. This is not a fabricated test success.
        db.add(
            ToolInvocation(
                office_id=office["id"],
                principal_id=job.principal_id,
                tool_version_id=tool["version_id"],
                job_id=ident,
                budget_id=job.budget_id,
                request_key=ident + ":test",
                argument_digest=digest(arguments),
                input_metadata={"mode": "test", "dispatched": True},
                status="executing",
            )
        )
        db.commit()
    before = len(calls)
    asyncio.run(process_job(ident))
    job = client.get(response.json()["status_url"], headers=headers).json()
    assert job["status"] == "failed" and job["result"]["execution_outcome"] == "AMBIGUOUS_OUTCOME"
    assert job["attempts"] == 2 and len(calls) == before


def test_hot_operator_policy_is_authoritative_and_fixture_exception_forbidden_in_production(tmp_path, monkeypatch):
    settings = get_settings()
    path = tmp_path / "egress.json"
    monkeypatch.setattr(settings, "outbound_hosts_policy_file", str(path))
    monkeypatch.setattr(settings, "connector_fixture_origins", [])
    path.write_text(json.dumps({"hosts": ["api.open-meteo.com"]}))
    destination("https://api.open-meteo.com/v1/forecast")
    path.write_text(json.dumps({"hosts": ["power.larc.nasa.gov"]}))
    with pytest.raises(ConnectorError, match="outside"):
        destination("https://api.open-meteo.com/v1/forecast")
    destination("https://power.larc.nasa.gov/mcp")
    with pytest.raises(ValueError, match="forbidden"):
        Settings(app_env="production", connector_fixture_origins=["http://127.0.0.1:9999"])


def test_dns_resolver_rejects_mixed_private_answers(monkeypatch):
    from src.mcp.egress_proxy import public_addresses

    async def scenario():
        loop = asyncio.get_running_loop()

        async def resolver(*args, **kwargs):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443)),
            ]

        monkeypatch.setattr(loop, "getaddrinfo", resolver)
        with pytest.raises(ValueError, match="private"):
            await public_addresses("operator-fixture.example")

    asyncio.run(scenario())


def test_connect_proxy_pins_literal_resolved_public_address(monkeypatch):
    from src.mcp import egress_proxy as module

    contacted = []
    real_connect = asyncio.open_connection

    async def resolver(host):
        assert host == "operator-fixture.example"
        return ["93.184.216.34"]

    async def connector(host, port):
        if host == "93.184.216.34":
            contacted.append((host, port))
            raise OSError("Controlled fixture: never contact this address")
        return await real_connect(host, port)

    monkeypatch.setattr(module, "public_addresses", resolver)
    monkeypatch.setattr(module.asyncio, "open_connection", connector)

    async def scenario():
        async with module.egress_proxy(frozenset({"operator-fixture.example"})) as proxy:
            async with httpx.AsyncClient(proxy=proxy, trust_env=False, timeout=2) as client:
                with pytest.raises(httpx.ProxyError):
                    await client.get("https://operator-fixture.example/")

    asyncio.run(scenario())
    assert contacted == [("93.184.216.34", 443)]


@pytest.mark.parametrize(
    "change",
    [
        {"command": "python malicious.py"},
        {"request": {"method": "DELETE", "path": "/soil"}},
        {"input_json_schema": {"type": "object", "properties": {"x": {"$ref": "https://metadata.invalid/schema"}}}},
        {"effect_classification": "MODIFY_EXTERNAL"},
    ],
)
def test_configuration_cannot_execute_code_or_unsupported_effects(client, office, rest_fixture, change):
    origin, calls = rest_fixture
    conn = connection(client, office, origin)
    response = client.post(
        f"/api/v1/integrations/{conn['id']}/tools",
        headers=office["users"]["admin"]["headers"],
        json={**soil_spec(), **change},
    )
    assert response.status_code in (403, 422), response.text
    assert not calls
