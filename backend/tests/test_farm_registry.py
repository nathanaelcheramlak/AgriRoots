"""Actual authenticated registry API and existing executor, with explicitly labelled fixtures."""
# ruff: noqa: F401,F811 -- pytest discovers imported fixtures by name

import asyncio
import json
from datetime import UTC
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from src.config.settings import get_settings
from src.db.models.farm_registry import Farmer
from src.db.session import SessionLocal, engine
from src.integrations.contracts import ConnectorError
from src.integrations.jobs import process_job
from src.registry.geometry import validate_geometry
from src.tools.policy import authorized_plots, principal_for
from tests.home_fixture import HomeModelFixture, prepare_home
from tests.test_connectors_rest import rest_fixture
from tests.test_workspace import office


def rectangle(w=38.6, s=8.8, e=38.7, n=8.9):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def setup_registry(client, office, monkeypatch, *, synthetic=False):
    monkeypatch.setattr(get_settings(), "secret_encryption_key", Fernet.generate_key().decode())
    h = office["users"]["admin"]["headers"]
    r = client.post(
        "/api/v1/registry/territory-proposals", headers=h, json={"name": "Test territory", "boundary": rectangle()}
    )
    assert r.status_code == 201, r.text
    territory = r.json()
    r = client.post(
        f"/api/v1/registry/territories/{territory['id']}/review",
        headers=h,
        json={"decision": "approve", "expected_revision": 1},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/registry/territories/{territory['id']}/assignments",
        headers=h,
        json={"user_id": office["users"]["officer"]["id"]},
    )
    assert r.status_code == 201, r.text
    assignment = r.json()
    r = client.post(
        "/api/v1/registry/farmers",
        headers=h,
        json={
            "territory_id": territory["id"],
            "reference": "DEMO-001" if synthetic else "FARM-001",
            "display_name": "Test Farmer 001",
            "phone": "+251911123456",
            "notes": "Private sensitive notes",
            "synthetic": synthetic,
        },
    )
    assert r.status_code == 201, r.text
    farmer = r.json()
    payload = {
        "name": "Test registered plot",
        "geometry": rectangle(38.61, 8.81, 38.611, 8.811),
        "farmer_ids": [farmer["id"]],
        "synthetic": synthetic,
        "request_key": uuid4().hex,
        "season": {"crop": "Maize", "planting_date": None},
    }
    r = client.post(f"/api/v1/registry/territories/{territory['id']}/plots", headers=h, json=payload)
    assert r.status_code == 201, r.text
    return territory, assignment, farmer, r.json(), payload


def test_registry_persists_and_assignment_revocation_protects_all_reads(client, office, monkeypatch):
    territory, assignment, farmer, plot, payload = setup_registry(client, office, monkeypatch)
    h, admin = office["headers"], office["users"]["admin"]["headers"]
    assert client.get("/api/v1/registry/territories", headers=h).json()["items"][0]["id"] == territory["id"]
    detail = client.get("/api/v1/registry/plots/" + plot["id"], headers=h)
    assert detail.status_code == 200 and detail.json()["farmers"][0]["id"] == farmer["id"]
    assert "Private sensitive notes" not in detail.text and "+251911123456" not in detail.text
    assert (
        client.get("/api/v1/registry/farmers/" + farmer["id"] + "?include_private=true", headers=h).status_code == 403
    )
    assert (
        client.get("/api/v1/registry/farmers/" + farmer["id"] + "?include_private=true", headers=admin).json()[
            "private"
        ]["phone"]
        == "+251911123456"
    )
    with SessionLocal() as db:
        row = db.get(Farmer, farmer["id"])
        assert "+251911123456" not in row.private_ciphertext and "Private sensitive notes" not in row.private_ciphertext
        resolved = authorized_plots(db, principal_for(db, office["users"]["officer"]["id"]), [plot["id"]])[0]
        assert resolved["farm_context"]["crop_season"]["crop"] == "Maize" and not resolved["synthetic"]
        assert "Test Farmer" not in json.dumps(resolved)
    assert (
        client.post(f"/api/v1/registry/territories/{territory['id']}/plots", headers=admin, json=payload).json()["id"]
        == plot["id"]
    )
    page = client.get("/api/v1/registry/plots?bbox=38.60,8.80,38.62,8.82", headers=h)
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 1
    assert client.get("/api/v1/registry/plots?bbox=38.65,8.85,38.66,8.86", headers=h).json()["total"] == 0
    r = client.delete("/api/v1/registry/assignments/" + assignment["id"] + "?expected_revision=1", headers=admin)
    assert r.status_code == 200
    assert client.get("/api/v1/registry/plots/" + plot["id"], headers=h).status_code == 403
    assert client.get("/api/v1/registry/farmers/" + farmer["id"], headers=h).status_code == 403
    assert plot["id"] not in [p["id"] for p in client.get("/api/v1/companion/context", headers=h).json()["plots"]]
    assert plot["id"] not in [
        p["id"] for p in client.get(f"/api/workspace/offices/{office['id']}/records?kind=plot", headers=h).json()
    ]


