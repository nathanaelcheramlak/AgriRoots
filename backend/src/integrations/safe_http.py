"""Controlled HTTP transport shared by REST, provider adapters and the official MCP SDK.

Production requests use the reviewed CONNECT proxy, which validates the complete DNS
answer and connects to a literal public IP. TLS still verifies the original hostname.
Only deployment configuration can grant exact local fixture origins outside production.
"""

import asyncio
import ipaddress
import json
import time
import zlib
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.config.settings import get_settings
from src.integrations.contracts import ConnectorError
from src.mcp.egress_proxy import egress_proxy


def approved_hosts():
    settings = get_settings()
    hosts = set(settings.outbound_allowed_hosts)
    if settings.outbound_hosts_policy_file:
        try:
            path = Path(settings.outbound_hosts_policy_file)
            if not path.is_absolute() or path.stat().st_size > 16384:
                raise ValueError()
            policy = json.loads(path.read_text(encoding="utf-8"))
            if set(policy) != {"hosts"} or not isinstance(policy["hosts"], list):
                raise ValueError()
            hosts = set(policy["hosts"])
        except (OSError, ValueError, TypeError):
            raise ConnectorError("EGRESS_BLOCKED", "Operator host policy file is unavailable or invalid") from None
    if any(not isinstance(host, str) or host != host.lower() or any(c in host for c in "/:@*\\") for host in hosts):
        raise ConnectorError("EGRESS_BLOCKED", "Operator host policy requires exact lowercase host names")
    return hosts


def destination(url, *, fixed_origin=False):
    settings = get_settings()
    try:
        p = urlsplit(str(url))
        if not p.hostname or p.username or p.password or p.fragment or "\\" in str(url):
            raise ValueError()
        origin = f"{p.scheme}://{p.netloc}"
        fixtures = settings.connector_fixture_origins if settings.app_env != "production" else []
        is_fixture = origin in fixtures
        if not is_fixture and (p.scheme != "https" or p.port not in (None, 443)):
            raise ValueError()
        if is_fixture and p.scheme not in ("http", "https"):
            raise ValueError()
        if any(ord(c) < 32 or ord(c) == 127 for c in str(url)) or p.query:
            raise ValueError()
        if fixed_origin and p.path not in ("", "/"):
            raise ValueError()
        if "%" in p.path or "//" in p.path or any(segment in (".", "..") for segment in p.path.split("/")):
            raise ValueError()
        host = p.hostname.encode("idna").decode().lower()
        if not is_fixture:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError()
            if host not in approved_hosts():
                raise ValueError()
        return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", "", "")), is_fixture
    except (ValueError, UnicodeError):
        raise ConnectorError(
            "EGRESS_BLOCKED", "Destination is outside the deployment-approved HTTPS host/path policy"
        ) from None


def fixed_url(base, path):
    canonical, _ = destination(base, fixed_origin=True)
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or "?" in path
        or "#" in path
        or "://" in path
    ):
        raise ConnectorError("EGRESS_BLOCKED", "A fixed absolute path on the approved origin is required")
    p = urlsplit(canonical)
    return destination(urlunsplit((p.scheme, p.netloc, path, "", "")))[0]


class LimitedStream(httpx.AsyncByteStream):
    def __init__(self, stream, limit, encoding):
        self.stream, self.limit, self.encoding = stream, limit, encoding

    async def __aiter__(self):
        total = 0
        encoded = 0
        decoder = (
            zlib.decompressobj(16 + zlib.MAX_WBITS if self.encoding == "gzip" else zlib.MAX_WBITS)
            if self.encoding
            else None
        )
        try:
            async for chunk in self.stream:
                encoded += len(chunk)
                if encoded > self.limit:
                    raise ConnectorError("RESPONSE_TOO_LARGE", "Encoded response exceeds the configured limit")
                data = decoder.decompress(chunk, self.limit - total + 1) if decoder else chunk
                total += len(data)
                if total > self.limit or decoder and decoder.unconsumed_tail:
                    raise ConnectorError("RESPONSE_TOO_LARGE", "Decompressed response exceeds the configured limit")
                yield data
            if decoder:
                tail = decoder.flush(self.limit - total + 1)
                if total + len(tail) > self.limit or not decoder.eof:
                    raise ConnectorError(
                        "OUTPUT_VALIDATION_FAILED", "Compressed response is incomplete or exceeds the limit"
                    )
                yield tail
        except zlib.error:
            raise ConnectorError("OUTPUT_VALIDATION_FAILED", "Invalid compressed response") from None
        finally:
            await self.stream.aclose()

    async def aclose(self):
        await self.stream.aclose()


class ControlledTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner, gate, limit):
        self.inner, self.gate, self.limit = inner, gate, limit

    async def handle_async_request(self, request):
        # Request queries are built by reviewed adapters, not destination configuration.
        parsed = urlsplit(str(request.url))
        destination(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")))
        if self.gate.context.deadline <= time.monotonic():
            raise ConnectorError("TIMEOUT", "Invocation deadline expired")
        attempt = self.gate.reserve_http(
            request.method, urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        )
        start = time.monotonic()
        try:
            # Revocation and dispatch serialize on the same integration row. The lock
            # remains held until the remote request has actually begun (headers return).
            async with self.gate.dispatch_lock():
                response = await self.inner.handle_async_request(request)
            self.gate.finish_http(attempt, response.status_code, "HTTP_RESPONSE", (time.monotonic() - start) * 1000)
        except BaseException as exc:
            self.gate.finish_http(
                attempt,
                None,
                exc.code if isinstance(exc, ConnectorError) else "AMBIGUOUS_TRANSPORT",
                (time.monotonic() - start) * 1000,
            )
            raise
        encoding = response.headers.get("content-encoding", "").lower()
        if 300 <= response.status_code < 400:
            await response.aclose()
            raise ConnectorError("EGRESS_BLOCKED", "Redirect responses are blocked for every connector transport")
        if encoding not in ("", "identity", "gzip", "deflate"):
            await response.aclose()
            raise ConnectorError("OUTPUT_VALIDATION_FAILED", "Unsupported response compression")
        response.stream = LimitedStream(response.stream, self.limit, encoding if encoding != "identity" else "")
        if encoding:
            response.headers.pop("content-encoding", None)
            response.headers.pop("content-length", None)
        return response

    async def aclose(self):
        await self.inner.aclose()


class SafeHttp:
    def __init__(self, gate, *, timeout=15, limit=1048576):
        self.gate, self.timeout, self.limit = gate, timeout, limit

    async def raw(self, method, url, *, headers=None, params=None, body=None, content=None, form=None):
        """Bounded bytes through the same gate as JSON; never follows redirects or retries writes."""
        if method not in ("GET", "POST", "HEAD"):
            raise ConnectorError("POLICY_DENIED", "Unsupported reviewed HTTP method")
        try:
            async with self.client(url, headers) as client:
                async with asyncio.timeout(max(.001, self.gate.context.deadline - time.monotonic())):
                    response = await client.request(method, url, params=params, json=body, content=content, data=form)
            if response.status_code in (401, 403):
                raise ConnectorError("AUTH_INVALID", "Provider rejected access")
            if response.status_code == 429:
                raise ConnectorError("RATE_LIMITED", "Provider request limit reached", retryable=True)
            if response.status_code >= 400:
                raise ConnectorError("UPSTREAM_ERROR", f"Provider returned HTTP {response.status_code}")
            import hashlib
            self.gate.record_payload({"sha256": hashlib.sha256(response.content).hexdigest(),
                                      "bytes": len(response.content)}, kind="provider_binary")
            return response
        except httpx.TimeoutException:
            raise ConnectorError("TIMEOUT", "Provider timeout; remote completion may be ambiguous") from None
        except httpx.TransportError:
            raise ConnectorError("UPSTREAM_ERROR", "Provider transport failed; remote completion may be ambiguous") from None

    @asynccontextmanager
    async def client(self, url, headers=None):
        _, fixture = destination(url)
        async with egress_proxy(
            frozenset(approved_hosts()), max_bytes=self.limit * 3, timeout=min(60, self.timeout + 5)
        ) as proxy:
            transport = ControlledTransport(
                httpx.AsyncHTTPTransport(proxy=None if fixture else proxy, retries=0), self.gate, self.limit
            )
            async with httpx.AsyncClient(
                transport=transport,
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": "AgriLo-Connectors/0.4",
                    "Accept": "application/json, text/event-stream",
                    "Accept-Encoding": "identity",
                    **(headers or {}),
                },
            ) as client:
                yield client

    async def json(
        self, method, url, *, headers=None, params=None, body=None, form=None, attempts=1, legacy_climateserv_json=False
    ):
        if method not in ("GET", "POST"):
            raise ConnectorError("POLICY_DENIED", "Only reviewed read operations are supported")
        if legacy_climateserv_json:
            canonical, fixture = destination(url)
            parsed = urlsplit(canonical)
            if (
                parsed.hostname != "climateserv.servirglobal.net"
                and not fixture
                or parsed.path
                not in {"/api/submitDataRequest/", "/api/getDataRequestProgress/", "/api/getDataFromRequest/"}
            ):
                raise ConnectorError(
                    "POLICY_DENIED", "Legacy JSON handling is restricted to reviewed ClimateSERV operations"
                )
        async with self.client(url, headers) as client:
            for attempt in range(attempts):
                try:
                    async with asyncio.timeout(max(0.001, self.gate.context.deadline - time.monotonic())):
                        response = await client.request(method, url, params=params, json=body, data=form)
                except httpx.TimeoutException:
                    raise ConnectorError(
                        "TIMEOUT", "Provider timeout; remote completion may be ambiguous", retryable=True
                    ) from None
                except httpx.TransportError:
                    raise ConnectorError(
                        "UPSTREAM_ERROR",
                        "Provider transport failed; remote completion may be ambiguous",
                        retryable=True,
                    ) from None
                code = response.status_code
                if code in (429, 502, 503, 504) and method == "GET" and attempt + 1 < attempts:
                    wait = response.headers.get("Retry-After", "1")
                    delay = float(wait) if wait.isdigit() else 1
                    if delay <= 3 and time.monotonic() + delay < self.gate.context.deadline:
                        await asyncio.sleep(delay)
                        continue
                if code in (401, 403):
                    raise ConnectorError(
                        "AUTH_INVALID", "Provider rejected this connection's credentials or access scope"
                    )
                if code == 429:
                    raise ConnectorError("RATE_LIMITED", "Provider request limit reached", retryable=True)
                if 300 <= code < 400:
                    raise ConnectorError("EGRESS_BLOCKED", "Provider redirects are not followed")
                if code >= 400:
                    raise ConnectorError("UPSTREAM_ERROR", f"Provider returned HTTP {code}", retryable=code >= 500)
                if code == 204:
                    return None
                media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                legacy_media_type = "json" not in media_type
                if legacy_media_type and not (legacy_climateserv_json and media_type in {"text/html", "text/plain"}):
                    raise ConnectorError("OUTPUT_VALIDATION_FAILED", "Expected JSON; received another content type")
                try:
                    value = response.json()

                    def bounded(item, depth=0):
                        if depth > 20:
                            raise ValueError()
                        if isinstance(item, dict):
                            if len(item) > 2000:
                                raise ValueError()
                            for v in item.values():
                                bounded(v, depth + 1)
                        elif isinstance(item, list):
                            if len(item) > 20000:
                                raise ValueError()
                            for v in item:
                                bounded(v, depth + 1)

                    bounded(value)
                    json.dumps(value, allow_nan=False)
                    self.gate.record_payload(
                        value, kind="climateserv_json_legacy_media_type" if legacy_media_type else "provider_json"
                    )
                    return value
                except (ValueError, RecursionError):
                    raise ConnectorError(
                        "OUTPUT_VALIDATION_FAILED", "Malformed, non-finite or excessively nested JSON"
                    ) from None
        raise ConnectorError("UPSTREAM_ERROR", "Provider attempts exhausted")
