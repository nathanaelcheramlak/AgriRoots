"""Explicit local operator activation of four reviewed agricultural data providers.

JSON on stdin identifies an existing administrator, connection IDs and skill IDs.
Run with LIVE_TESTS_ENABLED=true to authorize bounded upstream verification.
Uses normal exact-version jobs, executor, evidence, approvals and enablement.
No model, diagnosis, delivery or new credential is used by this command.
"""

import asyncio
from datetime import timedelta
import json
from pathlib import Path
import secrets
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from src.config.settings import get_settings  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402
from src.db.models.user import User, UserProfile  # noqa: E402
from src.db.models.workspace import WorkspaceRecord, Membership, WorkspaceEvent  # noqa: E402
from src.db.models.connectors import Integration, RegisteredTool, ConnectorJob, ExecutionBudget, InvocationAttempt  # noqa: E402
from src.auth.password import hash_password  # noqa: E402
from src.api.schemas.workspace import RecordInput  # noqa: E402
from src.integrations.contracts import TestRequest, ExactVersion, Enabled, ConnectorError, now  # noqa: E402
from src.integrations.jobs import process_job  # noqa: E402
from src.integrations.service import IntegrationService, credential_scope  # noqa: E402
from src.skills.service import SkillService  # noqa: E402
from src.services.workspace_service import WorkspaceService  # noqa: E402
from src.tools.policy import principal_for, require_admin, authorized_plots  # noqa: E402
from src.tools.executor import ToolExecutor  # noqa: E402

PRIORITY = {
    "open_meteo": {"handler": "open_meteo.forecast", "skill": "weather_forecast", "ttl": 3600},
    "isda_soil": {"handler": "isda.soil_profile", "skill": "soil_profile", "ttl": 2592000},
    "chirps": {"handler": "chirps.rainfall_history", "skill": "rainfall_history", "ttl": 86400},
    "nasa_power": {"handler": "nasa_power.history", "skill": "climate_history", "ttl": 86400},
}


def validation_plot(actor):
    """Seed labelled test context only; source evidence is subsequently fetched live."""
    with SessionLocal() as db:
        query = select(WorkspaceRecord).where(
            WorkspaceRecord.office_id == actor.office_id, WorkspaceRecord.kind == "plot"
        )
        for row in db.scalars(query):
            if row.data.get("name") == "SYNTHETIC Adama API validation plot":
                authorized_plots(db, actor, [row.id])
                return row.id
        user = User(
            phone_number="validation-" + uuid4().hex[:8], password_hash=hash_password(secrets.token_urlsafe(32))
        )
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.user_id, full_name="SYNTHETIC API validation farmer"))
        db.add(Membership(office_id=actor.office_id, user_id=user.user_id, role="farmer"))
        db.add(
            WorkspaceEvent(
                office_id=actor.office_id,
                actor_id=actor.user_id,
                entity_id=user.user_id,
                action="validation_identity_created",
                details={"synthetic": True, "interactive_password_saved": False},
            )
        )
        db.commit()
        service = WorkspaceService(db, db.get(User, actor.user_id))

        def record(kind, data):
            return service.save_record(actor.office_id, RecordInput(kind=kind, data=data))

        cluster = record(
            "cluster",
            {"name": "SYNTHETIC API validation cluster", "assigned_officer_id": actor.user_id, "synthetic": True},
        )
        household = record(
            "household",
            {
                "name": "SYNTHETIC API validation household",
                "farmer_user_id": user.user_id,
                "cluster_id": cluster.id,
                "assigned_officer_id": actor.user_id,
                "synthetic": True,
            },
        )
        plot = record(
            "plot",
            {
                "name": "SYNTHETIC Adama API validation plot",
                "household_id": household.id,
                "latitude": 8.54,
                "longitude": 39.27,
                "area": 1,
                "area_unit": "ha",
                "agroclimatic_zone": "Synthetic validation context only",
            },
        )
        return plot.id


