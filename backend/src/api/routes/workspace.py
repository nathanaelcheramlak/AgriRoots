from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from time import perf_counter
from src.db.models.user import User

from src.api.schemas.workspace import Named, MemberInput, RecordInput, AdvisoryInput, Transition
from src.auth.dependencies import get_current_user
from src.db.models.workspace import (Administrator, Office, Membership, WorkspaceRecord,
                                     Advisory, AdvisoryVersion, WorkspaceEvent)
from src.db.session import get_db
from src.integrations.voice.local_speech import synthesize_speech
from src.config.settings import get_settings
from src.services.workspace_service import WorkspaceService, public_version, fail

router = APIRouter(prefix="/api/workspace", tags=["Extension workspace"])


def service(db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        yield WorkspaceService(db, user)
    except IntegrityError:
        db.rollback()
        fail(409, "Record conflict; reload before continuing")


@router.get("/me")
def me(s: WorkspaceService = Depends(service)):
    memberships = list(s.db.scalars(select(Membership).where(Membership.user_id == s.user.user_id)))
    return {"user_id": s.user.user_id, "global_administrator": bool(s.db.get(Administrator, s.user.user_id)),
            "memberships": [{"office_id": m.office_id, "role": m.role,
                              "office_name": s.db.get(Office, m.office_id).name} for m in memberships]}


@router.post("/offices", status_code=201)
def create_office(payload: Named, s: WorkspaceService = Depends(service)):
    return s.create_office(payload.name)


@router.get("/offices")
def offices(s: WorkspaceService = Depends(service)):
    if not s.db.get(Administrator, s.user.user_id):
        fail(403, "Provisioned administrator required")
    return list(s.db.scalars(select(Office)))


@router.get("/offices/{office_id}/members")
def members(office_id: str, s: WorkspaceService = Depends(service)):
    s.membership(office_id)
    return [{"office_id": m.office_id, "user_id": m.user_id, "role": m.role,
             "name": (s.db.get(User, m.user_id).profile.full_name
                      if s.db.get(User, m.user_id).profile else None)}
            for m in s.db.scalars(select(Membership).where(Membership.office_id == office_id))]


@router.post("/offices/{office_id}/members", status_code=201)
def assign_member(office_id: str, payload: MemberInput, s: WorkspaceService = Depends(service)):
    return s.assign_member(office_id, payload)


@router.get("/offices/{office_id}/records")
def records(office_id: str, kind: str | None = None, s: WorkspaceService = Depends(service)):
    s.membership(office_id)
    query = select(WorkspaceRecord).where(WorkspaceRecord.office_id == office_id)
    if kind:
        query = query.where(WorkspaceRecord.kind == kind)
    return list(s.db.scalars(query.order_by(WorkspaceRecord.created_at)))


@router.post("/offices/{office_id}/records", status_code=201)
def create_record(office_id: str, payload: RecordInput, s: WorkspaceService = Depends(service)):
    return s.save_record(office_id, payload)


@router.put("/offices/{office_id}/records/{record_id}")
def edit_record(office_id: str, record_id: str, payload: RecordInput, s: WorkspaceService = Depends(service)):
    return s.save_record(office_id, payload, record_id)


@router.post("/offices/{office_id}/advisories", status_code=201)
def create_advisory(office_id: str, payload: AdvisoryInput, s: WorkspaceService = Depends(service)):
    return s.save_advisory(office_id, payload)


@router.put("/offices/{office_id}/advisories/{advisory_id}")
def edit_advisory(office_id: str, advisory_id: str, payload: AdvisoryInput, s: WorkspaceService = Depends(service)):
    return s.save_advisory(office_id, payload, advisory_id)


@router.get("/offices/{office_id}/advisories")
def advisories(office_id: str, s: WorkspaceService = Depends(service)):
    s.membership(office_id)
    return list(s.db.scalars(select(AdvisoryVersion).join(Advisory).where(
        Advisory.office_id == office_id).order_by(AdvisoryVersion.created_at.desc())))


@router.post("/offices/{office_id}/advisories/{advisory_id}/transition")
def transition(office_id: str, advisory_id: str, payload: Transition, s: WorkspaceService = Depends(service)):
    return s.transition(office_id, advisory_id, payload)


@router.get("/offices/{office_id}/events")
def events(office_id: str, entity_id: str | None = None, s: WorkspaceService = Depends(service)):
    s.membership(office_id)
    query = select(WorkspaceEvent).where(WorkspaceEvent.office_id == office_id)
    if entity_id:
        query = query.where(WorkspaceEvent.entity_id == entity_id)
    return list(s.db.scalars(query.order_by(WorkspaceEvent.created_at)))


@router.get("/released")
def released(s: WorkspaceService = Depends(service)):
    return [public_version(v) for v in s.released()]


@router.get("/released/{version_id}")
def released_version(version_id: str, s: WorkspaceService = Depends(service)):
    return public_version(s.released(version_id))


@router.post("/released/{version_id}/audio")
def released_audio(version_id: str, language: str | None = Query(default=None),
                   s: WorkspaceService = Depends(service)):
    v = s.released(version_id)
    c = v.content
    language = language or c["language"]
    if language == c["language"]:
        text = "\n".join(r["action"] + ("\n" + r["basis"] if r.get("basis") else "") + "\n" + r["uncertainty"] for r in c["recommendations"])
        text += "\n" + c["missing_information"]
    elif language in c["translations"]:
        text = "\n".join(c["translations"][language])
    else:
        fail(422, "This language has no reviewed translation")
    started = perf_counter()
    office_id = s.db.get(Advisory, v.advisory_id).office_id
    try:
        audio = synthesize_speech(text, language_code=language)
    except Exception:
        s.event(office_id, v.advisory_id, "audio_failed", version_id=v.id, language=language)
        s.db.commit()
        fail(502, "Advisory audio is temporarily unavailable")
    s.event(office_id, v.advisory_id, "audio_generated", version_id=v.id, language=language,
            provider=get_settings().advisory_audio_provider, duration_ms=round((perf_counter() - started) * 1000))
    s.db.commit()
    return Response(content=audio, media_type="audio/wav" if get_settings().advisory_audio_provider == "local" else "audio/mpeg")
