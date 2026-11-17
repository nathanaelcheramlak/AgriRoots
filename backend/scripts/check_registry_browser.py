"""Disposable actual-PostGIS browser acceptance. Never uses the operational agrilo database."""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = dotenv_values(ROOT / "private-data/compose.env")
    admin_url = "postgresql://agrilo_owner:" + quote(values["POSTGRES_PASSWORD"], safe="") + "@127.0.0.1:25432/postgres"
    name = "agrilo_registry_browser_" + uuid4().hex[:12]
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=10) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    with tempfile.TemporaryDirectory(prefix="agrilo-registry-browser-") as temporary:
        ready = Path(temporary) / "ready.json"
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {
            **os.environ,
            "AGRI_HOME_FIXTURE": "1",
            "AGRI_HOME_PORT": str(port),
            "AGRI_HOME_READY": str(ready),
            "AGRI_REGISTRY_DATABASE_URL": admin_url.replace("postgresql://", "postgresql+psycopg://").rsplit("/", 1)[0]
            + "/"
            + name,
            "FIELDOPS_BACKEND_URL": f"http://127.0.0.1:{port}",
            "VITE_API_MODE": "http",
            "VITE_API_BASE_URL": "/backend",
        }
        with (Path(temporary) / "backend.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "tests/home_browser_server.py"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            try:
                for _ in range(180):
                    if ready.exists():
                        break
                    if process.poll() is not None:
                        raise RuntimeError("Isolated registry fixture stopped during startup")
                    time.sleep(0.5)
                else:
                    raise RuntimeError("Registry fixture startup timeout")
                return subprocess.run(
                    [
                        shutil.which("node") or "node",
                        "node_modules/@playwright/test/cli.js",
                        "test",
                        "--config",
                        "playwright.registry.config.ts",
                    ],
                    cwd=ROOT.parent / "agrilo-fieldops-frontend",
                    env=env,
                    check=False,
                ).returncode
            finally:
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
                        )
                    else:
                        process.terminate()
                process.wait(timeout=15)
                log.flush()
                # Logs may contain session details; retain only in ignored private storage.
                (ROOT / "private-data/registry-browser.log").write_text(
                    (Path(temporary) / "backend.log").read_text(), encoding="utf-8"
                )
                with psycopg.connect(admin_url, autocommit=True, connect_timeout=10) as conn:
                    conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    raise SystemExit(main())
