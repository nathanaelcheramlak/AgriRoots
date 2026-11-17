"""Backend-only registration demo and bounded opt-in live connector verification.

Only initial synthetic identity bootstrapping writes directly to the isolated demo
database. Connections, versions, tests, approvals and enablement use actual APIs.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def checked(response, status=200):
    if response.status_code != status:
        raise RuntimeError(f"Application API returned {response.status_code}: {response.text[:1000]}")
    return response.json()


def seed(client):
    from src.db.session import SessionLocal
    from src.db.models.user import User, UserProfile
    from src.db.models.workspace import Administrator
    from src.auth.jwt_utils import create_access_token
    from src.auth.password import hash_password

    admin_id, farmer_id = str(uuid4()), str(uuid4())
    with SessionLocal() as db:
        for ident, role in [(admin_id, "operator"), (farmer_id, "farmer")]:
            db.add(
                User(
                    user_id=ident,
                    phone_number="+2519" + str(secrets.randbelow(10**8)).zfill(8),
                    password_hash=hash_password(secrets.token_urlsafe(24)),
                )
            )
            db.add(UserProfile(user_id=ident, full_name="Synthetic connector demonstration " + role))
        db.flush()
        db.add(Administrator(user_id=admin_id))
        db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(admin_id)}
    office = checked(
        client.post("/api/workspace/offices", headers=headers, json={"name": "Synthetic connector demonstration"}), 201
    )
    prefix = f"/api/workspace/offices/{office['id']}"
    checked(client.post(prefix + "/members", headers=headers, json={"user_id": farmer_id, "role": "farmer"}), 201)

    def record(kind, data):
        return checked(client.post(prefix + "/records", headers=headers, json={"kind": kind, "data": data}), 201)

    cluster = record("cluster", {"name": "Synthetic Adama cluster", "assigned_officer_id": admin_id, "synthetic": True})
    household = record(
        "household",
        {
            "name": "Synthetic demonstration household",
            "farmer_user_id": farmer_id,
            "cluster_id": cluster["id"],
            "assigned_officer_id": admin_id,
            "synthetic": True,
        },
    )
    plot = record(
        "plot",
        {
            "name": "Synthetic Adama point",
            "household_id": household["id"],
            "latitude": 8.54,
            "longitude": 39.27,
            "area": 1,
            "area_unit": "ha",
            "agroclimatic_zone": "Synthetic demo context",
        },
    )
    return headers, plot["id"]


def register_test_publish(client, headers, plot_id, configuration, specification, arguments):
    conn = checked(client.post("/api/v1/integrations", headers=headers, json=configuration), 201)
    prefix = f"/api/v1/integrations/{conn['id']}"
    tool = checked(client.post(prefix + "/tools", headers=headers, json=specification), 201)
    return test_publish_existing(client, headers, plot_id, conn, tool, arguments)


def test_publish_existing(client, headers, plot_id, conn, tool, arguments):
    from src.integrations.jobs import process_job

    prefix = f"/api/v1/integrations/{conn['id']}"
    exact = {key: tool[key] for key in ("version", "digest", "connection_revision")}
    job = checked(
        client.post(
            prefix + f"/tools/{tool['id']}/test",
            headers=headers,
            json={
                **exact,
                "arguments": arguments,
                "plot_ids": [plot_id],
                "authorize_network": True,
                "request_key": uuid4().hex,
            },
        ),
        202,
    )
    asyncio.run(process_job(job["id"]))
    result = checked(client.get(job["status_url"], headers=headers))
    if result["status"] == "succeeded":
        approved = checked(client.post(prefix + f"/tools/{tool['id']}/approve", headers=headers, json=exact))
        checked(
            client.patch(
                prefix + f"/tools/{tool['id']}/enabled",
                headers=headers,
                json={"enabled": True, "expected_revision": approved["revision"], "version": tool["version"]},
            )
        )
        current = checked(client.get(prefix, headers=headers))
        checked(
            client.patch(
                prefix + "/enabled",
                headers=headers,
                json={
                    "enabled": True,
                    "expected_revision": current["revision"],
                    "version": tool["connection_revision"],
                },
            )
        )
    return {"connection_id": conn["id"], "tool_id": tool["id"], "job": result}


def fixture_demo(output):
    """Persist actual API lifecycle and a graph run against explicitly synthetic HTTP/model fixtures."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = json.dumps({"ph": 6.8, "units": "pH", "fixture": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    database = ROOT / "private-data" / ("connector-fixture-" + uuid4().hex + ".sqlite")
    database.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        DATABASE_URL="sqlite:///" + database.as_posix(),
        JWT_SECRET_KEY=secrets.token_urlsafe(32),
        APP_ENV="development",
        DEBUG="false",
        CONNECTOR_FIXTURE_ORIGINS=json.dumps([origin]),
        CONNECTOR_ARTIFACT_ROOT=str(database.with_suffix("")),
    )
    from fastapi.testclient import TestClient
    from src.main import app
    from src.integrations.jobs import process_job

    class ExplicitModelFixture:
        def configuration(self):
            return {"provider": "explicit-test-fixture", "model_request_executed": False}

        async def generate(self, contents, tools, system):
            responses = [
                part["function_response"]
                for content in contents
                for part in content.get("parts", [])
                if "function_response" in part
            ]
            if not responses:
                call = {"name": tools[0]["alias"], "arguments": {}, "id": "demo-fixture-call"}
                return {
                    "calls": [call],
                    "text": "",
                    "content": {
                        "role": "model",
                        "parts": [{"function_call": {"name": call["name"], "args": {}, "id": call["id"]}}],
                    },
                    "usage": {},
                }
            evidence = responses[-1]["response"]["evidence_ids"][0]
            text = "Synthetic fixture pH is 6.8. No field measurement was made. Evidence: " + evidence
            return {"calls": [], "text": text, "content": {"role": "model", "parts": [{"text": text}]}, "usage": {}}

    try:
        with TestClient(app) as client:
            headers, plot_id = seed(client)
            actual = register_test_publish(
                client,
                headers,
                plot_id,
                {"name": "Explicit local soil fixture", "adapter_type": "rest", "base_url": origin},
                {
                    "name": "soil_fixture",
                    "description": "Explicit synthetic soil fixture; not real field data",
                    "capability_tags": ["soil.profile"],
                    "input_json_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                    "request": {"method": "GET", "path": "/soil"},
                    "response": {
                        "normalized_output_json_schema": {
                            "type": "object",
                            "properties": {
                                "ph": {"type": "number"},
                                "units": {"const": "pH"},
                                "fixture": {"const": True},
                            },
                            "required": ["ph", "units", "fixture"],
                            "additionalProperties": False,
                        }
                    },
                },
                {},
            )
            if actual["job"]["status"] != "succeeded":
                raise RuntimeError("Fixture operation test failed")
            skill = checked(
                client.post(
                    "/api/v1/skills",
                    headers=headers,
                    json={
                        "name": "soil_fixture_explanation",
                        "description": "Explain explicit fixture evidence",
                        "instructions": "Use actual evidence IDs and identify fixture values.",
                        "required_capabilities": ["soil.profile"],
                    },
                ),
                201,
            )
            exact = {"version": skill["version"], "digest": skill["digest"], "request_key": uuid4().hex}
            checked(client.post(f"/api/v1/skills/{skill['id']}/test", headers=headers, json=exact), 202)
            approved = checked(client.post(f"/api/v1/skills/{skill['id']}/approve", headers=headers, json=exact))
            checked(
                client.patch(
                    f"/api/v1/skills/{skill['id']}/enabled",
                    headers=headers,
                    json={"enabled": True, "version": skill["version"], "expected_revision": approved["revision"]},
                )
            )

            def run():
                queued = checked(
                    client.post(
                        f"/api/v1/skills/{skill['id']}/runs",
                        headers=headers,
                        json={
                            "task": "Explain this explicitly synthetic soil profile",
                            "plot_ids": [plot_id],
                            "request_key": uuid4().hex,
                            "authorize_network": True,
                        },
                    ),
                    202,
                )
                asyncio.run(process_job(queued["id"], model=ExplicitModelFixture()))
                return checked(client.get(queued["status_url"], headers=headers))

            success = run()
            prefix = "/api/v1/integrations/" + actual["connection_id"]
            current = checked(client.get(prefix, headers=headers))
            checked(
                client.patch(
                    prefix + "/enabled",
                    headers=headers,
                    json={"enabled": False, "expected_revision": current["revision"]},
                )
            )
            # A new run is refused during capability resolution after revocation.
            denied = client.post(
                f"/api/v1/skills/{skill['id']}/runs",
                headers=headers,
                json={"task": "Explain the soil after revocation", "plot_ids": [plot_id], "request_key": uuid4().hex},
            )
            report = {
                "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                "command": "python scripts/demo_connectors.py",
                "type": "EXPLICIT_FIXTURE_DEMO",
                "identity_context": "synthetic office and Adama point",
                "database": str(database),
                "registration": actual,
                "skill_run": success,
                "after_revocation": {"http_status": denied.status_code, "body": denied.json()},
                "external_provider_calls": 0,
                "real_model_calls": 0,
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            assert success["status"] == "succeeded", success
            assert denied.status_code == 409, denied.text
            print("Fixture registration, approval, skill execution, evidence and revocation verified.")
            print("Persistent demonstration and sanitized report:", output)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Explicitly authorize small public Open-Meteo and NASA MCP probes"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from dotenv import dotenv_values

    local = dotenv_values(ROOT / ".env")
    if os.environ.get("APP_ENV", local.get("APP_ENV")) == "production":
        raise SystemExit("The isolated identity-bootstrap demonstration is refused in production.")
    if not args.live:
        fixture_demo(args.output or ROOT / "reports/connector_fixture_demo.json")
        return
    args.output = args.output or ROOT / "reports/connector_live_results.json"
    database = ROOT / "private-data" / ("connector-live-" + uuid4().hex + ".sqlite")
    database.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        DATABASE_URL="sqlite:///" + database.as_posix(),
        JWT_SECRET_KEY=secrets.token_urlsafe(32),
        APP_ENV="development",
        LIVE_TESTS_ENABLED="true",
        DEBUG="false",
        CONNECTOR_MAX_PROVIDER_REQUESTS="20",
    )
    from fastapi.testclient import TestClient
    from src.main import app
    from src.providers.factory import template
    from src.db.session import SessionLocal
    from src.db.models.connectors import InvocationAttempt
    from sqlalchemy import select
    from src.config.settings import get_settings

    report = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python scripts/demo_connectors.py --live",
        "type": "LIVE_PUBLIC_CONNECTOR_VERIFICATION",
        "identity_context": "explicitly synthetic Adama office/point",
        "implementation": "agrilo-backend 0.4.0",
        "database": "isolated SQLite; PostgreSQL tested separately",
        "checks": [],
    }
    with TestClient(app) as client:
        headers, plot_id = seed(client)
        provider = template("open_meteo.forecast")
        try:
            actual = register_test_publish(
                client, headers, plot_id, provider["connection"], provider["operations"][0], {}
            )
            report["checks"].append(
                {
                    "id": "LIVE-01",
                    "provider": "Open-Meteo",
                    **actual,
                    "outcome": "VERIFIED_LIVE" if actual["job"]["status"] == "succeeded" else "FAILED",
                }
            )
        except Exception as error:
            report["checks"].append(
                {"id": "LIVE-01", "provider": "Open-Meteo", "outcome": "FAILED", "error": str(error)}
            )
        try:
            endpoint = "https://power.larc.nasa.gov/mcp/"
            conn = checked(
                client.post(
                    "/api/v1/integrations",
                    headers=headers,
                    json={
                        "name": "NASA POWER public MCP",
                        "adapter_type": "mcp",
                        "base_url": endpoint,
                        "egress_data_classes": ["public_environment", "plot_coordinates"],
                    },
                ),
                201,
            )
            prefix = f"/api/v1/integrations/{conn['id']}"
            discovery = checked(
                client.post(
                    prefix + "/discover",
                    headers=headers,
                    json={"connection_revision": 1, "authorize_network": True, "request_key": uuid4().hex},
                ),
                202,
            )
            from src.integrations.jobs import process_job

            asyncio.run(process_job(discovery["id"]))
            discovered = checked(client.get(discovery["status_url"], headers=headers))
            if discovered["status"] not in ("succeeded", "partial"):
                report["checks"].append(
                    {"id": "LIVE-02", "provider": "NASA POWER MCP", "outcome": "BLOCKED", "discovery": discovered}
                )
            else:
                candidates = checked(client.get(prefix + "/tools?limit=100", headers=headers))["items"]
                tool = next(
                    (row for row in candidates if row["specification"]["upstream_tool_name"] == "get_daily_data"), None
                )
                if not tool:
                    report["checks"].append(
                        {
                            "id": "LIVE-02",
                            "provider": "NASA POWER MCP",
                            "outcome": "BLOCKED",
                            "reason": "get_daily_data was absent or incompatible with the implemented schema subset",
                            "discovery": discovered,
                        }
                    )
                else:
                    spec = tool["specification"]
                    spec["description"] = (
                        "Retrieve one day of NASA POWER gridded historical agroclimate for an authorized plot. Not a forecast."
                    )
                    spec["capability_tags"] = ["climate.history"]
                    spec["required_data_classes"] = ["plot_coordinates"]
                    spec["response"]["format"] = "json"
                    spec["response"]["normalized_output_json_schema"] = {"type": "object"}
                    revised = checked(
                        client.post(
                            prefix + f"/tools/{tool['id']}/versions",
                            headers=headers,
                            json={
                                "expected_revision": tool["revision"],
                                "connection_revision": 1,
                                "specification": spec,
                            },
                        ),
                        201,
                    )
                    properties = spec["input_json_schema"]["properties"]
                    date_value = "2025-07-01" if properties.get("start", {}).get("format") == "date" else "20250701"
                    if properties.get("start", {}).get("type") == "integer":
                        date_value = 20250701
                    parameters = ["T2M", "PRECTOTCORR", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN"]
                    arguments = {
                        "latitude": 8.54,
                        "longitude": 39.27,
                        "start": date_value,
                        "end": date_value,
                        "community": "AG",
                        "parameters": parameters
                        if properties.get("parameters", {}).get("type") == "array"
                        else ",".join(parameters),
                    }
                    actual = test_publish_existing(client, headers, plot_id, conn, revised, arguments)
                    report["checks"].append(
                        {
                            "id": "LIVE-02",
                            "provider": "NASA POWER MCP",
                            "outcome": "VERIFIED_LIVE" if actual["job"]["status"] == "succeeded" else "FAILED",
                            "discovery": discovered,
                            **actual,
                        }
                    )
        except Exception as error:
            report["checks"].append(
                {"id": "LIVE-02", "provider": "NASA POWER MCP", "outcome": "FAILED", "error": str(error)}
            )
        settings = get_settings()
        report["checks"].append(
            {
                "id": "MODEL-01",
                "provider": "Gemini",
                "outcome": "BLOCKED" if not settings.gemini_api_key else "NOT_TESTED",
                "reason": "GEMINI_API_KEY is not configured; model ID/access must be verified"
                if not settings.gemini_api_key
                else "Run an explicitly authorized configured skill workflow; this public-API probe does not spend model quota",
            }
        )
        with SessionLocal() as db:
            report["attempts"] = [
                {
                    "method": row.method,
                    "endpoint": row.origin_path,
                    "http_status": row.status_code,
                    "outcome": row.outcome,
                    "elapsed_ms": row.elapsed_ms,
                    "started_at": row.started_at.isoformat(),
                }
                for row in db.scalars(select(InvocationAttempt).order_by(InvocationAttempt.started_at))
            ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for row in report["checks"]:
        print(row["id"], row["provider"], row["outcome"])
    print("Sanitized evidence:", args.output)


if __name__ == "__main__":
    main()
