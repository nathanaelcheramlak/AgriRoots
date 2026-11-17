"""Three-field map registration uses the real registry transaction and scope rules."""

# ruff: noqa: F401,F811 -- imported pytest fixtures
from uuid import uuid4

from sqlalchemy import func, select

from src.db.models.farm_registry import Farmer, RegisteredPlot
from src.db.session import SessionLocal
from tests.test_farm_registry import rectangle, setup_registry
from tests.test_workspace import office


def payload():
    return {
        "selection_boundary": rectangle(38.615, 8.815, 38.65, 8.85),
        "geometry": rectangle(38.62, 8.82, 38.621, 8.821),
        "farmer_name": "Test Farmer Quick",
        "farmer_reference": "QUICK-001",
        "phone": "+251911111222",
        "request_key": uuid4().hex,
    }


def test_three_field_save_replays_and_reuses_farmer_without_exposing_phone(client, office, monkeypatch):
    territory, _, _, _, _ = setup_registry(client, office, monkeypatch)
    url = f"/api/v1/registry/territories/{territory['id']}/farm-registrations"
    body = payload()
    first = client.post(url, headers=office["headers"], json=body)
    assert first.status_code == 201, first.text
    farm = first.json()
    assert farm["id"] == farm["home_plot"]["id"] and not farm["home_plot"]["synthetic"]
    assert farm["farmers"][0]["reference"] == "QUICK-001"
    assert body["phone"] not in first.text
    repeated = client.post(url, headers=office["headers"], json=body)
    assert repeated.status_code == 201 and repeated.json()["id"] == farm["id"]
    changed = client.post(url, headers=office["headers"], json={**body, "farmer_name": "Different person"})
    assert changed.status_code == 409
    second = client.post(
        url,
        headers=office["headers"],
        json={**body, "geometry": rectangle(38.63, 8.83, 38.631, 8.831), "request_key": uuid4().hex},
    )
    assert second.status_code == 201, second.text
    assert second.json()["farmerIds"] == farm["farmerIds"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Farmer)) == 2  # existing fixture + one new farmer
        assert db.scalar(select(func.count()).select_from(RegisteredPlot)) == 3


def test_crop_and_assignment_checks_rollback_failed_farmer_creation(client, office, monkeypatch):
    territory, assignment, _, _, _ = setup_registry(client, office, monkeypatch)
    url = f"/api/v1/registry/territories/{territory['id']}/farm-registrations"
    body = payload()
    outside = client.post(
        url, headers=office["headers"], json={**body, "geometry": rectangle(38.66, 8.86, 38.661, 8.861)}
    )
    assert outside.status_code == 422
    # Geometry conflicts are discovered after preparing the farmer: neither may commit.
    conflict = client.post(
        url,
        headers=office["headers"],
        json={**body, "selection_boundary": rectangle(), "geometry": rectangle(38.61, 8.81, 38.611, 8.811)},
    )
    assert conflict.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Farmer)) == 1
        assert db.scalar(select(func.count()).select_from(RegisteredPlot)) == 1
    assert client.post(url, headers=office["headers"], json={**body, "synthetic": True}).status_code == 422
    assert client.post(url, headers=office["headers"], json={**body, "phone": "-------"}).status_code == 422
    client.delete(
        "/api/v1/registry/assignments/" + assignment["id"] + "?expected_revision=1",
        headers=office["users"]["admin"]["headers"],
    )
    assert client.post(url, headers=office["headers"], json=body).status_code == 403
