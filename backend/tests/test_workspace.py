from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from fastapi.testclient import TestClient

from src.auth.jwt_utils import create_access_token
from src.db.base import Base
from src.db.models.user import User, UserProfile
from src.db.models.workspace import Administrator, Membership, WorkspaceEvent
from src.db.schema_migrations import migrate
from src.db.session import SessionLocal
from src.main import app


@pytest.fixture
def office(client):
    users = {}
    with SessionLocal() as db:
        for i, name in enumerate(["admin", "officer", "farmer", "other", "outsider"]):
            user_id = str(uuid4())
            db.add(User(user_id=user_id, phone_number=f"+25190000000{i}", password_hash="test-only"))
            db.add(UserProfile(user_id=user_id, full_name=f"Synthetic {name}"))
            users[name] = {"id": user_id, "headers": {"Authorization": f"Bearer {create_access_token(user_id)}"}}
        db.flush()
        db.add(Administrator(user_id=users["admin"]["id"]))
        db.commit()
    response = client.post("/api/workspace/offices", json={"name": "Synthetic demonstration office"}, headers=users["admin"]["headers"])
    assert response.status_code == 201, response.text
    office_id = response.json()["id"]
    prefix = f"/api/workspace/offices/{office_id}"
    for name, role in [("officer", "officer"), ("farmer", "farmer"), ("other", "farmer")]:
        r = client.post(prefix + "/members", json={"user_id": users[name]["id"], "role": role}, headers=users["admin"]["headers"])
        assert r.status_code == 201, r.text
    headers = users["officer"]["headers"]

    def record(kind, data):
        r = client.post(prefix + "/records", json={"kind": kind, "data": data}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()

    cluster = record("cluster", {"name": "Synthetic cluster A", "assigned_officer_id": users["officer"]["id"], "synthetic": True})
    household = record("household", {"name": "Synthetic household A", "farmer_user_id": users["farmer"]["id"],
        "cluster_id": cluster["id"], "assigned_officer_id": users["officer"]["id"], "synthetic": True})
    plot = record("plot", {"name": "Synthetic plot A", "household_id": household["id"], "latitude": 9.03,
        "longitude": 38.74, "area": 1, "area_unit": "ha", "agroclimatic_zone": "Demonstration zone"})
    evidence = record("evidence", {"source_name": "Synthetic observation", "source_reference": "internal:synthetic-weather-1",
        "observed_at": "2026-10-14T08:00:00Z", "retrieved_at": "2026-10-15T08:00:00Z",
        "valid_from": "2026-10-14T08:00:00Z", "valid_until": "2026-10-20T08:00:00Z",
        "location": "Synthetic plot A", "crop": "maize", "units": "mm", "values": {"rain": 20},
        "snapshot": "Synthetic rainfall observation, for demonstrations only", "classification": "synthetic", "plot_id": plot["id"]})
    draft = {"title": "Synthetic drainage advisory", "household_ids": [household["id"]], "plot_ids": [plot["id"]],
        "assigned_officer_id": users["officer"]["id"], "language": "en", "recommendations": [
            {"action": "Inspect drainage before the demonstration rain event.", "evidence_ids": [evidence["id"]],
             "uncertainty": "Synthetic example; not operational farming advice."}], "missing_information": "Field inspection pending",
        "translations": {"am": ["ለማሳያ ብቻ።"]}}
    return {"users": users, "id": office_id, "prefix": prefix, "headers": headers, "record": record,
            "cluster": cluster, "household": household, "plot": plot, "evidence": evidence, "draft": draft}


def create(client, o, draft=None):
    r = client.post(o["prefix"] + "/advisories", json=draft or o["draft"], headers=o["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def transition(client, o, v, action, expected=200, **kwargs):
    r = client.post(o["prefix"] + f'/advisories/{v["advisory_id"]}/transition',
        json={"action": action, "expected_version": v["version"], **kwargs}, headers=o["headers"])
    assert r.status_code == expected, r.text
    return r.json()


def test_review_approval_release_and_exact_audio(client, office, monkeypatch):
    o = office
    v = create(client, o)
    farmer = o["users"]["farmer"]["headers"]
    assert client.get("/api/workspace/released", headers=farmer).json() == []
    assert client.get(f'/api/workspace/released/{v["id"]}', headers=farmer).status_code == 404
    transition(client, o, v, "release", 409)
    transition(client, o, v, "submit")
    transition(client, o, v, "approve")
    assert client.get("/api/workspace/released", headers=farmer).json() == []
    assert client.post(f'/api/workspace/released/{v["id"]}/audio', headers=farmer).status_code == 404
    transition(client, o, v, "release")
    transition(client, o, v, "release")
    published = client.get("/api/workspace/released", headers=farmer).json()
    assert len(published) == 1 and published[0]["version"] == 1
    assert "recipient_user_ids" not in published[0]
    for name in ("other", "outsider", "officer"):
        assert client.get("/api/workspace/released", headers=o["users"][name]["headers"]).json() == []
        assert client.get(f'/api/workspace/released/{v["id"]}', headers=o["users"][name]["headers"]).status_code == 404
    spoken = []
    monkeypatch.setattr("src.api.routes.workspace.synthesize_speech", lambda text, language_code: spoken.append((text, language_code)) or b"audio")
    audio = client.post(f'/api/workspace/released/{v["id"]}/audio', headers=farmer)
    assert audio.content == b"audio"
    assert spoken[0][0] == o["draft"]["recommendations"][0]["action"] + "\n" + o["draft"]["recommendations"][0]["uncertainty"] + "\nField inspection pending"
    assert client.post(f'/api/workspace/released/{v["id"]}/audio?language=am', headers=farmer).content == b"audio"
    assert spoken[-1] == ("ለማሳያ ብቻ።", "am")
    assert client.post(f'/api/workspace/released/{v["id"]}/audio?language=fr', headers=farmer).status_code == 422
    events = client.get(o["prefix"] + "/events", params={"entity_id": v["advisory_id"]}, headers=o["headers"]).json()
    assert [e["action"] for e in events if not e["action"].startswith("audio_")] == ["created", "submit", "approve", "release"]
    audio_events = [e for e in events if e["action"] == "audio_generated"]
    assert len(audio_events) == 2
    assert all(e["actor_id"] == o["users"]["farmer"]["id"] and e["details"]["version_id"] == v["id"] for e in audio_events)
    assert events[2]["actor_id"] == o["users"]["officer"]["id"]
    assert events[2]["details"]["version_id"] == v["id"]


def test_new_version_invalidates_approval_and_preserves_history(client, office):
    o = office; v = create(client, o)
    transition(client, o, v, "submit"); transition(client, o, v, "approve")
    changed = deepcopy(o["draft"]); changed["recommendations"][0]["action"] = "Corrected synthetic advice"
    response = client.put(o["prefix"] + f'/advisories/{v["advisory_id"]}', json={**changed, "expected_version": 1}, headers=o["headers"])
    assert response.status_code == 200, response.text
    v2 = response.json()
    assert v2["version"] == 2 and v2["status"] == "draft"
    transition(client, o, v, "release", 409); transition(client, o, v2, "release", 409)
    transition(client, o, v2, "submit"); transition(client, o, v2, "approve"); transition(client, o, v2, "release")
    v3 = client.put(o["prefix"] + f'/advisories/{v["advisory_id"]}', json={**o["draft"], "expected_version": 2}, headers=o["headers"]).json()
    assert v3["status"] == "draft"
    published = client.get("/api/workspace/released", headers=o["users"]["farmer"]["headers"]).json()
    assert [p["version"] for p in published] == [2]
    versions = client.get(o["prefix"] + "/advisories", headers=o["headers"]).json()
    assert len(versions) == 3
    assert next(x for x in versions if x["version"] == 1)["content"] == v["content"]
    assert client.put(o["prefix"] + f'/advisories/{v["advisory_id"]}', json={**o["draft"], "expected_version": 1}, headers=o["headers"]).status_code == 409


def test_scope_and_privilege_escalation(client, office):
    o = office
    for name in ("farmer", "outsider"):
        h = o["users"][name]["headers"]
        assert client.get(o["prefix"] + "/records", headers=h).status_code == 403
        assert client.get(o["prefix"] + "/advisories", headers=h).status_code == 403
        assert client.post(o["prefix"] + "/members", json={"user_id": o["users"][name]["id"], "role": "officer"}, headers=h).status_code == 403
        assert client.post("/api/workspace/offices", json={"name": "Unauthorized office"}, headers=h).status_code == 403
    assert client.post(o["prefix"] + "/members", json={"user_id": o["users"]["officer"]["id"], "role": "administrator"}, headers=o["headers"]).status_code == 403
    assert client.post(o["prefix"] + "/advisories", json=o["draft"], headers=o["users"]["farmer"]["headers"]).status_code == 403
    draft = create(client, o)
    assert client.post(o["prefix"] + f'/advisories/{draft["advisory_id"]}/transition', json={"action": "approve", "expected_version": 1}, headers=o["users"]["farmer"]["headers"]).status_code == 403
    admin_h = o["users"]["admin"]["headers"]
    other_office = client.post("/api/workspace/offices", json={"name": "Other office"}, headers=admin_h).json()["id"]
    assert client.post(f"/api/workspace/offices/{other_office}/members", json={"user_id": o["users"]["outsider"]["id"], "role": "officer"}, headers=admin_h).status_code == 201
    other_h = o["users"]["outsider"]["headers"]
    for suffix in ("/records", "/advisories", "/events", "/members"):
        assert client.get(o["prefix"] + suffix, headers=other_h).status_code == 403
        assert client.get(f"/api/workspace/offices/{other_office}" + suffix, headers=o["headers"]).status_code == 403
    # Office access does not authorize reusing another office's records.
    assert client.post(f"/api/workspace/offices/{other_office}/records", json={"kind": "plot", "data": o["plot"]["data"]}, headers=other_h).status_code == 404
    spoof = {**o["draft"], "assigned_officer_id": o["users"]["outsider"]["id"]}
    assert client.post(o["prefix"] + "/advisories", json=spoof, headers=o["headers"]).status_code == 422
    # The editable profile type never grants office privileges.
    assert client.patch("/api/users/me/profile", json={"user_type": "administrator"}, headers=o["users"]["farmer"]["headers"]).status_code == 422
    assert client.patch("/api/users/me/profile", json={"user_type": "experienced"}, headers=o["users"]["farmer"]["headers"]).status_code == 200
    assert client.get(o["prefix"] + "/records", headers=o["users"]["farmer"]["headers"]).status_code == 403
    assert client.get("/api/workspace/me").status_code == 401


def test_unsourced_and_invalid_records_are_blocked(client, office):
    o = office
    draft = deepcopy(o["draft"]); draft["recommendations"][0]["evidence_ids"] = []
    v = create(client, o, draft); transition(client, o, v, "submit", 422)
    # Approval repeats validation even if a malformed draft somehow reaches review.
    from src.db.models.workspace import AdvisoryVersion
    with SessionLocal() as db:
        row = db.get(AdvisoryVersion, v["id"]); row.status = "pending_review"; db.commit()
    transition(client, o, v, "approve", 422)
    draft["recommendations"][0]["evidence_ids"] = [str(uuid4())]
    assert client.post(o["prefix"] + "/advisories", json=draft, headers=o["headers"]).status_code == 404
    for field, value in [("latitude", 91), ("longitude", -181), ("area", 0), ("area_unit", "acres")]:
        assert client.post(o["prefix"] + "/records", json={"kind": "plot", "data": {**o["plot"]["data"], field: value}}, headers=o["headers"]).status_code == 422
    season = {"plot_id": o["plot"]["id"], "crop": "maize", "planting_date": "2026-05-01", "harvest_date": "2026-10-01", "previous_yield": 0, "yield_unit": "kg/ha"}
    assert o["record"]("season", season)["data"]["previous_yield"] == 0
    assert o["record"]("season", {**season, "previous_yield": None, "yield_unit": None})["data"]["previous_yield"] is None
    for bad in [{"harvest_date": "2026-01-01"}, {"previous_yield": -1}, {"yield_unit": None}]:
        assert client.post(o["prefix"] + "/records", json={"kind": "season", "data": {**season, **bad}}, headers=o["headers"]).status_code == 422
    assert client.put(o["prefix"] + f'/records/{o["evidence"]["id"]}', json={"kind": "evidence", "data": o["evidence"]["data"], "expected_revision": 1}, headers=o["headers"]).status_code == 409


def test_reject_cancel_replace_and_record_audits(client, office):
    o = office; v = create(client, o)
    transition(client, o, v, "submit"); transition(client, o, v, "reject", 422)
    transition(client, o, v, "reject", reason="Needs field inspection")
    transition(client, o, v, "approve", 409)
    transition(client, o, v, "submit"); transition(client, o, v, "cancel", reason="Season ended")
    transition(client, o, v, "submit", 409)
    v2 = create(client, o)
    transition(client, o, v2, "submit"); transition(client, o, v2, "approve"); transition(client, o, v2, "release")
    replacement = create(client, o, {**o["draft"], "replaces_advisory_id": v2["advisory_id"]})
    assert replacement["content"]["replaces_advisory_id"] == v2["advisory_id"]
    url = o["prefix"] + f'/records/{o["plot"]["id"]}'
    updated = {"kind": "plot", "data": {**o["plot"]["data"], "area": 2}, "expected_revision": 1}
    assert client.put(url, json=updated, headers=o["headers"]).status_code == 200
    assert client.put(url, json=updated, headers=o["headers"]).status_code == 409
    events = client.get(o["prefix"] + "/events", params={"entity_id": o["plot"]["id"]}, headers=o["headers"]).json()
    assert events[-1]["details"]["before"]["area"] == 1
    assert events[-1]["details"]["after"]["area"] == 2
    assert client.post("/api/debug/reset-all-data", headers={"x-debug-token": "test-debug-token"}).status_code == 409


def test_concurrent_release_publishes_once(client, office):
    o = office; v = create(client, o)
    transition(client, o, v, "submit"); transition(client, o, v, "approve")
    def publish(_):
        with TestClient(app) as concurrent:
            return concurrent.post(o["prefix"] + f'/advisories/{v["advisory_id"]}/transition',
                json={"action": "release", "expected_version": 1}, headers=o["headers"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(publish, range(8)))
    assert [r.status_code for r in results] == [200] * 8
    with SessionLocal() as db:
        releases = list(db.scalars(select(WorkspaceEvent).where(WorkspaceEvent.entity_id == v["advisory_id"], WorkspaceEvent.action == "release")))
        assert len(releases) == 1
    assert len(client.get("/api/workspace/released", headers=o["users"]["farmer"]["headers"]).json()) == 1


def test_migrations_fresh_and_legacy_copy(tmp_path):
    from src.db.session import engine as configured_engine
    from sqlalchemy.schema import CreateSchema, DropSchema
    schemas = []
    targets = [(create_engine(f'sqlite:///{tmp_path / ("legacy.db" if legacy else "fresh.db")}'), legacy)
               for legacy in (False, True)]
    if configured_engine.dialect.name == "postgresql":
        for legacy in (False, True):
            name = "migration_" + uuid4().hex
            with configured_engine.begin() as conn: conn.execute(CreateSchema(name))
            schemas.append(name)
            targets.append((create_engine(configured_engine.url, connect_args={"options": f"-csearch_path={name}"}), legacy))
    for engine, legacy in targets:
        if legacy:
            # Reconstruct the legacy schema and copy a real-format row into it.
            from src.db.migrations.v001_legacy import TABLES
            Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in TABLES])
            with engine.begin() as conn:
                for name in ("content_type", "message_content_english", "media_url", "language_used"):
                    conn.execute(text(f"ALTER TABLE chat_messages DROP COLUMN {name}"))
                conn.execute(text("INSERT INTO users (user_id, phone_number, password_hash, is_active, created_at, updated_at) VALUES ('legacy-user', '+251999999999', 'hash', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        migrate(engine); migrate(engine)
        assert "advisory_versions" in inspect(engine).get_table_names()
        assert "language_used" in {c["name"] for c in inspect(engine).get_columns("chat_messages")}
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version FROM schema_revisions ORDER BY version")).scalars().all() == [1, 2, 3]
            if legacy:
                assert conn.execute(text("SELECT phone_number FROM users WHERE user_id='legacy-user'")).scalar() == "+251999999999"
        engine.dispose()
    for name in schemas:
        with configured_engine.begin() as conn: conn.execute(DropSchema(name, cascade=True))


def test_chat_education_requests_and_legacy_history(client, office):
    from src.db.models.chat import ChatMessage
    o = office; farmer = o["users"]["farmer"]["headers"]
    session = client.post("/api/chat/sessions", json={"title": "Synthetic request"}, headers=farmer).json()["session_id"]
    url = f"/api/chat/sessions/{session}/messages"
    education = client.post(url, data={"message": "What is compost?"}, headers=farmer).json()
    assert education["chosen_route"] == "education"
    assert "decomposed organic material" in education["assistant_message"]["content"]
    request = client.post(url, data={"message": "What should I plant on my plot?"}, headers=farmer).json()
    assert request["chosen_route"] == "officer_review_required"
    assert "review queue" in request["assistant_message"]["content"]
    queued = client.get(o["prefix"] + "/records?kind=request", headers=o["headers"]).json()
    assert len(queued) == 1 and queued[0]["data"]["farmer_user_id"] == o["users"]["farmer"]["id"]
    with SessionLocal() as db:
        db.add(ChatMessage(session_id=session, sender="assistant", content="UNAPPROVED LEGACY ADVICE",
            content_type="text", message_content_english="UNAPPROVED ENGLISH", sequence_no=5))
        db.commit()
    messages = client.get(url, headers=farmer).json()
    assert "UNAPPROVED" not in str(messages)
    assert "requires officer review" in messages[-1]["content"]


def test_controlled_initial_administrator_provisioning(client):
    from src.cli.provision_admin import provision
    user_id = str(uuid4())
    with SessionLocal() as db:
        db.add(User(user_id=user_id, phone_number="+251911111111", password_hash="test-only"))
        db.commit()
    provision(user_id)
    with SessionLocal() as db:
        assert db.get(Administrator, user_id)
        assert db.scalar(select(WorkspaceEvent).where(WorkspaceEvent.action == "administrator_provisioned"))
    with pytest.raises(SystemExit, match="already provisioned"):
        provision(user_id)


def test_synthetic_seed_is_usable_and_refuses_existing_data(tmp_path):
    import os
    import subprocess
    import sys
    target = tmp_path / "synthetic.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{target}"}
    result = subprocess.run([sys.executable, "-m", "src.cli.seed_synthetic"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    login_check = subprocess.run([sys.executable, "-c", """
from fastapi.testclient import TestClient
from src.main import app
with TestClient(app) as client:
    for phone in ('+251900000001', '+251900000002', '+251900000003'):
        result = client.post('/api/auth/login', json={'phone_number': phone, 'password': 'SyntheticDemo123!'})
        assert result.status_code == 200, result.text
        assert result.json()['user']['onboarding_completed']
"""], env=env, capture_output=True, text=True)
    assert login_check.returncode == 0, login_check.stderr
    seeded = create_engine(f"sqlite:///{target}")
    with seeded.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar() == 3
        assert conn.execute(text("SELECT COUNT(*) FROM workspace_records")).scalar() == 5
        assert conn.execute(text("SELECT COUNT(*) FROM workspace_administrators")).scalar() == 1
    again = subprocess.run([sys.executable, "-m", "src.cli.seed_synthetic"], env=env, capture_output=True, text=True)
    assert again.returncode != 0 and "empty database" in again.stderr
    seeded.dispose()


def test_amharic_education_uses_fixed_catalogue(client, office):
    farmer = office["users"]["farmer"]["headers"]
    session = client.post("/api/chat/sessions", json={}, headers=farmer).json()["session_id"]
    response = client.post(f"/api/chat/sessions/{session}/messages", data={"message": "ኮምፖስት ምንድን ነው?", "language_code": "am"}, headers=farmer)
    assert response.status_code == 200
    body = response.json()
    assert body["chosen_route"] == "education"
    assert "የበሰበሰ ኦርጋኒክ ቁስ" in body["assistant_message"]["content"]
    assert body["assistant_message"]["message_content_english"] is None


def test_release_rolls_back_if_auditing_fails(client, office, monkeypatch):
    from src.services.workspace_service import WorkspaceService
    o = office; v = create(client, o)
    transition(client, o, v, "submit"); transition(client, o, v, "approve")
    event = WorkspaceService.event
    def fail_release_audit(self, office_id, entity_id, action, **details):
        if action == "release":
            raise RuntimeError("Simulated audit storage failure")
        return event(self, office_id, entity_id, action, **details)
    monkeypatch.setattr(WorkspaceService, "event", fail_release_audit)
    with pytest.raises(RuntimeError, match="audit storage failure"):
        transition(client, o, v, "release")
    assert client.get("/api/workspace/released", headers=o["users"]["farmer"]["headers"]).json() == []
    monkeypatch.setattr(WorkspaceService, "event", event)
    transition(client, o, v, "release")
    events = client.get(o["prefix"] + "/events", params={"entity_id": v["advisory_id"]}, headers=o["headers"]).json()
    assert len([e for e in events if e["action"] == "release"]) == 1
