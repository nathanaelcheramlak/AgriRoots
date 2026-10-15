"""Readiness probes; never generates advice or changes office records."""
import asyncio
from importlib.metadata import version
from sqlalchemy import select, text
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys
import tempfile
import httpx
from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.db.models.workspace import Membership, WorkspaceRecord
from src.mcp.clients import farmly_client
from src.mcp.public_sources import FETCH_VERSION
from src.mcp.public_sources import SOURCES
from src.mcp.clients import fetch_public_document
from src.db.models.advisory_run import PublicDocument
from datetime import datetime, timezone, timedelta
from src.services.run_service import utc
from src.integrations.voice.local_speech import synthesize_speech
import hashlib


async def check_forecast(client, retry_delay=1):
    for attempt in range(2):
        try:
            forecast = await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": 9.03, "longitude": 38.74, "daily": "precipitation_sum,temperature_2m_max,wind_speed_10m_max",
                "timezone": "UTC", "forecast_days": 4}, timeout=30)
            forecast.raise_for_status()
            if len(forecast.json()["daily"]["time"]) != 4:
                raise ValueError("Readiness forecast is incomplete")
            return
        except httpx.HTTPError as exc:
            if attempt: raise RuntimeError("Live weather readiness failed after two attempts; retry startup when the provider is reachable") from exc
            await asyncio.sleep(retry_delay)


async def main():
    settings = get_settings()
    assert synthesize_speech("Synthetic readiness check.", "en").startswith(b"RIFF")
    with SessionLocal() as db:
        assert list(db.scalars(text("SELECT version FROM schema_revisions ORDER BY version"))) == [1, 2, 3]
        assert db.scalar(select(Membership).where(Membership.role == "officer"))
        assert db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.kind == "calendar"))
        seasons = list(db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.kind == "season")))
        today = datetime.now(timezone.utc).date().isoformat()
        assert any(s.data["planting_date"] <= today <= (s.data.get("harvest_date") or "") for s in seasons), "Demo crop seasons expired; update the synthetic records through the workspace."
    headers = {"Authorization": "Bearer " + open(settings.advisory_model_key_file).read().strip()}
    async with httpx.AsyncClient(trust_env=False) as client:
        for phone in ("+251900000001", "+251900000002", "+251900000003"):
            login = await client.post("http://127.0.0.1:8000/api/auth/login",
                json={"phone_number": phone, "password": "SyntheticDemo123!"})
            login.raise_for_status()
        response = await client.get(settings.advisory_model_url + "/v1/models", headers=headers)
        response.raise_for_status()
        assert settings.advisory_model_id in [m["id"] for m in response.json()["data"]]
        await check_forecast(client)
    async with farmly_client("readiness-no-run", "no-write-capability") as session:
        assert {t.name for t in (await session.list_tools()).tools} == {
            "get_cluster_plot_history", "get_weather_evidence", "get_crop_risk_context", "save_advisory_draft"}
    assert version("mcp-server-fetch") == FETCH_VERSION
    with tempfile.TemporaryDirectory() as cwd:
        async with stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "mcp_server_fetch"],
                cwd=cwd, env={"PATH": cwd})) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), 15)
                assert "fetch" in {t.name for t in (await session.list_tools()).tools}
    for source in SOURCES:
        with SessionLocal() as db:
            cached = db.get(PublicDocument, source["url"])
            fresh = cached and cached.server_version == FETCH_VERSION and timedelta(0) <= datetime.now(timezone.utc) - utc(cached.retrieved_at) < timedelta(days=30)
        if not fresh:
            extract = await fetch_public_document(source)
            with SessionLocal() as db:
                db.merge(PublicDocument(url=source["url"], retrieved_at=datetime.now(timezone.utc), extract=extract,
                    sha256=hashlib.sha256(extract.encode()).hexdigest(), source_license=source["license"], server_version=FETCH_VERSION))
                db.commit()
    print("Ready: migrated database, seeded office, authenticated model, both MCP servers, live forecast and public guidance cache.")


if __name__ == "__main__":
    try: asyncio.run(asyncio.wait_for(main(), 150))
    except (RuntimeError, httpx.HTTPError, TimeoutError) as exc:
        raise SystemExit(f"Demo readiness failed: {exc}") from None
