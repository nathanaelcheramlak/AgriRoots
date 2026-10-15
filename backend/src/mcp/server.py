"""Run-scoped Farmly MCP server, stdio transport, no approval/delivery tools."""
import asyncio
import json
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from src.mcp.advisory_tools import AdvisoryTools, TOOL_SCHEMAS


async def serve():
    server = Server("farmly-advisory", version="2.0.0")
    tools = AdvisoryTools(os.environ["FARMLY_RUN_ID"], os.environ["FARMLY_RUN_CAPABILITY"])
    @server.list_tools()
    async def list_tools():
        return [Tool(name=name, description={
            "get_cluster_plot_history": "Read the initiating officer's authorized cluster and plot-season history.",
            "get_weather_evidence": "Retrieve dated plot forecasts and persist sourced evidence.",
            "get_crop_risk_context": "Retrieve locally reviewed crop guidance, calendars and pest signals.",
            "save_advisory_draft": "Validate citations and persist an idempotent advisory draft; cannot approve or publish.",
        }[name], inputSchema=schema.model_json_schema()) for name, schema in TOOL_SCHEMAS.items()]
    @server.call_tool()
    async def call_tool(name, arguments):
        result = await tools.call(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(serve())
