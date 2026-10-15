"""An authenticated HTTPS CONNECT proxy with exact-domain and pinned-public-IP egress.

Each redirect's new connection is checked. Resolved addresses are checked as a set,
then a literal IP is passed to the socket connector, closing the DNS-rebinding gap.
"""
import asyncio
import base64
import ipaddress
import secrets
import socket
from contextlib import asynccontextmanager
from src.mcp.public_sources import ALLOWED_HOSTS


def public_ip(address):
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def validate_authority(authority):
    host, sep, port = authority.rpartition(":")
    if not sep or port != "443" or host.lower() not in ALLOWED_HOSTS:
        raise ValueError("Public guidance domain or port is not approved")
    return host.lower()


async def public_addresses(host):
    infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses or not all(public_ip(ip) for ip in addresses):
        raise ValueError("Public source resolved to a private or special-use destination")
    return addresses


@asynccontextmanager
async def egress_proxy():
    password = secrets.token_hex(24)
    expected = "Basic " + base64.b64encode(("farmly:" + password).encode()).decode()
    async def handle(reader, writer):
        upstream = None
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            if len(header) > 8192: raise ValueError("Header too large")
            lines = header.decode("ascii").split("\r\n")
            method, authority, protocol = lines[0].split(" ")
            fields = dict(line.split(": ", 1) for line in lines[1:] if line)
            auth = next((v for k, v in fields.items() if k.lower() == "proxy-authorization"), "")
            if method != "CONNECT" or not secrets.compare_digest(auth, expected):
                raise ValueError("Proxy authorization required")
            host = validate_authority(authority)
            addresses = await public_addresses(host)
            upstream_reader, upstream = await asyncio.wait_for(asyncio.open_connection(addresses[0], 443), 10)
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n"); await writer.drain()
            total = 0
            async def copy(source, target):
                nonlocal total
                while chunk := await source.read(32768):
                    total += len(chunk)
                    if total > 2 * 1024 * 1024:
                        raise ValueError("Public document response exceeds limit")
                    target.write(chunk); await target.drain()
            async def tunnel():
                tasks = [asyncio.create_task(copy(reader, upstream)), asyncio.create_task(copy(upstream_reader, writer))]
                try:
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in done: t.result()
                finally:
                    for t in tasks: t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.wait_for(tunnel(), 30)
        except Exception:
            if not writer.is_closing():
                try: writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n"); await writer.drain()
                except Exception: pass
        finally:
            if upstream: upstream.close()
            writer.close()
    server = await asyncio.start_server(handle, "127.0.0.1", 0, limit=8192)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://farmly:{password}@127.0.0.1:{port}"
    finally:
        server.close(); await server.wait_closed()
