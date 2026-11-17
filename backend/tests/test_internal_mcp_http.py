"""The existing four domain tools over actual HTTP; only the model and evidence are fixtures."""

# ruff: noqa: F401, F811 -- pytest discovers imported fixtures by name
import asyncio
import socket
from threading import Thread
import time

import httpx
import pytest
import uvicorn

from tests.test_workspace import office  # noqa: F401
from tests.test_advisory_runs import ready, TestModel, detail  # noqa: F401
from src.agent.advisory.graph import execute_run
from src.config.settings import get_settings
from src.mcp.http_server import make_app


@pytest.fixture
def internal_http(monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    endpoint = f"http://127.0.0.1:{sock.getsockname()[1]}/mcp/"
    server = uvicorn.Server(uvicorn.Config(make_app(), log_level="error", lifespan="on"))
    thread = Thread(target=lambda: asyncio.run(server.serve(sockets=[sock])), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    monkeypatch.setattr(get_settings(), "internal_mcp_url", endpoint)
    yield endpoint
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def test_internal_http_mcp_preserves_run_scope_and_persisted_review_draft(client, ready, internal_http):
    assert httpx.post(internal_http, timeout=5).status_code == 401
    assert (
        httpx.post(
            internal_http, headers={"Authorization": "Bearer invalid", "X-Agrilo-Run-Id": ready["run"]["id"]}, timeout=5
        ).status_code
        == 403
    )
    asyncio.run(execute_run(ready["run"]["id"], model=TestModel()))
    result = detail(client, ready)
    assert result["status"] == "pending_review", result["error"]
    executed = {item["tool_name"] for item in result["calls"]}
    assert {
        "get_cluster_plot_history",
        "get_weather_evidence",
        "get_crop_risk_context",
        "save_advisory_draft",
    } <= executed
    drafts = client.get(ready["prefix"] + "/advisories", headers=ready["headers"]).json()
    assert len(drafts) == 1 and drafts[0]["status"] == "pending_review"
    assert client.get("/api/workspace/released", headers=ready["users"]["farmer"]["headers"]).json() == []
