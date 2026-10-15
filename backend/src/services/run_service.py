import hashlib
import hmac
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, update
from src.config.settings import get_settings
from src.db.models.advisory_run import AdvisoryRun, RunCall
from src.db.models.user import User
from src.services.workspace_service import WorkspaceService, fail


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def get_run(db, office_id, run_id, user):
    WorkspaceService(db, user).membership(office_id)
    run = db.get(AdvisoryRun, run_id)
    if not run or run.office_id != office_id:
        fail(404, "Run not found")
    return run


def create_run(db, office_id, payload, user):
    service = WorkspaceService(db, user)
    service.membership(office_id)
    service.record(office_id, payload.cluster_id, "cluster")
    existing = db.scalar(select(AdvisoryRun).where(AdvisoryRun.office_id == office_id,
                                                AdvisoryRun.request_key == payload.request_key))
    if existing:
        if existing.officer_id != user.user_id or existing.cluster_id != payload.cluster_id or existing.task != payload.task:
            fail(409, "Request key already belongs to a different request")
        return existing
    run = AdvisoryRun(office_id=office_id, officer_id=user.user_id, cluster_id=payload.cluster_id,
                      task=payload.task, request_key=payload.request_key)
    db.add(run); db.flush()
    service.event(office_id, run.id, "run_created", cluster_id=payload.cluster_id)
    db.commit(); db.refresh(run)
    return run


def authorize_capability(db, run_id, capability):
    run = db.get(AdvisoryRun, run_id)
    digest = hashlib.sha256(capability.encode()).hexdigest()
    if (not run or run.status != "running" or not run.capability_hash
            or not hmac.compare_digest(run.capability_hash, digest)
            or not run.lease_until or utc(run.lease_until) <= datetime.now(timezone.utc)):
        fail(403, "Run capability is invalid or expired")
    officer = db.get(User, run.officer_id)
    if not officer or not officer.is_active:
        fail(403, "Initiating officer is inactive")
    WorkspaceService(db, officer).membership(run.office_id)
    return run, officer


def run_view(run):
    return {key: getattr(run, key) for key in (
        "id", "office_id", "officer_id", "cluster_id", "task", "status", "stage", "warnings", "error",
        "attempt", "tool_calls", "advisory_id", "model_config", "created_at", "updated_at")}


def retry_run(db, run):
    if run.status == "pending_review":
        return run
    if run.status == "running" and utc(run.lease_until) > datetime.now(timezone.utc):
        fail(409, "Run is still active")
    if run.attempt >= 3:
        fail(409, "Run retry limit reached; resolve the issue before creating a new request")
    # Checkpoints retain successful tool calls and the draft link. Weather and
    # evidence validity are checked again before any resumed draft is saved.
    changed = db.execute(update(AdvisoryRun).where(AdvisoryRun.id == run.id,
        AdvisoryRun.status == run.status, AdvisoryRun.attempt == run.attempt,
        AdvisoryRun.capability_hash == run.capability_hash,
    ).values(status="queued", error=None, capability_hash=None).execution_options(synchronize_session=False))
    if not changed.rowcount:
        db.rollback(); fail(409, "Run changed; reload before retrying")
    db.commit(); db.refresh(run)
    return run
