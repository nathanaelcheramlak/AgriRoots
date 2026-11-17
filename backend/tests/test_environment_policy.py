"""Real-farm environmental evidence mode never supplies private registry context to a model."""

# ruff: noqa: F401,F811 -- imported pytest fixtures
import asyncio
import json
from uuid import uuid4

import pytest

from src.agent.companion.environment_policy import environment_prompt, scope_environment_snapshot
from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.integrations.contracts import ConnectorError
from src.integrations.jobs import process_job
from src.integrations.llm.companion_model import function_response
from tests.home_fixture import HomeModelFixture, prepare_home
from tests.test_connectors_rest import rest_fixture
from tests.test_farm_registry import setup_registry
from tests.test_workspace import office


def test_environment_prompt_excludes_private_context_and_coordinates():
    plot = {
        "id": "private-plot-id",
        "latitude": 9.123456,
        "longitude": 38.654321,
        "farm_context": {"crop": "Private crop", "notes": "Private note"},
    }
    prompt = environment_prompt(
        {"task": "Check forecast and soil", "parameters": {"name": "Private name"}},
        [plot],
        {"missing_optional_capabilities": []},
    )
    text = json.dumps(prompt)
    for value in ["private-plot-id", "9.123456", "38.654321", "Private crop", "Private note", "Private name"]:
        assert value not in text
    response = json.dumps(
        function_response(
            "weather",
            {
                "data": {"source_coordinates": [38.654321, 9.123456], "rain_mm": 2},
                "source": {"url": "https://example.invalid?latitude=9.123456"},
            },
        )
    )
    assert "9.123456" not in response and "38.654321" not in response and "rain_mm" in response


def test_new_demo_skills_do_not_add_implicit_rainfall_to_home_weather_soil():
    snapshot = {
        "manifest": {
            "required_capabilities": ["weather.forecast", "soil.profile"],
            "allowed_internal_actions": [],
            "optional_capabilities": ["rainfall.history"],
        },
        "tools": [{"capability_tags": [cap]} for cap in ("weather.forecast", "soil.profile", "rainfall.history")],
        "missing_optional_capabilities": [],
    }
    scoped = scope_environment_snapshot(snapshot)
    assert [t["capability_tags"] for t in scoped["tools"]] == [["weather.forecast"], ["soil.profile"]]
    assert scoped["missing_optional_capabilities"] == ["rainfall.history"]


def test_other_capabilities_are_not_authorized_by_weather_soil_mode():
    snapshot = {
        "manifest": {
            "required_capabilities": ["climate.history"],
            "allowed_internal_actions": [],
            "optional_capabilities": [],
        },
        "tools": [],
        "missing_optional_capabilities": [],
    }
    with pytest.raises(ConnectorError, match="weather forecasts"):
        scope_environment_snapshot(snapshot)
    snapshot["manifest"]["required_capabilities"] = ["weather.forecast"]
    snapshot["manifest"]["optional_capabilities"] = ["climate.history"]
    snapshot["tools"] = [{"capability_tags": ["weather.forecast"]}, {"capability_tags": ["climate.history"]}]
    result = scope_environment_snapshot(snapshot)
    assert len(result["tools"]) == 1 and result["missing_optional_capabilities"] == ["climate.history"]
    assert len(snapshot["tools"]) == 2


def test_real_registered_farm_runs_with_only_minimized_environmental_context(
    client, office, rest_fixture, monkeypatch, tmp_path
):
    _, _, _, plot, _ = setup_registry(client, office, monkeypatch)
    origin, _ = rest_fixture
    skill = prepare_home(client, office, origin, monkeypatch)
    monkeypatch.setattr(get_settings(), "cloud_model_data_policy", "environment_only")
    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path))
    captured = []

    class Capture(HomeModelFixture):
        async def generate(self, contents, tools, system):
            captured.append(json.dumps(contents))
            return await super().generate(contents, tools, system)

    context = client.get("/api/v1/companion/context", headers=office["headers"]).json()
    assert context["model"]["plot_data_policy"] == "environment_only"
    assert all(
        set(cap for tool in item["tools"] for cap in tool["capabilities"]) <= {"weather.forecast", "soil.profile"}
        for item in context["skills"]
    )
    r = client.post(
        f"/api/v1/skills/{skill['id']}/runs",
        headers=office["headers"],
        json={
            "task": "Inspect weather and soil",
            "plot_ids": [plot["id"]],
            "request_key": uuid4().hex,
            "authorize_network": True,
            "authorize_model": True,
        },
    )
    assert r.status_code == 202, r.text
    assert asyncio.run(process_job(r.json()["id"], model=Capture()))
    job = client.get(r.json()["status_url"], headers=office["headers"]).json()
    assert job["status"] == "succeeded", job
    assert len(job["result"]["evidence_ids"]) == 2
    combined = " ".join(captured)
    assert plot["id"] not in combined and "Test Farmer" not in combined and "Private sensitive notes" not in combined
    assert "farm_contexts" not in combined and "source_coordinates" not in combined
