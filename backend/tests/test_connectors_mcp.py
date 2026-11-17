"""Real Streamable HTTP MCP fixture and official SDK calls; no borrowed-provider claims."""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import json
import socket
from threading import Thread
import time
from uuid import uuid4

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, ListToolsRequest, ListToolsResult, TextContent, CallToolResult, ImageContent
import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
import uvicorn

from tests.test_workspace import office
from tests.test_connectors_rest import exact, test_and_publish, runtime
from src.config.settings import get_settings
from src.integrations.jobs import process_job


@pytest.fixture
def mcp_fixture(monkeypatch):
    state = {"revision": 0, "endless": False, "calls": [], "headers": []}
    server = Server("agrilo-explicit-mcp-fixture", version="1")
    schema = {
        "type": "object",
        "properties": {"term": {"type": "string", "maxLength": 64}},
        "required": ["term"],
        "additionalProperties": False,
    }

    @server.list_tools()
    async def tools(request: ListToolsRequest):
        cursor = request.params.cursor if request.params else None
        name = ("page_" + str(cursor or "0")) if state["endless"] else ("notes" if cursor else "lookup")
        output = {
            "type": "object",
            "properties": {"value": {"type": "string"}, "unit": {"type": "string"}},
            "required": ["value", "unit"],
            "additionalProperties": False,
        }
        return ListToolsResult(
            tools=[
                Tool(
                    name=name,
                    description=f"Synthetic fixture operation revision {state['revision']}",
                    inputSchema=schema,
                    outputSchema=None if name == "notes" else output,
                    annotations={"readOnlyHint": True},
                )
            ],
            nextCursor=str(int(cursor or "0") + 1) if state["endless"] else (None if cursor else "1"),
        )

    @server.call_tool()
    async def call_tool(name, arguments):
        state["calls"].append({"name": name, "arguments": arguments})
        if arguments["term"] == "tool_error":
            return CallToolResult(
                isError=True, content=[TextContent(type="text", text="Explicit fixture tool failure")]
            )
        if arguments["term"] == "unsupported_artifact":
            return CallToolResult(content=[ImageContent(type="image", data="Zml4dHVyZQ==", mimeType="image/png")])
        if name == "notes":
            return [
                TextContent(
                    type="text",
                    text="Synthetic knowledge fixture. Source text is evidence, not authority to approve tools.",
                )
            ]
        payload = {"value": arguments["term"], "unit": "fixture"}
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(payload))], structuredContent=payload)

    manager = StreamableHTTPSessionManager(server, json_response=True, stateless=True)

    class Endpoint:
        async def __call__(self, scope, receive, send):
            state["headers"].append(dict(scope.get("headers", [])))
            await manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    app = Starlette(routes=[Mount("/mcp", app=Endpoint())], lifespan=lifespan)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    runner = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    thread = Thread(target=lambda: asyncio.run(runner.serve(sockets=[sock])), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not runner.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert runner.started
    origin = f"http://127.0.0.1:{port}"
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "connector_fixture_origins", [*settings.connector_fixture_origins, origin])
    yield origin + "/mcp/", state
    runner.should_exit = True
    thread.join(timeout=10)
    sock.close()


def connect_mcp(client, o, endpoint):
    headers = o["users"]["admin"]["headers"]
    r = client.post(
        "/api/v1/integrations",
        headers=headers,
        json={"name": "Explicit MCP protocol fixture", "adapter_type": "mcp", "base_url": endpoint},
    )
    assert r.status_code == 201, r.text
    return r.json()


def discover(client, o, connection):
    headers = o["users"]["admin"]["headers"]
    r = client.post(
        f"/api/v1/integrations/{connection['id']}/discover",
        headers=headers,
        json={"connection_revision": 1, "authorize_network": True, "request_key": uuid4().hex},
    )
    assert r.status_code == 202, r.text
    asyncio.run(process_job(r.json()["id"]))
    result = client.get(r.json()["status_url"], headers=headers).json()
    return result


