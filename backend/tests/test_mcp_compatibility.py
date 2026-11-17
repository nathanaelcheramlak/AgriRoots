"""Authenticated SDK lifecycle isolation and explicit compatibility blockers."""

# ruff: noqa: F401, F811 -- pytest discovers imported fixtures by name
import asyncio
from datetime import timedelta
from uuid import uuid4

from cryptography.fernet import Fernet

from tests.test_workspace import office
from tests.test_connectors_mcp import mcp_fixture, connect_mcp, discover, reviewed_tool
from tests.test_connectors_rest import test_and_publish
from src.config.settings import get_settings
from src.db.models.connectors import ExecutionBudget
from src.db.models.workspace import Administrator
from src.db.session import SessionLocal
from src.integrations.contracts import now
from src.tools.executor import ToolExecutor
from src.tools.policy import principal_for


def test_mcp_authenticated_clients_are_isolated_across_offices(client, office, mcp_fixture, monkeypatch):
    endpoint, state = mcp_fixture
    monkeypatch.setattr(get_settings(), "secret_encryption_key", Fernet.generate_key().decode())
    outsider = office["users"]["outsider"]
    with SessionLocal() as db:
        db.add(Administrator(user_id=outsider["id"]))
        db.commit()
    response = client.post(
        "/api/workspace/offices", headers=outsider["headers"], json={"name": "Second MCP fixture office"}
    )
    assert response.status_code == 201
    second = {"id": response.json()["id"], "users": {"admin": outsider, "officer": outsider}}
    checks = []
    for number, o in enumerate([office, second]):
        secret = "explicit-office-fixture-secret-" + str(number)
        headers = o["users"]["admin"]["headers"]
        response = client.post(
            "/api/v1/integrations",
            headers=headers,
            json={
                "name": "Scoped HTTP MCP fixture",
                "adapter_type": "mcp",
                "base_url": endpoint,
                "authentication": {"type": "api_key_header", "header_name": "X-Office-Key"},
            },
        )
        assert response.status_code == 201
        conn = response.json()
        assert (
            client.put(
                f"/api/v1/integrations/{conn['id']}/credential",
                headers=headers,
                json={"value": secret, "principal_scope": "fixture-account-" + str(number)},
            ).status_code
            == 200
        )
        start = len(state["headers"])
        assert discover(client, o, conn)["status"] == "succeeded"
        tool = reviewed_tool(client, o, conn)
        assert test_and_publish(client, o, conn, tool, {"term": "maize"})["status"] == "succeeded"
        assert all(row.get(b"x-office-key") == secret.encode() for row in state["headers"][start:])
        checks.append((o, tool, secret))
    for o, tool, secret in checks:
        with SessionLocal() as db:
            actor = principal_for(db, o["users"]["admin"]["id"])
            spending = ExecutionBudget(office_id=o["id"], deadline=now() + timedelta(seconds=30))
            db.add(spending)
            db.flush()
            budget_id = spending.id
            db.commit()
        start = len(state["headers"])
        result = asyncio.run(
            ToolExecutor().execute(
                tool["version_id"],
                {"term": "maize"},
                actor,
                budget_id=budget_id,
                request_key=uuid4().hex,
                authorize_network=True,
            )
        )
        assert result["execution_outcome"] == "SUCCESS"
        assert all(row.get(b"x-office-key") == secret.encode() for row in state["headers"][start:])
        assert secret not in str(result)


def test_mcp_unhandled_artifacts_are_blocked_without_retrieval(client, office, mcp_fixture):
    endpoint, _ = mcp_fixture
    conn = connect_mcp(client, office, endpoint)
    assert discover(client, office, conn)["status"] == "succeeded"
    tool = reviewed_tool(client, office, conn, "notes")
    result = test_and_publish(client, office, conn, tool, {"term": "unsupported_artifact"})
    assert result["status"] == "failed" and result["result"]["execution_outcome"] == "UNSUPPORTED_CAPABILITY"


def test_unsupported_auth_transport_and_sdk_version_fail_honestly(client, office, mcp_fixture, monkeypatch):
    endpoint, state = mcp_fixture
    headers = office["users"]["admin"]["headers"]
    for change, code in [
        ({"authentication": {"type": "oauth"}}, "UNSUPPORTED_AUTH"),
        ({"transport": "stdio"}, "UNSUPPORTED_TRANSPORT"),
    ]:
        response = client.post(
            "/api/v1/integrations",
            headers=headers,
            json={"name": "Unsupported fixture connection", "adapter_type": "mcp", "base_url": endpoint, **change},
        )
        assert response.status_code == 422 and response.json()["error"]["code"] == code
    assert not state["headers"]
    conn = connect_mcp(client, office, endpoint)
    monkeypatch.setattr("src.integrations.mcp_client.package_version", lambda package: "0.0-unverified")
    result = discover(client, office, conn)
    assert result["status"] == "failed" and result["error"]["code"] == "UNSUPPORTED_PROTOCOL"
    assert not state["headers"]
