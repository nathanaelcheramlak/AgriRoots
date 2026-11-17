"""Real registry installation and encrypted attachment; no upstream requests or fake approval."""

# ruff: noqa: F401, F811 -- pytest fixture imported by name
import importlib.util
import json
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import select, func

from tests.test_workspace import office
from src.config.settings import get_settings
from src.db.models.connectors import (
    Integration,
    RegisteredSkill,
    ConnectionCredential,
    DefinitionApproval,
    InvocationAttempt,
    RegisteredTool,
)
from src.db.models.workspace import Administrator
from src.db.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("provided_api_registration", ROOT / "scripts/register_api_skills.py")
registration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registration)


def configure(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "secret_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(
        settings, "outbound_allowed_hosts", [*settings.outbound_allowed_hosts, "data.apps.fao.org", "crop.kindwise.com"]
    )


def manifest():
    return json.loads((ROOT / "config/skills/provided_agri_apis.v1.json").read_text(encoding="utf-8"))


def test_provided_pack_registration_is_scoped_disabled_secret_safe_and_idempotent(client, office, monkeypatch):
    configure(monkeypatch)
    credentials = {
        "isda_soil": {
            "value": {"username": "fixture@example.invalid", "password": "explicit-fixture-password"},
            "principal_scope": "fixture-soil-account",
        },
        "kindwise": {"value": "explicit-fixture-crop-health-key", "principal_scope": "fixture-crop-account"},
    }
    request = {"manifest": manifest(), "principal_id": office["users"]["admin"]["id"], "credentials": credentials}
    first = registration.register(request)
    second = registration.register(request)
    assert first["pack_id"] == second["pack_id"]
    assert len(first["connections"]) == 9 and len(first["skills"]) == 8 and first["tool_count"] == 6
    assert all(not row["enabled"] for row in first["connections"] + first["skills"])
    assert all(not row["approved"] for row in first["skills"])
    assert {row["provider_id"] for row in first["connections"] if row["credential_stored"]} == {"isda_soil", "kindwise"}
    assert not any(row["credential_changed"] for row in second["connections"])
    assert "explicit-fixture-password" not in json.dumps(
        first
    ) and "explicit-fixture-crop-health-key" not in json.dumps(first)
    with SessionLocal() as db:
        for model, count in [
            (Integration, 9),
            (RegisteredSkill, 8),
            (RegisteredTool, 6),
            (ConnectionCredential, 2),
            (DefinitionApproval, 0),
            (InvocationAttempt, 0),
        ]:
            assert db.scalar(select(func.count()).select_from(model)) == count
        assert all(
            row.office_id == office["id"] and row.revision == 1 for row in db.scalars(select(ConnectionCredential))
        )


def test_empty_local_bootstrap_grants_no_global_administrator_and_installs_only_drafts(client, monkeypatch):
    configure(monkeypatch)
    report = registration.register({"manifest": manifest(), "bootstrap_empty_local": True})
    assert report["local_workspace_created"] and report["provider_requests"] == 0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Administrator)) == 0
        assert all(not row.enabled for row in db.scalars(select(RegisteredSkill)))
