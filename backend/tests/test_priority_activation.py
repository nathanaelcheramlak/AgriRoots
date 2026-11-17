"""Priority activation exercises real approval gates against labeled HTTP fixtures."""

# ruff: noqa: F401, F811 -- pytest imports fixtures by name
import asyncio
import importlib.util
from pathlib import Path

from sqlalchemy import select, func

from tests.test_workspace import office
from tests.test_connectors_rest import rest_fixture, register
from src.db.models.connectors import Integration, RegisteredTool, DefinitionApproval
from src.db.session import SessionLocal
from src.providers.factory import HANDLERS, template
from src.tools.policy import principal_for

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("priority_activation", ROOT / "scripts/activate_priority_skills.py")
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


def connection(client, o, origin, monkeypatch, handler):
    monkeypatch.setitem(HANDLERS, handler, {**HANDLERS[handler], "base_url": origin})
    provider = template(handler)
    response = client.post("/api/v1/integrations", headers=o["users"]["admin"]["headers"], json=provider["connection"])
    assert response.status_code == 201, response.text
    conn = response.json()
    tool = register(client, o, conn, provider["operations"][0])
    return conn, tool


def test_priority_activation_requires_evidence_then_publishes_exact_version_and_reuses_cache(
    client, office, rest_fixture, monkeypatch
):
    origin, calls = rest_fixture
    conn, tool = connection(client, office, origin, monkeypatch, "open_meteo.forecast")
    with SessionLocal() as db:
        actor = principal_for(db, office["users"]["admin"]["id"])
    result = asyncio.run(activation.finish_provider(actor, "open_meteo", conn["id"], office["plot"]["id"]))
    assert result["status"] == "ENABLED" and result["runtime_verified"] and result["runtime_cache_hit"]
    assert result["classification"] == "fixture" and len(calls) == 1
    with SessionLocal() as db:
        assert db.get(Integration, conn["id"]).enabled
        assert db.get(RegisteredTool, tool["id"]).enabled_version == 2
        assert db.scalar(select(func.count()).select_from(DefinitionApproval)) == 1
    again = asyncio.run(activation.finish_provider(actor, "open_meteo", conn["id"], office["plot"]["id"]))
    assert again["status"] == "ALREADY_ACTIVE" and len(calls) == 1


def test_failed_priority_authentication_never_grants_approval_or_enablement(client, office, rest_fixture, monkeypatch):
    origin, calls = rest_fixture
    conn, tool = connection(client, office, origin, monkeypatch, "isda.soil_profile")
    with SessionLocal() as db:
        actor = principal_for(db, office["users"]["admin"]["id"])
    result = asyncio.run(activation.finish_provider(actor, "isda_soil", conn["id"], office["plot"]["id"]))
    assert result["status"] == "NOT_ENABLED" and result["execution_outcome"] == "AUTH_REQUIRED"
    assert not calls
    with SessionLocal() as db:
        assert not db.get(Integration, conn["id"]).enabled and not db.get(RegisteredTool, tool["id"]).enabled
        assert db.scalar(select(func.count()).select_from(DefinitionApproval)) == 0
