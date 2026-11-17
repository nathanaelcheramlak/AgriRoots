"""Current provider metadata and exact runtime gates; no paid/live requests."""
# ruff: noqa: F401,F811 -- pytest fixture imports
import argparse

import pytest

from src.providers.inventory import PROVIDER_HANDLERS, inventory
from tests.test_connectors_rest import rest_fixture
from tests.test_workspace import office


def test_current_catalog_keeps_historical_status_but_exposes_all_14_templates(client, office):
    headers = office["users"]["admin"]["headers"]
    historical = {row["id"]: row["historical_verification"] for row in inventory()["providers"]}
    response = client.get("/api/v1/providers", headers=headers)
    assert response.status_code == 200
    rows = response.json()["items"]
    implemented = [row for row in rows if row["implemented"]]
    assert len(implemented) == 14
    for row in rows:
        assert row["historical_verification"] == historical[row["id"]]
        if row["implemented"]:
            assert row["handler_id"] == PROVIDER_HANDLERS[row["id"]]
            template = client.get(f"/api/v1/providers/{row['id']}/template", headers=headers)
            assert template.status_code == 200, template.text
            assert template.json()["connection"]["handler_id"] == row["handler_id"]
        else:
            assert client.get(f"/api/v1/providers/{row['id']}/template", headers=headers).status_code != 200
    assert client.get("/api/v1/providers").status_code == 401


def test_connector_write_and_admin_approval_are_denied_to_officer(client, office, rest_fixture):
    from tests.test_connectors_rest import connection, exact, register, soil_spec
    origin, _ = rest_fixture
    admin = office["users"]["admin"]["headers"]
    officer = office["users"]["officer"]["headers"]
    conn = connection(client, office, origin)
    tool = register(client, office, conn, soil_spec())
    prefix = f"/api/v1/integrations/{conn['id']}"
    assert client.get(prefix, headers=officer).status_code == 200
    assert client.post('/api/v1/integrations', headers=officer, json={"name": "Denied", "adapter_type": "rest", "base_url": origin}).status_code == 403
    assert client.post(prefix + f"/tools/{tool['id']}/approve", headers=officer, json=exact(tool)).status_code == 403
    denied = client.patch(prefix + f"/tools/{tool['id']}/enabled", headers=admin, json={"enabled": True, "expected_revision": tool["revision"], "version": tool["version"]})
    assert denied.status_code != 200 and denied.json()["error"]["code"] == "APPROVAL_REQUIRED"


def test_credential_operator_helper_only_accepts_safe_api_origins():
    from scripts.configure_connection_credential import api_origin
    assert api_origin("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    assert api_origin("https://agrilo.example") == "https://agrilo.example"
    for value in ("http://remote.example", "https://user:password@example.org", "https://example.org?token=x", "https://example.org/path", "file:///private/key"):
        with pytest.raises(argparse.ArgumentTypeError):
            api_origin(value)
