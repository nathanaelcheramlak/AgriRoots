"""Reused agricultural parsers and complete adapter requests against labeled HTTP fixtures."""

# ruff: noqa: F401, F811 -- pytest discovers imported fixtures by name
from copy import deepcopy
import json

import pytest
from src.db.models.workspace import WorkspaceRecord
from src.db.session import SessionLocal

from tests.test_workspace import office  # noqa: F401
from tests.test_connectors_rest import rest_fixture, register, test_and_publish, runtime  # noqa: F401
from src.providers.factory import HANDLERS, template
from src.providers.agriculture import validate_power
from src.integrations.contracts import ConnectorError


def test_chirps_uses_current_documented_api_routes_for_submit_poll_and_result(
    client, office, rest_fixture, monkeypatch
):
    origin, calls = rest_fixture
    with SessionLocal() as db:
        plot = db.get(WorkspaceRecord, office["plot"]["id"])
        plot.data = {**plot.data, "latitude": 8.54, "longitude": 39.27}
        db.commit()
    monkeypatch.setitem(
        HANDLERS, "chirps.rainfall_history", {**HANDLERS["chirps.rainfall_history"], "base_url": origin}
    )
    provider = template("chirps.rainfall_history")
    response = client.post(
        "/api/v1/integrations", headers=office["users"]["admin"]["headers"], json=provider["connection"]
    )
    assert response.status_code == 201
    tool = register(client, office, response.json(), provider["operations"][0])
    result = test_and_publish(client, office, response.json(), tool, {"start": "2025-07-01", "end": "2025-07-01"})
    assert result["status"] == "succeeded", result
    assert result["result"]["classification"] == "fixture"
    assert result["result"]["data"]["data"][0]["value"]["avg"] == 7.8
    assert [row["path"].split("?")[0] for row in calls] == [
        "/api/submitDataRequest/",
        "/api/getDataRequestProgress/",
        "/api/getDataFromRequest/",
    ]


def test_generic_rest_cannot_adopt_provider_only_legacy_json_handling(client, office, rest_fixture):
    from tests.test_connectors_rest import connection

    origin, calls = rest_fixture
    conn = connection(client, office, origin)
    spec = {
        "name": "strict_json_progress",
        "description": "Explicit fixture to verify generic JSON media-type enforcement",
        "capability_tags": ["reference.lookup"],
        "input_json_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "request": {"method": "GET", "path": "/api/getDataRequestProgress/"},
        "response": {"normalized_output_json_schema": {"type": "array", "items": {"type": "number"}}},
    }
    tool = register(client, office, conn, spec)
    result = test_and_publish(client, office, conn, tool, {})
    assert result["status"] == "failed" and result["result"]["execution_outcome"] == "OUTPUT_VALIDATION_FAILED"
    assert len(calls) == 1


def test_legacy_json_handling_cannot_be_used_on_other_provider_origins():
    import asyncio
    from src.integrations.safe_http import SafeHttp

    async def probe():
        with pytest.raises(ConnectorError) as error:
            await SafeHttp(None).json(
                "GET", "https://api.open-meteo.com/api/submitDataRequest/", legacy_climateserv_json=True
            )
        assert error.value.code == "POLICY_DENIED"

    asyncio.run(probe())


@pytest.mark.parametrize("handler_id", ["open_meteo.forecast", "isda.soil_profile"])
def test_reviewed_provider_adapter_uses_common_executor_and_transport(
    client, office, rest_fixture, monkeypatch, handler_id
):
    origin, calls = rest_fixture
    definition = {**HANDLERS[handler_id], "base_url": origin}
    monkeypatch.setitem(HANDLERS, handler_id, definition)
    provider = template(handler_id)
    headers = office["users"]["admin"]["headers"]
    response = client.post("/api/v1/integrations", headers=headers, json=provider["connection"])
    assert response.status_code == 201, response.text
    conn = response.json()
    if handler_id.startswith("isda."):
        response = client.put(
            f"/api/v1/integrations/{conn['id']}/credential",
            headers=headers,
            json={
                "value": {"username": "fixture@example.invalid", "password": "fixture-provider-password"},
                "principal_scope": "explicit-fixture-account",
            },
        )
        assert response.status_code == 200
    tool = register(client, office, conn, provider["operations"][0])
    assert test_and_publish(client, office, conn, tool, {})["status"] == "succeeded"
    result = runtime(office, tool, {})
    assert result["execution_outcome"] == "SUCCESS" and result["classification"] == "fixture"
    assert result["source"]["provider"] == ("iSDAsoil" if handler_id.startswith("isda.") else "Open-Meteo")
    assert result["evidence_ids"] and result["limitations"]
    with SessionLocal() as db:
        evidence = db.get(WorkspaceRecord, result["evidence_ids"][0])
        assert len(evidence.data["provider_response_digests"]) == (4 if handler_id.startswith("isda.") else 1)
        assert all(len(row["sha256"]) == 64 for row in evidence.data["provider_response_digests"])
    if handler_id.startswith("isda."):
        assert len(calls) == 8  # each invocation logs in, reads layers, reads two available properties
        assert calls[-1]["headers"]["Authorization"] == "Bearer explicit-fixture-short-lived-token"
        assert "fixture-provider-password" not in json.dumps(result)
        assert result["data"]["properties"]["ph"][0]["value"]["value"] == 6.8
    else:
        assert len(calls) == 2 and result["data"]["units"]["precipitation_sum"] == "mm"


def power_fixture():
    fields = {"T2M": "C", "PRECTOTCORR": "mm/day", "RH2M": "%", "WS2M": "m/s", "ALLSKY_SFC_SW_DWN": "MJ/m^2/day"}
    return {
        "geometry": {"coordinates": [39.27, 8.54]},
        "header": {"time_standard": "UTC"},
        "properties": {"parameter": {name: {"20250701": 1.0} for name in fields}},
        "parameters": {name: {"units": unit} for name, unit in fields.items()},
    }


@pytest.mark.parametrize("failure", ["units", "fill", "dates", "location", "bool"])
def test_power_validation_rejects_plausible_but_invalid_agricultural_payloads(failure):
    args = {"start": "2025-07-01", "end": "2025-07-01", "latitude": 8.54, "longitude": 39.27}
    raw = power_fixture()
    assert validate_power(raw, args)["time_standard"] == "UTC"
    invalid = deepcopy(raw)
    if failure == "units":
        invalid["parameters"]["T2M"]["units"] = "F"
    elif failure == "fill":
        invalid["properties"]["parameter"]["T2M"]["20250701"] = -999
    elif failure == "dates":
        invalid["properties"]["parameter"]["T2M"]["20250702"] = 25
    elif failure == "location":
        invalid["geometry"]["coordinates"] = [0, 0]
    else:
        invalid["properties"]["parameter"]["T2M"]["20250701"] = True
    with pytest.raises(ConnectorError) as error:
        validate_power(invalid, args)
    assert error.value.code == "OUTPUT_VALIDATION_FAILED"