async def finish_provider(actor, provider_id, connection_id, plot_id):
    definition = PRIORITY[provider_id]
    with SessionLocal() as db:
        service = IntegrationService(db, actor)
        connection = service.owned(Integration, connection_id)
        config = service.config(connection)
        if config.configuration.get("handler_id") != definition["handler"]:
            raise ConnectorError("POLICY_DENIED", "Priority activation may only target its reviewed provider handler")
        tool = db.scalar(
            select(RegisteredTool).where(
                RegisteredTool.connection_id == connection.id,
                RegisteredTool.name == definition["handler"].replace(".", "_"),
            )
        )
        if not tool:
            raise ConnectorError("NOT_FOUND", "Register the reviewed provider operation first")
        tool, version = service.tool_version(connection.id, tool.id)
        view = service.tool_view(tool, version)
        if view["approved"] and tool.enabled and tool.enabled_version == version.version and connection.enabled:
            return {"provider_id": provider_id, "status": "ALREADY_ACTIVE", "tool_version_id": version.id}
        spec = json.loads(json.dumps(version.specification))
        endpoint_review = provider_id == "chirps" and "ClimateSERV /api/ strict JSON" not in spec["description"]
        if endpoint_review:
            spec["description"] += (
                "; ClimateSERV /api/ strict JSON parsing with reviewed legacy media types; synthetic Adama coverage only."
            )
        if (
            spec["policy"]["cache_ttl_seconds"] != definition["ttl"]
            or version.connection_revision != config.revision
            or endpoint_review
        ):
            spec["policy"]["cache_ttl_seconds"] = definition["ttl"]
            tool, version = service.register_tool(
                connection.id, spec, expected_revision=tool.revision, connection_revision=config.revision
            )
        arguments = {"start": "2025-07-01", "end": "2025-07-01"} if provider_id in ("chirps", "nasa_power") else {}
        exact = ExactVersion(
            version=version.version, connection_revision=version.connection_revision, digest=version.digest
        )
        request = TestRequest(
            **exact.model_dump(),
            arguments=arguments,
            plot_ids=[plot_id],
            authorize_network=True,
            request_key=f"priority:{provider_id}:{version.id}:{credential_scope(db, connection)[:8]}:{now():%Y%m%d}",
        )
        job = service.queue_tool_test(connection.id, tool.id, request)
        job_id, tool_id, version_id = job.id, tool.id, version.id
    # The deployed worker may have already claimed this job. Claims are atomic.
    await process_job(job_id)
    deadline = time.monotonic() + 185
    while True:
        with SessionLocal() as db:
            job = db.get(ConnectorJob, job_id)
            if job.status not in ("queued", "running"):
                result = job.result or {}
                summary = {
                    "provider_id": provider_id,
                    "job_id": job_id,
                    "tool_version_id": version_id,
                    "job_status": job.status,
                    "execution_outcome": result.get("execution_outcome"),
                    "data_outcome": result.get("data_outcome"),
                    "classification": result.get("classification"),
                    "evidence_ids": result.get("evidence_ids", []),
                    "retrieved_at": result.get("retrieved_at"),
                    "source": result.get("source"),
                    "data": result.get("data"),
                    "limitations": result.get("limitations", []),
                    "error": job.error or result.get("error"),
                }
                break
        if time.monotonic() >= deadline:
            return {
                "provider_id": provider_id,
                "job_id": job_id,
                "status": "NOT_ENABLED",
                "reason": "Verification did not finish within the operator wait limit",
            }
        await asyncio.sleep(0.25)
    if (
        summary["job_status"] != "succeeded"
        or summary["execution_outcome"] != "SUCCESS"
        or summary["data_outcome"] != "VALID"
        or not summary["evidence_ids"]
    ):
        return {**summary, "status": "NOT_ENABLED"}
    with SessionLocal() as db:
        service = IntegrationService(db, actor)
        approved = service.approve_tool(connection_id, tool_id, exact)
        service.set_tool_enabled(
            connection_id, tool_id, Enabled(enabled=True, expected_revision=approved["revision"], version=exact.version)
        )
        connection = service.owned(Integration, connection_id)
        service.set_enabled(
            connection_id,
            Enabled(enabled=True, expected_revision=connection.revision, version=exact.connection_revision),
        )
        budget = ExecutionBudget(office_id=actor.office_id, deadline=now() + timedelta(seconds=30))
        db.add(budget)
        db.flush()
        budget_id = budget.id
        db.commit()
    runtime = await ToolExecutor().execute(
        version_id,
        arguments,
        actor,
        budget_id=budget_id,
        request_key="priority-runtime:" + uuid4().hex,
        plot_ids=[plot_id],
        authorize_network=True,
    )
    if runtime["execution_outcome"] != "SUCCESS":
        with SessionLocal() as db:
            service = IntegrationService(db, actor)
            connection = service.owned(Integration, connection_id)
            service.set_enabled(connection_id, Enabled(enabled=False, expected_revision=connection.revision))
            tool, version = service.tool_version(connection_id, tool_id)
            service.set_tool_enabled(
                connection_id, tool_id, Enabled(enabled=False, expected_revision=tool.revision, version=version.version)
            )
        return {**summary, "status": "RUNTIME_CHECK_FAILED", "runtime": runtime}
    return {
        **summary,
        "status": "ENABLED",
        "runtime_verified": True,
        "runtime_cache_hit": runtime.get("cache_hit", False),
        "coverage_limit": "Synthetic Adama polygon only"
        if provider_id == "chirps"
        else "Live verification at the synthetic Adama point; broader accuracy not established",
    }