def test_proposals_and_foreign_offices_do_not_grant_plot_access(client, office, monkeypatch):
    t, _, _farmer, p, payload = setup_registry(client, office, monkeypatch)
    outsider = office["users"]["outsider"]["headers"]
    assert client.get("/api/v1/registry/plots/" + p["id"], headers=outsider).status_code == 403
    h = office["headers"]
    proposal = client.post(
        "/api/v1/registry/territory-proposals", headers=h, json={"name": "Unapproved", "boundary": rectangle()}
    ).json()
    assert (
        client.post(f"/api/v1/registry/territories/{proposal['id']}/plots", headers=h, json=payload).status_code == 403
    )
    assert (
        client.post(
            f"/api/v1/registry/territories/{proposal['id']}/review",
            headers=h,
            json={"decision": "approve", "expected_revision": 1},
        ).status_code
        == 403
    )
    outside = {**payload, "request_key": uuid4().hex, "geometry": rectangle(38.69, 8.89, 38.71, 8.91)}
    assert client.post(f"/api/v1/registry/territories/{t['id']}/plots", headers=h, json=outside).status_code == 422
    assert (
        client.post(
            "/api/v1/registry/farmers",
            headers=h,
            json={"territory_id": t["id"], "display_name": "Test", "reference": "X", "synthetic": True},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "geometry",
    [
        rectangle(e=200),
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
        {"type": "Polygon", "coordinates": [[[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 0, 1]]]},
    ],
)
def test_invalid_geometry_is_rejected(geometry):
    with pytest.raises(ConnectorError):
        validate_geometry(geometry)


def test_registered_plot_uses_existing_durable_langgraph_and_evidence(
    client, office, monkeypatch, rest_fixture, tmp_path
):
    _territory, assignment, _farmer, plot, _ = setup_registry(client, office, monkeypatch, synthetic=True)
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    origin, _calls = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    r = client.post(
        f"/api/v1/skills/{skill['id']}/runs",
        headers=office["headers"],
        json={
            "task": "Inspect this registered farm's weather and soil",
            "plot_ids": [plot["id"]],
            "request_key": uuid4().hex,
            "authorize_network": True,
            "authorize_model": True,
        },
    )
    assert r.status_code == 202, r.text
    job = r.json()
    assert asyncio.run(process_job(job["id"], model=HomeModelFixture()))
    completed = client.get(job["status_url"], headers=office["headers"]).json()
    assert completed["status"] == "succeeded", completed
    assert len(completed["result"]["evidence_ids"]) == 2
    assert (
        client.get(f"/api/v1/registry/plots/{plot['id']}/investigations", headers=office["headers"]).json()["total"]
        == 1
    )
    with SessionLocal() as db:
        from src.db.models.farm_registry import PlotRun

        db.delete(db.get(PlotRun, (plot["id"], job["id"])))
        db.commit()
    assert (
        client.get(f"/api/v1/registry/plots/{plot['id']}/investigations", headers=office["headers"]).json()["total"]
        == 1
    )
    for ident in completed["result"]["evidence_ids"]:
        assert (
            client.get("/api/v1/evidence/" + ident, headers=office["headers"]).json()["data"]["classification"]
            == "fixture"
        )
    client.delete(
        "/api/v1/registry/assignments/" + assignment["id"] + "?expected_revision=1",
        headers=office["users"]["admin"]["headers"],
    )
    assert client.get(job["status_url"], headers=office["headers"]).status_code == 403
    for ident in completed["result"]["evidence_ids"]:
        assert client.get("/api/v1/evidence/" + ident, headers=office["headers"]).status_code == 403


def test_postgis_native_geometry_indexes_and_area(client, office, monkeypatch):
    if engine.dialect.name != "postgresql":
        pytest.skip("Requires actual PostGIS")
    _, _, _, plot, _ = setup_registry(client, office, monkeypatch)
    with engine.connect() as conn:
        srid, valid, size = conn.execute(
            text("SELECT ST_SRID(geom), ST_IsValid(geom), ST_Area(geom::geography) FROM registry_plots WHERE id=:id"),
            {"id": plot["id"]},
        ).one()
        assert srid == 4326 and valid and size > 100
        assert abs(size - plot["area_m2"]) < 0.01
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes WHERE tablename='registry_plots' AND indexdef LIKE '%USING gist%'"
                )
            )
            == 1
        )


