"""Run connector tests only against the named disposable local Compose test database.

The test fixture drops all application tables. Never point it at an operational DB.
Passwords are read from the ignored environment and are never printed.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
TESTS = [
    "test_connector_policy",
    "test_connectors_rest",
    "test_connectors_mcp",
    "test_companion_skills",
    "test_provider_adapters",
    "test_internal_mcp_http",
    "test_connector_redis",
    "test_mcp_compatibility",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / "private-data/compose.env")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    password = values.get("POSTGRES_PASSWORD")
    if not password:
        raise SystemExit("POSTGRES_PASSWORD is missing from the private test environment")
    environment = {
        **os.environ,
        "AGRIROOTS_TEST_DATABASE_URL": "postgresql+psycopg://agrilo_owner:"
        + quote(password, safe="")
        + "@127.0.0.1:25432/agrilo_test",
        "AGRIROOTS_TEST_REDIS_URL": "redis://127.0.0.1:26379/5",
    }
    # The fixed host/port/database belong to the dedicated compose.test.yaml project.
    # Refuse to create/drop arbitrary databases supplied through CLI configuration.
    import psycopg
    from psycopg import sql

    with psycopg.connect(
        host="127.0.0.1",
        port=25432,
        dbname="agrilo",
        user="agrilo_owner",
        password=password,
        connect_timeout=5,
        autocommit=True,
    ) as db:
        if not db.execute("SELECT 1 FROM pg_database WHERE datname = 'agrilo_test'").fetchone():
            db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("agrilo_test")))
    command = [
        sys.executable,
        "-m",
        "pytest",
        *["tests/" + name + ".py" for name in TESTS],
        "-q",
        "--tb=short",
        "--junitxml=validation/agri-mcp-postgres-redis.xml",
    ]
    raise SystemExit(subprocess.call(command, cwd=ROOT, env=environment))


if __name__ == "__main__":
    main()
