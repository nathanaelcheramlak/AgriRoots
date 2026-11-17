"""Authenticated version/availability projection uses real registry policy only."""
# ruff: noqa: F401,F811 -- pytest fixture imports
from src.db.models.connectors import RegisteredSkill
from src.db.models.workspace import Membership, Office
from src.db.session import SessionLocal
from src.skills.service import SkillService
from src.tools.policy import principal_for
from tests.home_fixture import prepare_home
from tests.test_connectors_rest import rest_fixture
from tests.test_workspace import office


def test_catalog_execution_projection_keeps_active_version_and_draft_separate(client, office, rest_fixture, monkeypatch):
    origin, calls = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    with SessionLocal() as db:
        service = SkillService(db, principal_for(db, office["users"]["admin"]["id"]))
        row, version = service.version(skill["id"])
        service.create_skill({**version.manifest, "description": "New unapproved draft", "required_capabilities": ["missing.draft_only"]}, expected_revision=row.revision)
    before = len(calls)
    result = client.get(f"/api/v1/skills/{skill['id']}?include_execution=true", headers=office["headers"])
    assert result.status_code == 200
    view = result.json()
    assert view["version"] == 2 and not view["approved"] and view["enabled_version"] == 1
    e = view["execution"]
    assert e["available"] and e["approved"] and e["version"] == 1
    assert e["manifest"]["required_capabilities"] == ["weather.forecast", "soil.profile"]
    assert len(e["tools"]) == 2 and all(t["input_schema"]["properties"] == {} for t in e["tools"])
    assert all(set(t["source"]) == {"name", "host"} for t in e["tools"])
    assert "credential" not in result.text and "http://" not in result.text
    assert len(calls) == before  # Browsing never probes a provider.
    default = client.get(f"/api/v1/skills/{skill['id']}", headers=office["headers"]).json()
    assert "execution" not in default
    with SessionLocal() as db:
        row = db.get(RegisteredSkill, skill["id"]); row.enabled = False; db.commit()
    assert not client.get(f"/api/v1/skills/{skill['id']}?include_execution=true", headers=office["headers"]).json()["execution"]["available"]


def test_skill_catalog_is_office_scoped_and_viewer_execution_is_blocked(client, office, rest_fixture, monkeypatch):
    origin, _ = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    assert client.get('/api/v1/skills?include_execution=true').status_code == 401
    with SessionLocal() as db:
        other = Office(name="Other isolated fixture office")
        db.add(other); db.flush()
        db.add(Membership(user_id=office["users"]["outsider"]["id"], office_id=other.id, role="officer"))
        db.commit()
    other_headers = office["users"]["outsider"]["headers"]
    assert client.get('/api/v1/skills?include_execution=true', headers=other_headers).json()["items"] == []
    assert client.get(f"/api/v1/skills/{skill['id']}?include_execution=true", headers=other_headers).status_code == 404
    with SessionLocal() as db:
        member = db.query(Membership).filter_by(user_id=office["users"]["officer"]["id"]).one()
        member.role = "viewer"; db.commit()
    e = client.get(f"/api/v1/skills/{skill['id']}?include_execution=true", headers=office["headers"]).json()["execution"]
    assert not e["available"] and e["blocked_code"] == "POLICY_DENIED"


def test_draft_dependency_explanation_does_not_create_tools_or_claim_availability(client, office):
    payload = {"name": "missing_evidence_fixture", "description": "Missing evidence fixture", "instructions": "Only use required approved evidence.", "required_capabilities": ["field.observation_fixture"], "optional_capabilities": ["rainfall.fixture_optional"]}
    created = client.post('/api/v1/skills', headers=office["users"]["admin"]["headers"], json=payload)
    assert created.status_code == 201
    e = client.get(f"/api/v1/skills/{created.json()['id']}?include_execution=true", headers=office["headers"]).json()["execution"]
    assert not e["available"] and not e["approved"]
    assert e["dependencies"] == [{"capability": "field.observation_fixture", "required": True, "available": False}, {"capability": "rainfall.fixture_optional", "required": False, "available": False}]
    assert e["tools"] == []