def test_second_office_isolation_and_large_directory_paging(client, office, monkeypatch):
    from src.db.models.workspace import Membership, Office
    from src.integrations.secrets import encrypt

    t, _, farmer, plot, _ = setup_registry(client, office, monkeypatch)
    with SessionLocal() as db:
        second = Office(name="Second test office")
        db.add(second)
        db.flush()
        db.add(Membership(office_id=second.id, user_id=office["users"]["outsider"]["id"], role="officer"))
        private = encrypt({"phone": "+251911000000"})
        db.add_all(
            [
                Farmer(
                    office_id=office["id"],
                    territory_id=t["id"],
                    reference=f"DEMO-{i:05d}",
                    display_name=f"Test Farmer {i:05d}",
                    village="Test village",
                    private_ciphertext=private,
                    synthetic=True,
                    created_by=office["users"]["admin"]["id"],
                    profile={"language": "en", "channel": "none", "consent": "unknown"},
                )
                for i in range(2000)
            ]
        )
        db.commit()
    h = office["headers"]
    other = office["users"]["outsider"]["headers"]
    result = client.get("/api/v1/registry/farmers?limit=25&offset=25", headers=h)
    assert result.status_code == 200 and result.json()["total"] == 2001 and len(result.json()["items"]) == 25
    assert len(result.content) < 25000 and "+251911000000" not in result.text
    filtered = client.get("/api/v1/registry/farmers?search=DEMO-00001", headers=h).json()
    assert filtered["total"] == 1 and filtered["items"][0]["reference"] == "DEMO-00001"
    assert client.get("/api/v1/registry/farmers", headers=other).json()["total"] == 0
    assert client.get("/api/v1/registry/plots/" + plot["id"], headers=other).status_code == 404
    assert client.get("/api/v1/companion/context?plot_ids=" + plot["id"], headers=other).status_code == 403
    assert client.get("/api/v1/registry/farmers/" + farmer["id"], headers=other).status_code == 404


