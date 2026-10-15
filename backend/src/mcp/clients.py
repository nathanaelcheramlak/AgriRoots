import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from contextlib import asynccontextmanager
from importlib.metadata import version
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from src.config.settings import get_settings
from src.mcp.public_sources import FETCH_VERSION, SOURCES
from src.mcp.egress_proxy import egress_proxy

BACKEND = str(Path(__file__).resolve().parents[2])


@asynccontextmanager
async def farmly_client(run_id, capability):
    settings = get_settings()
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONUNBUFFERED": "1",
           "DATABASE_URL": settings.database_url, "JWT_SECRET_KEY": "mcp-not-an-authentication-server",
           "FARMLY_RUN_ID": run_id, "FARMLY_RUN_CAPABILITY": capability,
           "ADVISORY_MAX_TOOL_CALLS": str(settings.advisory_max_tool_calls)}
    params = StdioServerParameters(command=sys.executable, args=["-m", "src.mcp.server"], env=env, cwd=BACKEND)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 15)
            yield session


async def call_farmly(session, name, inputs):
    from src.api.schemas.advisory_run import ToolResult
    response = await asyncio.wait_for(session.call_tool(name, inputs), get_settings().advisory_tool_timeout)
    if response.isError:
        raise ValueError("MCP server rejected the tool call")
    text = "".join(c.text for c in response.content if c.type == "text")
    if len(text) > 90000:
        raise ValueError("Tool output exceeds context limit")
    result = ToolResult.model_validate_json(text)
    if not result.ok:
        error = result.error
        if error.retryable: raise TimeoutError(error.message)
        raise ValueError(error.message)
    return result.data


async def fetch_public_document(source):
    if source not in SOURCES:
        raise ValueError("Document source was not approved by the operator")
    if version("mcp-server-fetch") != FETCH_VERSION:
        raise ValueError("Installed borrowed MCP server version does not match the tested pin")
    # Fresh empty cwd and an explicit minimal environment prevent inherited app
    # credentials, database config and household context reaching this server.
    with tempfile.TemporaryDirectory(prefix="farmly-fetch-") as cwd:
        async with egress_proxy() as proxy:
            params = StdioServerParameters(command=sys.executable,
                args=["-m", "mcp_server_fetch", "--proxy-url", proxy],
                # Keep node/npm out of this process: readabilipy otherwise runs
                # an unpinned npm install during extraction and pollutes stdio.
                # Its supported pure-Python extractor uses our pinned packages.
                env={"PATH": cwd, "PYTHONUNBUFFERED": "1"}, cwd=cwd)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await asyncio.wait_for(session.call_tool("fetch", {"url": source["url"], "max_length": 4000,
                                                                                 "start_index": 0, "raw": False}), 45)
                    text = "\n".join(c.text for c in result.content if c.type == "text")
                    failed = result.isError
                    text = text.split("<error>Content truncated.", 1)[0]
            # Leave the MCP transport cleanly before reporting tool errors.
            if failed:
                raise ValueError("Approved public guidance fetch failed: " + text[:500])
            if "<error>" in text or len(text.strip()) < 150:
                raise ValueError("Public guidance extract is empty or failed")
            return text[:4000]