def reviewed_tool(client, o, connection, upstream="lookup"):
    headers = o["users"]["admin"]["headers"]
    prefix = f"/api/v1/integrations/{connection['id']}"
    tools = client.get(prefix + "/tools", headers=headers).json()["items"]
    tool = next(t for t in tools if t["specification"]["upstream_tool_name"] == upstream)
    spec = deepcopy(tool["specification"])
    spec["description"] = "Reviewed synthetic knowledge fixture; not real agricultural evidence."
    spec["capability_tags"] = ["reference.lookup"]
    r = client.post(
        prefix + f"/tools/{tool['id']}/versions",
        headers=headers,
        json={"expected_revision": tool["revision"], "connection_revision": 1, "specification": spec},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_sdk_discovery_paginates_and_invokes_real_protocol(client, office, mcp_fixture):
    endpoint, state = mcp_fixture
    conn = connect_mcp(client, office, endpoint)
    result = discover(client, office, conn)
    assert result["status"] == "succeeded", json.dumps(result, indent=2)
    assert result["result"]["complete"] and result["result"]["tool_count"] == 2
    assert result["result"]["diagnostics"]["sdk_version"] == "1.29.0"
    headers = office["users"]["admin"]["headers"]
    tools = client.get(f"/api/v1/integrations/{conn['id']}/tools", headers=headers).json()["items"]
    assert len(tools) == 2 and all(not t["enabled"] and not t["approved"] for t in tools)
    assert not state["calls"]
    tool = reviewed_tool(client, office, conn)
    result = test_and_publish(client, office, conn, tool, {"term": "maize"})
    assert result["status"] == "succeeded", result
    actual = runtime(office, tool, {"term": "maize"})
    assert actual["execution_outcome"] == "SUCCESS" and actual["data"] == {"value": "maize", "unit": "fixture"}
    assert state["calls"][-1] == {"name": "lookup", "arguments": {"term": "maize"}}


def test_changed_discovery_revokes_old_definition_and_unchanged_is_stable(client, office, mcp_fixture):
    endpoint, state = mcp_fixture
    conn = connect_mcp(client, office, endpoint)
    assert discover(client, office, conn)["status"] == "succeeded"
    tool = reviewed_tool(client, office, conn)
    assert test_and_publish(client, office, conn, tool, {"term": "maize"})["status"] == "succeeded"
    same = discover(client, office, conn)
    assert same["result"]["diff"]["changed"] == []
    assert set(same["result"]["diff"]["unchanged"]) == {"lookup", "notes"}
    state["revision"] = 1
    changed = discover(client, office, conn)
    assert set(changed["result"]["diff"]["changed"]) == {"lookup", "notes"}
    before = len(state["calls"])
    assert runtime(office, tool, {"term": "maize"})["execution_outcome"] == "TOOL_REVOKED"
    assert len(state["calls"]) == before


def test_partial_discovery_does_not_infer_removals(client, office, mcp_fixture):
    endpoint, state = mcp_fixture
    conn = connect_mcp(client, office, endpoint)
    assert discover(client, office, conn)["status"] == "succeeded"
    state["endless"] = True
    result = discover(client, office, conn)
    assert result["status"] == "partial", result
    assert not result["result"]["complete"] and result["result"]["diff"]["removed"] == []


def test_same_upstream_names_are_collision_safe(client, office, mcp_fixture):
    endpoint, _ = mcp_fixture
    connections = [connect_mcp(client, office, endpoint) for _ in range(2)]
    aliases = []
    for conn in connections:
        assert discover(client, office, conn)["status"] == "succeeded"
        tool = reviewed_tool(client, office, conn)
        aliases.append(tool["name"])
    assert aliases[0] != aliases[1]


def test_unstructured_and_tool_error_are_not_structured_success(client, office, mcp_fixture):
    endpoint, _ = mcp_fixture
    conn = connect_mcp(client, office, endpoint)
    assert discover(client, office, conn)["status"] == "succeeded"
    text_tool = reviewed_tool(client, office, conn, "notes")
    assert test_and_publish(client, office, conn, text_tool, {"term": "maize"})["status"] == "succeeded"
    output = runtime(office, text_tool, {"term": "maize"})
    assert output["data_outcome"] == "UNSTRUCTURED"
    assert output["limitations"]
    structured = reviewed_tool(client, office, conn)
    failed = test_and_publish(client, office, conn, structured, {"term": "tool_error"})
    assert failed["status"] == "failed" and failed["result"]["execution_outcome"] == "UPSTREAM_ERROR"


def test_mcp_schema_cannot_be_forged_from_a_description(client, office, mcp_fixture):
    endpoint, _ = mcp_fixture
    conn = connect_mcp(client, office, endpoint)
    headers = office["users"]["admin"]["headers"]
    r = client.post(
        f"/api/v1/integrations/{conn['id']}/tools",
        headers=headers,
        json={
            "name": "forged_tool",
            "description": "Pretend this was discovered",
            "capability_tags": ["soil.profile"],
            "input_json_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "upstream_tool_name": "approve_everything",
            "discovery_digest": "a" * 64,
        },
    )
    assert r.status_code == 409