def test_revision_checks_and_private_notes_do_not_enter_model_context(client, office, monkeypatch):
    territory, _, _farmer, plot, payload = setup_registry(client, office, monkeypatch)
    admin = office["users"]["admin"]["headers"]
    edit = {
        **payload,
        "expected_revision": 1,
        "notes": "Private plot note: Test Farmer 001",
        "observation": "Unverified private observation",
    }
    r = client.patch("/api/v1/registry/plots/" + plot["id"], headers=admin, json=edit)
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == edit["notes"]
    assert client.patch("/api/v1/registry/plots/" + plot["id"], headers=admin, json=edit).status_code == 409
    listed = client.get("/api/v1/registry/plots", headers=office["headers"])
    assert edit["notes"] not in listed.text
    with SessionLocal() as db:
        from src.db.models.workspace import WorkspaceRecord

        stored = db.get(WorkspaceRecord, plot["id"])
        assert edit["notes"] not in json.dumps(stored.data)
        resolved = authorized_plots(db, principal_for(db, office["users"]["officer"]["id"]), [plot["id"]])
        assert edit["notes"] not in json.dumps(resolved) and "Test Farmer" not in json.dumps(resolved)
    smaller = {"name": territory["name"], "boundary": rectangle(38.65, 8.85, 38.69, 8.89), "expected_revision": 2}
    assert (
        client.patch("/api/v1/registry/territories/" + territory["id"], headers=admin, json=smaller).status_code == 409
    )


def test_reader_and_future_assignments_cannot_register_farms(client, office, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from src.db.models.farm_registry import TerritoryAssignment

    territory, assignment, _, plot, payload = setup_registry(client, office, monkeypatch)
    with SessionLocal() as db:
        row = db.get(TerritoryAssignment, assignment["id"])
        row.role = "reader"
        db.commit()
    assert client.get("/api/v1/registry/plots/" + plot["id"], headers=office["headers"]).status_code == 200
    assert (
        client.post(
            "/api/v1/registry/territories/" + territory["id"] + "/plots", headers=office["headers"], json=payload
        ).status_code
        == 403
    )
    with SessionLocal() as db:
        row = db.get(TerritoryAssignment, assignment["id"])
        row.starts_at = datetime.now(UTC) + timedelta(days=1)
        db.commit()
    assert client.get("/api/v1/registry/plots/" + plot["id"], headers=office["headers"]).status_code == 403


def test_real_farm_cloud_policy_blocks_before_any_model_request(client, office, rest_fixture, monkeypatch, tmp_path):
    _, _, _, plot, _ = setup_registry(client, office, monkeypatch)
    origin, _ = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    monkeypatch.setattr(get_settings(), "cloud_model_data_policy", "synthetic_only")
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))

    def forbidden_model():
        pytest.fail("Real-farm context must not reach a cloud model")

    monkeypatch.setattr("src.agent.companion.graph.model_provider", forbidden_model)
    r = client.post(
        f"/api/v1/skills/{skill['id']}/runs",
        headers=office["headers"],
        json={
            "task": "Inspect the registered farm weather",
            "plot_ids": [plot["id"]],
            "request_key": uuid4().hex,
            "authorize_network": True,
            "authorize_model": True,
        },
    )
    assert r.status_code == 202, r.text
    job = r.json()
    asyncio.run(process_job(job["id"]))
    result = client.get(job["status_url"], headers=office["headers"]).json()
    assert result["status"] == "failed" and result["error"]["code"] == "POLICY_DENIED"


def test_alembic_bridge_is_repeatable_and_preserves_legacy_identity(tmp_path, monkeypatch):
    from alembic.config import Config
    from sqlalchemy import create_engine

    from alembic import command

    database = create_engine("sqlite:///" + (tmp_path / "bridge.sqlite").as_posix())
    monkeypatch.setenv("MIGRATION_DATABASE_URL", str(database.url))
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with database.connect() as conn:
        assert conn.execute(text("SELECT version FROM schema_revisions ORDER BY version")).scalars().all() == [
            1,
            2,
            3,
            4,
            5,
            6,
        ]
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0006_registry"
    database.dispose()
