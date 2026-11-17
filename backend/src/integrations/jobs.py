"""Small durable PostgreSQL/SQLite queue, with leases and a separately runnable worker."""

import asyncio
import json
from datetime import timedelta
import secrets
import time
from sqlalchemy import select, update, or_, and_
from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.db.models.connectors import ConnectorJob, ExecutionBudget, Integration, ToolInvocation
from src.integrations.contracts import ConnectorError, ExecutionContext, now, utc, digest
from src.integrations.service import IntegrationService, audit
from src.integrations.secrets import redact
from src.tools.policy import principal_for
from src.tools.executor import ToolExecutor, DispatchGate, connection_headers


def job_view(job):
    return {
        "id": job.id,
        "kind": job.kind,
        "target_id": job.target_id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "attempts": job.attempts,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "status_url": f"/api/v1/connector-jobs/{job.id}",
    }


def claim(job_id):
    with SessionLocal() as db:
        row = db.get(ConnectorJob, job_id)
        if not row or row.status not in ("queued", "running"):
            return None
        if row.status == "running" and row.lease_until and utc(row.lease_until) > now():
            return None
        if row.attempts >= 3:
            row.status = "failed"
            row.error = ConnectorError("TIMEOUT", "Worker retry limit reached").as_dict()
            db.commit()
            return None
        token = secrets.token_hex(24)
        changed = db.execute(
            update(ConnectorJob)
            .where(
                ConnectorJob.id == job_id,
                ConnectorJob.attempts == row.attempts,
                or_(
                    ConnectorJob.status == "queued",
                    and_(ConnectorJob.status == "running", ConnectorJob.lease_until <= now()),
                ),
            )
            .values(
                status="running",
                attempts=ConnectorJob.attempts + 1,
                lease_token=token,
                lease_until=now() + timedelta(seconds=30),
                updated_at=now(),
            )
            .execution_options(synchronize_session=False)
        ).rowcount
        db.commit()
        return token if changed else None


async def heartbeat(job_id, token):
    while True:
        await asyncio.sleep(5)
        with SessionLocal() as db:
            changed = db.execute(
                update(ConnectorJob)
                .where(ConnectorJob.id == job_id, ConnectorJob.lease_token == token, ConnectorJob.status == "running")
                .values(lease_until=now() + timedelta(seconds=30), updated_at=now())
            ).rowcount
            db.commit()
            if not changed:
                return


async def discover_job(job, principal, lease_token):
    from src.integrations.safe_http import SafeHttp
    from src.integrations.mcp_client import McpConnector
    from src.integrations.discovery import stage_catalog

    with SessionLocal() as db:
        service = IntegrationService(db, principal)
        connection = service.owned(Integration, job.snapshot["connection_id"])
        config = service.config(connection, job.snapshot["connection_revision"])
        if connection.adapter_type != "mcp":
            raise ConnectorError(
                "UNSUPPORTED_CAPABILITY", "REST connections do not support automatic operation discovery"
            )
        invocation = ToolInvocation(
            office_id=principal.office_id,
            principal_id=principal.user_id,
            job_id=job.id,
            budget_id=job.budget_id,
            request_key=f"{job.id}:discovery:{job.attempts}",
            argument_digest=digest({}),
            input_metadata={"mode": "discovery"},
        )
        db.add(invocation)
        db.flush()
        context = ExecutionContext(
            principal,
            job.budget_id,
            invocation.id,
            job_id=job.id,
            mode="discovery",
            authorize_network=True,
            lease_token=lease_token,
        )
        budget = db.get(ExecutionBudget, job.budget_id)
        context.deadline = time.monotonic() + max(0, (utc(budget.deadline) - now()).total_seconds())
        gate = DispatchGate(context, connection_id=connection.id, connection_revision=config.revision)
        gate.check(db)
        headers, credential, _ = connection_headers(db, connection, config.configuration)
        from src.tools.executor import flatten_secrets

        secret_values = flatten_secrets(credential)
        configuration = config.configuration.copy()
        db.commit()
    try:
        http = SafeHttp(gate, timeout=get_settings().connector_http_timeout)
        async with asyncio.timeout(max(0.001, context.deadline - time.monotonic())):
            catalog, complete, diagnostics = await McpConnector(http, configuration, headers).discover()
        if any(secret and secret in json.dumps(catalog) for secret in secret_values):
            raise ConnectorError(
                "OUTPUT_VALIDATION_FAILED", "MCP catalog echoed connection credentials; it was not stored or exposed"
            )
        with SessionLocal() as db:
            gate.check(db)
            service = IntegrationService(db, principal)
            connection = service.owned(Integration, job.snapshot["connection_id"])
            config = service.config(connection, job.snapshot["connection_revision"])
            snapshot = stage_catalog(db, principal, connection, config, catalog, complete, diagnostics)
            result = {
                "snapshot_id": snapshot.id,
                "complete": complete,
                "diff": snapshot.diff,
                "diagnostics": diagnostics,
                "tool_count": len(catalog),
                "automatic_enablement": False,
            }
            log = db.get(ToolInvocation, context.invocation_id)
            log.status = "SUCCESS" if complete else "PARTIAL"
            log.finished_at = now()
            log.result = result
            db.commit()
            return result
    except BaseException:
        with SessionLocal() as db:
            log = db.get(ToolInvocation, context.invocation_id)
            log.status = "UPSTREAM_ERROR"
            log.finished_at = now()
            log.result = {"error": "Discovery did not complete; no removals inferred"}
            db.commit()
        raise


