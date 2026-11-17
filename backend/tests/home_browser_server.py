"""Disposable browser-test backend. Never seed or override an operational database.

Run only through scripts/check_home_browser.py. The model and provider are
explicit fixtures, while auth, API handlers, registry, queue, graph and evidence
are the actual application implementation.
"""
import asyncio
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

if os.environ.get("AGRI_HOME_FIXTURE") != "1":
    raise SystemExit("This fixture server requires the isolated Home test runner")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runtime = Path(tempfile.mkdtemp(prefix="agrilo-home-browser-"))
os.environ.update(DATABASE_URL="sqlite:///" + (runtime / "fixture.sqlite").as_posix(),
    JWT_SECRET_KEY=secrets.token_urlsafe(40), APP_ENV="test", REDIS_URL="", DEBUG="false",
    SECRET_ENCRYPTION_KEY="", INTERNAL_MCP_URL="", OUTBOUND_HOSTS_POLICY_FILE="")

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.auth.password import hash_password
from src.common.utils.phone import normalize_phone
from src.config.settings import get_settings
from src.db.models.connectors import ConnectorJob
from src.db.models.user import User
from src.db.session import SessionLocal
from src.integrations.jobs import process_job
from src.main import app
from tests.home_fixture import HomeModelFixture, prepare_home
from tests.test_connectors_rest import rest_fixture
from tests.test_workspace import office


async def main():
    monkeypatch = pytest.MonkeyPatch()
    fixture = rest_fixture.__wrapped__(monkeypatch)
    origin, _ = next(fixture)
    mcp_generator = None
    mcp_endpoint = None
    if os.environ.get("AGRI_PLUGINS_FIXTURE") == "1":
        from tests.test_connectors_mcp import mcp_fixture
        mcp_generator = mcp_fixture.__wrapped__(monkeypatch)
        mcp_endpoint, _ = next(mcp_generator)
    handler = fixture.gi_frame.f_locals["Handler"]
    original_get = handler.do_GET
    handler.fixture_outage = False
    def fixture_get(self):
        if handler.fixture_outage and self.path.split("?")[0] == "/soil":
            body = b'{"error":"explicit fixture provider outage"}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            original_get(self)
    handler.do_GET = fixture_get
    settings = get_settings()
    settings.connector_artifact_root = str(runtime / "private")
    settings.llm_provider = "gemini"
    settings.gemini_model = "explicit-browser-model-fixture"
    settings.model_fields_set.add("gemini_model")
    settings.gemini_api_key = "explicit-fixture-not-a-real-cloud-key"
    settings.live_model_tests_enabled = True
    settings.cors_allowed_origins = ["http://127.0.0.1:5176"]
    password = secrets.token_urlsafe(20)
    def prepare():
        with TestClient(app) as client:
            data = office.__wrapped__(client)
            prepare_home(client, data, origin, monkeypatch)
            if os.environ.get("AGRI_SKILLS_FIXTURE") == "1":
                from tests.skills_browser_fixture import prepare_skills
                prepare_skills(client, data, origin)
            with SessionLocal() as db:
                officer = db.get(User, data["users"]["officer"]["id"])
                officer.password_hash = hash_password(password)
                officer.phone_number = normalize_phone(officer.phone_number)
                phone = officer.phone_number
                db.commit()
            admin_login = None
            if mcp_endpoint:
                with SessionLocal() as db:
                    admin = db.get(User, data["users"]["admin"]["id"])
                    admin.password_hash = hash_password(password)
                    admin.phone_number = normalize_phone(admin.phone_number)
                    admin_login = {"phone": admin.phone_number, "password": password}
                    db.commit()
        return phone, admin_login
    phone, admin_login = await asyncio.to_thread(prepare)

    class BrowserModelFixture(HomeModelFixture):
        async def generate(self, contents, tools, system):
            await asyncio.sleep(1.5 if os.environ.get("AGRI_SKILLS_FIXTURE") == "1" and "[skills-fixture-pause]" in json.dumps(contents) else .35)
            return await super().generate(contents, tools, system)

    async def worker():
        while True:
            with SessionLocal() as db:
                ids = list(db.scalars(select(ConnectorJob.id).where(ConnectorJob.status == "queued")))
            for ident in ids:
                with SessionLocal() as db:
                    request = db.get(ConnectorJob, ident).request
                handler.fixture_outage = "[fixture-provider-outage]" in request.get("task", "")
                try:
                    await process_job(ident, model=BrowserModelFixture())
                finally:
                    handler.fixture_outage = False
            await asyncio.sleep(.15)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=int(os.environ["AGRI_HOME_PORT"]), log_level="warning"))
    task = asyncio.create_task(worker())
    ready = Path(os.environ["AGRI_HOME_READY"])
    ready.write_text(json.dumps({"phone": phone, "password": password, "runtime": str(runtime), "fixture": True,
        "admin": admin_login, "rest_origin": origin, "mcp_endpoint": mcp_endpoint}), encoding="utf-8")
    try:
        await server.serve()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        fixture.close()
        if mcp_generator:
            mcp_generator.close()
        monkeypatch.undo()
        ready.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
