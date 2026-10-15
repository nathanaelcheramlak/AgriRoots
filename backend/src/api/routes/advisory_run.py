from fastapi import APIRouter, Depends
from sqlalchemy import select
from src.api.routes.workspace import service
from src.api.schemas.advisory_run import RunRequest
from src.db.models.advisory_run import AdvisoryRun, RunCall
from src.services.run_service import create_run, get_run, retry_run, run_view

router = APIRouter(prefix="/api/workspace/offices/{office_id}/runs", tags=["Advisory runs"])


@router.post("", status_code=201)
def create(office_id: str, payload: RunRequest, s=Depends(service)):
    return run_view(create_run(s.db, office_id, payload, s.user))


@router.get("")
def list_runs(office_id: str, s=Depends(service)):
    s.membership(office_id)
    return [run_view(r) for r in s.db.scalars(select(AdvisoryRun).where(AdvisoryRun.office_id == office_id)
                                            .order_by(AdvisoryRun.created_at.desc()).limit(100))]


@router.get("/{run_id}")
def detail(office_id: str, run_id: str, s=Depends(service)):
    run = get_run(s.db, office_id, run_id, s.user)
    calls = list(s.db.scalars(select(RunCall).where(RunCall.run_id == run.id).order_by(RunCall.started_at)))
    return {**run_view(run), "calls": calls}


@router.post("/{run_id}/retry")
def retry(office_id: str, run_id: str, s=Depends(service)):
    run = get_run(s.db, office_id, run_id, s.user)
    if run.officer_id != s.user.user_id:
        from src.services.workspace_service import fail
        fail(403, "Only the initiating officer can retry this run")
    run = retry_run(s.db, run)
    s.event(office_id, run.id, "run_retry_requested", attempt=run.attempt)
    s.db.commit()
    return run_view(run)