async def process_job(job_id, *, model=None):
    token = claim(job_id)
    if not token:
        return False
    pulse = asyncio.create_task(heartbeat(job_id, token))
    try:
        with SessionLocal() as db:
            job = db.get(ConnectorJob, job_id)
            principal = principal_for(db, job.principal_id)
            if principal.office_id != job.office_id:
                raise ConnectorError("POLICY_DENIED", "Job ownership no longer matches active membership")
            request = job.request.copy()
            # Keep the job detached, with no lazy relationships or credential values.
            db.expunge(job)
        if job.kind == "tool_test":
            result = await ToolExecutor().execute(
                job.target_id,
                request["arguments"],
                principal,
                budget_id=job.budget_id,
                request_key=job.id + ":test",
                job_id=job.id,
                mode="test",
                plot_ids=request.get("plot_ids", []),
                authorize_network=request["authorize_network"],
                authorize_credit_use=request.get("authorize_credit_use", False),
                lease_token=token,
            )
            status = "succeeded" if result["execution_outcome"] == "SUCCESS" else "failed"
        elif job.kind == "discovery":
            result = await discover_job(job, principal, token)
            status = "succeeded" if result["complete"] else "partial"
        elif job.kind == "skill_run":
            from src.agent.companion.graph import execute_skill_job

            with SessionLocal() as db:
                budget = db.get(ExecutionBudget, job.budget_id)
                remaining = max(0.001, (utc(budget.deadline) - now()).total_seconds())
            async with asyncio.timeout(remaining):
                result = await execute_skill_job(job, principal, token, model=model)
            status = "succeeded" if result.get("status") == "completed" else "partial"
        else:
            raise ConnectorError("UNSUPPORTED_CAPABILITY", "Unknown job kind")
        with SessionLocal() as db:
            row = db.get(ConnectorJob, job_id)
            if row.lease_token == token and row.status == "running":
                row.status = status
                row.result = redact(result)
                row.error = result.get("error")
                row.updated_at = now()
                row.lease_until = None
                row.lease_token = None
                audit(db, principal, job_id, "connector_job_completed", status=status)
                if job.kind == "tool_test":
                    connection = db.get(Integration, job.snapshot["connection_id"])
                    connection.health = result["execution_outcome"] if status == "failed" else result["data_outcome"]
                db.commit()
        return True
    except BaseException as original:
        error = original
        while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
            error = error.exceptions[0]
        failure = (
            error
            if isinstance(error, ConnectorError)
            else ConnectorError(
                "CANCELLED"
                if isinstance(error, asyncio.CancelledError)
                else "TIMEOUT"
                if isinstance(error, TimeoutError)
                else "UPSTREAM_ERROR",
                "Job was interrupted"
                if isinstance(error, asyncio.CancelledError)
                else "Execution deadline exceeded"
                if isinstance(error, TimeoutError)
                else "Job failed; inspect sanitized invocation records",
            )
        )
        if not isinstance(error, ConnectorError):
            import logging
            import traceback

            logging.getLogger(__name__).error(
                "Connector job exception %s at %s",
                type(error).__name__,
                [(frame.name, frame.lineno) for frame in traceback.extract_tb(error.__traceback__)[-5:]],
            )
        with SessionLocal() as db:
            row = db.get(ConnectorJob, job_id)
            if row and row.lease_token == token:
                row.status = "cancelled" if failure.code == "CANCELLED" else "failed"
                row.error = failure.as_dict()
                row.updated_at = now()
                row.lease_until = None
                row.lease_token = None
                db.commit()
        if isinstance(original, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
            raise
        return False
    finally:
        pulse.cancel()
        await asyncio.gather(pulse, return_exceptions=True)


async def work(once=False):
    while True:
        with SessionLocal() as db:
            ids = list(
                db.scalars(
                    select(ConnectorJob.id)
                    .where(
                        or_(
                            ConnectorJob.status == "queued",
                            and_(ConnectorJob.status == "running", ConnectorJob.lease_until <= now()),
                        )
                    )
                    .order_by(ConnectorJob.created_at)
                    .limit(4)
                )
            )
        for job_id in ids:
            await process_job(job_id)
        if once:
            return
        await asyncio.sleep(1)
