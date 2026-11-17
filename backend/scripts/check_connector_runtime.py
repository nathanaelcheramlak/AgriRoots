"""Read-only deployment policy checks plus disposable checkpoint/cache/speech probes.

Run inside the API container by piping this file to ``python -``. No provider,
model or farmer-delivery requests are made. Never prints connection strings.
"""

import asyncio
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
from typing import TypedDict
from uuid import uuid4
import wave

import httpx
from langgraph.graph import StateGraph, END
from sqlalchemy import text

from src.agent.companion.graph import checkpointer
from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.integrations.contracts import ConnectorError, digest, now
from src.integrations.safe_http import destination
from src.integrations.voice.local_speech import synthesize_speech
from src.providers.inventory import inventory
from src.tools import cache


async def checkpoint_probe():
    class State(TypedDict):
        value: int

    graph = StateGraph(State)
    graph.add_node("advance", lambda state: {"value": state["value"] + 1})
    graph.set_entry_point("advance")
    graph.add_edge("advance", END)
    config = {"configurable": {"thread_id": "deployment-probe-" + uuid4().hex}}
    async with checkpointer() as saver:
        assert (await graph.compile(checkpointer=saver).ainvoke({"value": 1}, config))["value"] == 2
    async with checkpointer() as saver:
        assert (await graph.compile(checkpointer=saver).aget_state(config)).values["value"] == 2
    return "persisted and reloaded through separate PostgreSQL saver sessions as the application role"


def main():
    settings = get_settings()
    assert settings.app_env == "production" and not settings.connector_fixture_origins
    checks = {"application_environment": settings.app_env, "fixture_exceptions": 0}
    with SessionLocal() as db:
        checks["database_role"] = db.scalar(text("SELECT current_user"))
        assert checks["database_role"] == "agrilo_app"
        checks["immutable_permissions"] = {}
        for table in (
            "workspace_events",
            "connector_approvals",
            "connector_tool_versions",
            "connector_integration_versions",
            "connector_skill_versions",
        ):
            permissions = {
                name: db.scalar(
                    text("SELECT has_table_privilege(current_user, :table, :permission)"),
                    {"table": table, "permission": name},
                )
                for name in ("SELECT", "INSERT", "UPDATE", "DELETE")
            }
            assert permissions == {"SELECT": True, "INSERT": True, "UPDATE": False, "DELETE": False}
            checks["immutable_permissions"][table] = permissions
        assert not db.scalar(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')"))
        try:
            db.execute(text("UPDATE workspace_events SET action = action WHERE false"))
            raise AssertionError("Audit update unexpectedly authorized")
        except Exception as error:
            if getattr(getattr(error, "orig", None), "sqlstate", None) != "42501":
                raise
            db.rollback()
            checks["actual_audit_mutation"] = "denied with PostgreSQL insufficient_privilege"
    for kind in ("live", "ready"):
        response = httpx.get("http://127.0.0.1:8000/health/" + kind, timeout=5)
        response.raise_for_status()
        checks[kind] = response.json()
    for url in (
        "https://169.254.169.254/latest/meta-data/",
        "https://api.open-meteo.com.evil.invalid/",
        "http://127.0.0.1:9999/",
    ):
        try:
            destination(url)
            raise AssertionError("Unsafe destination unexpectedly allowed")
        except ConnectorError as error:
            assert error.code == "EGRESS_BLOCKED"
    destination("https://api.open-meteo.com/v1/forecast")
    checks["egress_policy"] = (
        "production operator host policy active; private/metadata/fixture/deceptive hosts blocked without contacting them"
    )
    checks["checkpoint"] = asyncio.run(checkpoint_probe())
    ident = digest({"deployment_probe": uuid4().hex})
    cache.put(ident, {"explicit_probe": True}, now() + timedelta(minutes=1))
    try:
        assert cache.get(ident) == {"explicit_probe": True}
        checks["redis"] = "authenticated encrypted payload read successfully"
    finally:
        cache.client(settings.redis_url).delete("agrilo:connector:" + ident)
    checks["speech"] = {}
    for language, phrase in [("en", "Inspect the crop."), ("am", "ለማሳያ ብቻ።")]:
        audio = synthesize_speech(phrase, language_code=language)
        with wave.open(io.BytesIO(audio)) as stream:
            assert stream.getframerate() >= 16000 and stream.getnframes() > 1000
            checks["speech"][language] = {"frames": stream.getnframes(), "sample_rate": stream.getframerate()}
    checks["inventory_entries"] = len(inventory()["providers"])
    assert checks["inventory_entries"] == 22
    assert httpx.post("http://mcp:8003/mcp/", timeout=5).status_code == 401
    checks["internal_mcp"] = "reachable; unauthenticated requests rejected"
    files = ["src/integrations/safe_http.py", "src/tools/executor.py", "src/agent/companion/graph.py", "src/main.py",
             "src/integrations/schema_translation.py"]
    checks["deployed_source_sha256"] = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files}
    print(
        json.dumps(
            {
                "executed_at_utc": now().isoformat(),
                "type": "REAL_LOCAL_POSTGRES_REDIS_COMPOSE_DEPLOYMENT",
                "command": "Get-Content scripts/check_connector_runtime.py -Raw | docker compose -p agrilo-connectors-test -f compose.yaml -f compose.test.yaml --env-file private-data/compose.env exec -T api python -",
                "checks": checks,
                "provider_requests": 0,
                "model_requests": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