async def activate(request):
    if not get_settings().live_tests_enabled:
        raise ConnectorError(
            "POLICY_DENIED", "Explicitly enable LIVE_TESTS_ENABLED for this bounded verification command"
        )
    selected = request.get("provider_ids", list(PRIORITY))
    if not selected or len(selected) != len(set(selected)) or set(selected) - set(PRIORITY):
        raise ConnectorError("POLICY_DENIED", "Only the four fixed first-wave data providers may be activated")
    with SessionLocal() as db:
        actor = principal_for(db, request["principal_id"])
        require_admin(actor)
        if request.get("plot_id"):
            authorized_plots(db, actor, [request["plot_id"]])
    plot_id = request.get("plot_id") or validation_plot(actor)
    reports = []
    for provider_id in selected:
        try:
            result = await finish_provider(actor, provider_id, request["connections"][provider_id], plot_id)
        except ConnectorError as error:
            result = {"provider_id": provider_id, "status": "NOT_ENABLED", "error": error.as_dict()}
        reports.append(result)
    skills = []
    for provider_id in selected:
        if next(r for r in reports if r["provider_id"] == provider_id)["status"] not in ("ENABLED", "ALREADY_ACTIVE"):
            continue
        with SessionLocal() as db:
            service = SkillService(db, actor)
            skill, version = service.version(request["skills"][PRIORITY[provider_id]["skill"]])
            current = service.skill_view(skill, version)
            if not current["approved"] or not current["enabled"]:
                exact = SimpleNamespace(
                    version=version.version, digest=version.digest, request_key=f"priority-skill:{version.id}"
                )
                service.test_skill(skill.id, exact)
                approved = service.approve_skill(skill.id, exact)
                current = service.enable_skill(
                    skill.id, Enabled(enabled=True, expected_revision=approved["revision"], version=version.version)
                )
            skills.append(
                {
                    "name": current["name"],
                    "id": current["id"],
                    "enabled": current["enabled"],
                    "approved": current["approved"],
                    "test_type": "configuration_validation_no_model_request",
                }
            )
    with SessionLocal() as db:
        job_ids = [r["job_id"] for r in reports if r.get("job_id")]
        from src.db.models.connectors import ToolInvocation

        attempts = (
            list(
                db.scalars(
                    select(InvocationAttempt)
                    .join(ToolInvocation, ToolInvocation.id == InvocationAttempt.invocation_id)
                    .where(ToolInvocation.job_id.in_(job_ids))
                )
            )
            if job_ids
            else []
        )
        trace = [
            {"method": r.method, "endpoint": r.origin_path, "http_status": r.status_code, "outcome": r.outcome}
            for r in attempts
        ]
    return {
        "executed_at_utc": now().isoformat(),
        "type": "FIRST_WAVE_ACTUAL_PROVIDER_ACTIVATION",
        "office_id": actor.office_id,
        "plot_id": plot_id,
        "context_note": "Explicit synthetic validation records; provider evidence is separately classified by the executor",
        "providers": reports,
        "skills": skills,
        "http_attempts": trace,
        "model_requests": 0,
        "diagnosis_requests": 0,
        "delivery_performed": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(activate(json.load(sys.stdin))), ensure_ascii=True, indent=2))
    except ConnectorError as error:
        print(json.dumps({"error": error.as_dict()}))
        raise SystemExit(1) from None
    except Exception as error:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "ACTIVATION_FAILED",
                        "type": type(error).__name__,
                        "message": "Inspect sanitized job records; secret input was not printed",
                    }
                }
            )
        )
        raise SystemExit(1) from None
