"""Deployment-controlled HTTP surface for the existing four run-scoped domain tools.

Authorization is the worker's short-lived run capability, not a client-supplied office
identity. Tenant registration cannot launch this process or choose its command.
"""

from contextlib import asynccontextmanager
from contextvars import ContextVar
import json
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount
import uvicorn

from src.db.session import SessionLocal
from src.services.run_service import authorize_capability
from src.mcp.advisory_tools import AdvisoryTools, TOOL_SCHEMAS

scope_context = ContextVar("agrilo_mcp_run_scope", default=None)


def make_app():
    server = Server("agrilo-reviewed-domain-tools", version="0.4.0")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=name,
                description="Run-scoped reviewed domain operation: " + name,
                inputSchema=schema.model_json_schema(),
            )
            for name, schema in TOOL_SCHEMAS.items()
        ]

    @server.call_tool()
    async def call_tool(name, arguments):
        scope = scope_context.get()
        if not scope:
            return [TextContent(type="text", text=json.dumps({"ok": False, "error": {"code": "AUTH_REQUIRED"}}))]
        result = await AdvisoryTools(scope[0], scope[1]).call(name, arguments)
        return [TextContent(type="text", text=json.dumps(result))]

    manager = StreamableHTTPSessionManager(server, json_response=True, stateless=True)

    class Endpoint:
        async def __call__(self, scope, receive, send):
            headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
            run_id = headers.get("x-agrilo-run-id", "")
            authorization = headers.get("authorization", "")
            if not authorization.startswith("Bearer "):
                await JSONResponse({"error": "AUTH_REQUIRED"}, status_code=401)(scope, receive, send)
                return
            capability = authorization[7:]
            try:
                with SessionLocal() as db:
                    authorize_capability(db, run_id, capability)
            except Exception:
                await JSONResponse({"error": "POLICY_DENIED"}, status_code=403)(scope, receive, send)
                return
            token = scope_context.set((run_id, capability))
            try:
                await manager.handle_request(scope, receive, send)
            finally:
                scope_context.reset(token)

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    return Starlette(routes=[Mount("/mcp", app=Endpoint())], lifespan=lifespan)


if __name__ == "__main__":
    uvicorn.run(make_app(), host="0.0.0.0", port=8003, log_level="warning")
