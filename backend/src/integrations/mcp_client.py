"""Official SDK 1.29 Streamable HTTP client, with the application's controlled HTTP transport."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from importlib.metadata import version as package_version
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from src.integrations.contracts import ConnectorError, ConnectorResult
from src.integrations.mappings import mapped
from src.integrations.schema_translation import validate


class McpConnector:
    def __init__(self, http, configuration, headers):
        self.http, self.configuration, self.headers = http, configuration, headers

    @asynccontextmanager
    async def session(self):
        if package_version("mcp") != "1.29.0":
            raise ConnectorError(
                "UNSUPPORTED_PROTOCOL", "This release is tested with mcp==1.29.0; install the lockfile"
            )
        url = self.configuration["base_url"]
        try:
            async with self.http.client(url, self.headers) as client:
                async with streamable_http_client(url, http_client=client) as (read, write, _):
                    async with ClientSession(
                        read, write, read_timeout_seconds=timedelta(seconds=self.http.timeout)
                    ) as session:
                        initialized = await session.initialize()
                        yield (
                            session,
                            {
                                "sdk": "mcp",
                                "sdk_version": package_version("mcp"),
                                "transport": "streamable-http",
                                "protocol_version": initialized.protocolVersion,
                                "server": initialized.serverInfo.model_dump(mode="json"),
                            },
                        )
        except BaseException as original:
            error = original
            while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
                error = error.exceptions[0]
            if isinstance(error, (ConnectorError, asyncio.CancelledError)):
                raise error
            import logging
            import traceback

            logging.getLogger(__name__).error(
                "MCP exception %s at %s",
                type(error).__name__,
                [(frame.name, frame.lineno) for frame in traceback.extract_tb(error.__traceback__)[-5:]],
            )
            text = str(error).lower()
            if "401" in text or "403" in text:
                raise ConnectorError(
                    "AUTH_INVALID",
                    "MCP endpoint rejected configured authentication; interactive OAuth is not implemented",
                ) from None
            if "protocol version" in text or "unsupported protocol" in text:
                raise ConnectorError(
                    "UNSUPPORTED_PROTOCOL", "Server protocol is incompatible with the pinned SDK"
                ) from None
            if "timeout" in text or isinstance(error, TimeoutError):
                raise ConnectorError("TIMEOUT", "MCP operation exceeded its deadline", retryable=True) from None
            raise ConnectorError(
                "UPSTREAM_ERROR", "MCP protocol/transport failed; inspect sanitized attempt records"
            ) from None

    async def discover(self):
        async with self.session() as (session, diagnostics):
            catalog, cursor, complete = [], None, False
            seen = set()
            for _ in range(5):
                page = await session.list_tools(cursor=cursor)
                for tool in page.tools:
                    if tool.name in seen:
                        raise ConnectorError("OUTPUT_VALIDATION_FAILED", "MCP catalog contains duplicate tool names")
                    seen.add(tool.name)
                    catalog.append(tool.model_dump(mode="json", exclude_none=True))
                    if len(catalog) >= 200:
                        diagnostics["limitation"] = "Discovery reached the 200-tool limit; removal inference disabled"
                        return catalog, False, diagnostics
                cursor = page.nextCursor
                if not cursor:
                    complete = True
                    break
            if not complete:
                diagnostics["limitation"] = "Discovery reached the five-page limit; removal inference disabled"
            return catalog, complete, diagnostics

    async def invoke(self, version, arguments, context):
        spec = version.specification
        if not spec.get("upstream_tool_name"):
            raise ConnectorError("UNSUPPORTED_CAPABILITY", "MCP operation has no reviewed upstream tool name")
        async with self.session() as (session, diagnostics):
            result = await session.call_tool(spec["upstream_tool_name"], arguments)
            self.http.gate.record_payload(result.model_dump(mode="json"), kind="mcp_tool_result")
            if result.isError:
                raise ConnectorError("UPSTREAM_ERROR", "MCP tool returned an error result")
            structured = result.structuredContent
            source = {"url": self.configuration["base_url"], "upstream_tool": spec["upstream_tool_name"], **diagnostics}
            if structured is None:
                text = "\n".join(block.text for block in result.content if block.type == "text")
                unsupported = [block.type for block in result.content if block.type != "text"]
                if spec["response"]["format"] == "text":
                    if not text:
                        raise ConnectorError("UNSUPPORTED_CAPABILITY", "MCP response has no permitted text content")
                    validate(text, spec["response"]["normalized_output_json_schema"], output=True)
                    return ConnectorResult(
                        data_outcome="UNSTRUCTURED",
                        data=text,
                        source=source,
                        limitations=["Unstructured source evidence; not validated numerical agricultural measurements"]
                        + (["Unreviewed resource/image/audio links were not retrieved"] if unsupported else []),
                    )
                try:
                    structured = json.loads(text)
                except ValueError:
                    raise ConnectorError(
                        "OUTPUT_VALIDATION_FAILED", "MCP tool did not return its reviewed structured format"
                    ) from None
            if spec["response"].get("provider_output_json_schema"):
                validate(structured, spec["response"]["provider_output_json_schema"], output=True)
            limits = []
            data = (
                mapped(spec["response"]["field_mapping"], response=structured, limitations=limits)
                if spec["response"]["field_mapping"]
                else structured
            )
            validate(data, spec["response"]["normalized_output_json_schema"], output=True)
            return ConnectorResult(data=data, source=source, limitations=limits)
