from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import Field
from sqlalchemy import select
from src.api.routes.integrations import service
from src.db.models.connectors import RegisteredSkill, PluginPack
from src.integrations.contracts import Strict, SkillManifest, SkillRunRequest, Enabled, ConnectorError
from src.integrations.jobs import job_view
from src.skills.service import SkillService
from src.skills.plugins import PluginService, PackManifest, pack_view
from src.skills.builtin_pack import agriculture_pack

router = APIRouter(prefix="/api/v1", tags=["Skills and plugin packs"])


class SkillExact(Strict):
    version: int = Field(ge=1)
    digest: str = Field(min_length=64, max_length=64)
    request_key: str = Field(default="configuration-check", min_length=8, max_length=100)


class SkillRevision(Strict):
    expected_revision: int = Field(ge=1)
    manifest: SkillManifest


class PackExact(Strict):
    digest: str = Field(min_length=64, max_length=64)


class PackEnabled(PackExact):
    enabled: bool


def skills(s):
    return SkillService(s.db, s.principal)


@router.get("/skills")
def list_skills(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=Depends(service)):
    ss = skills(s)
    rows = s.db.scalars(
        select(RegisteredSkill)
        .where(RegisteredSkill.office_id == s.principal.office_id)
        .order_by(RegisteredSkill.name)
        .offset(offset)
        .limit(limit)
    )
    return {"items": [ss.skill_view(row, ss.version(row.id)[1]) for row in rows], "limit": limit, "offset": offset}


@router.post("/skills", status_code=201)
def create_skill(payload: SkillManifest, s=Depends(service)):
    ss = skills(s)
    skill, version = ss.create_skill(payload.model_dump(mode="json"))
    return ss.skill_view(skill, version)


@router.get("/skills/{skill_id}")
def skill_detail(skill_id: str, s=Depends(service)):
    ss = skills(s)
    skill, version = ss.version(skill_id)
    return ss.skill_view(skill, version)


@router.post("/skills/{skill_id}/versions", status_code=201)
def skill_version(skill_id: str, payload: SkillRevision, s=Depends(service)):
    ss = skills(s)
    old, _ = ss.version(skill_id)
    if payload.manifest.name != old.name:
        raise ConnectorError("VERSION_CONFLICT", "Stable skill name is immutable")
    skill, version = ss.create_skill(
        payload.manifest.model_dump(mode="json"), expected_revision=payload.expected_revision
    )
    return ss.skill_view(skill, version)


@router.post("/skills/{skill_id}/test", status_code=202)
def skill_test(skill_id: str, payload: SkillExact, s=Depends(service)):
    return job_view(skills(s).test_skill(skill_id, payload))


@router.post("/skills/{skill_id}/approve")
def approve_skill(skill_id: str, payload: SkillExact, s=Depends(service)):
    return skills(s).approve_skill(skill_id, payload)


@router.patch("/skills/{skill_id}/enabled")
def enable_skill(skill_id: str, payload: Enabled, s=Depends(service)):
    return skills(s).enable_skill(skill_id, payload)


@router.post("/skills/{skill_id}/runs", status_code=202)
def run_skill(skill_id: str, payload: SkillRunRequest, s=Depends(service)):
    return job_view(skills(s).queue_run(skill_id, payload))


@router.get("/plugins/templates/agriculture-core")
def builtin_template(s=Depends(service)):
    return agriculture_pack()


@router.get("/plugins")
def list_packs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=Depends(service)):
    rows = s.db.scalars(
        select(PluginPack)
        .where(PluginPack.office_id == s.principal.office_id)
        .order_by(PluginPack.name, PluginPack.version)
        .offset(offset)
        .limit(limit)
    )
    return {"items": [pack_view(row) for row in rows], "limit": limit, "offset": offset}


@router.post("/plugins", status_code=201)
def register_pack(payload: PackManifest, s=Depends(service)):
    return pack_view(PluginService(s.db, s.principal).register_pack(payload.model_dump(mode="json")))


@router.get("/plugins/{pack_id}")
def pack_detail(pack_id: str, s=Depends(service)):
    return pack_view(s.owned(PluginPack, pack_id))


@router.post("/plugins/{pack_id}/install")
def install_pack(pack_id: str, payload: PackExact, s=Depends(service)):
    return pack_view(PluginService(s.db, s.principal).install(pack_id, payload.digest))


@router.patch("/plugins/{pack_id}/enabled")
def enable_pack(pack_id: str, payload: PackEnabled, s=Depends(service)):
    return pack_view(PluginService(s.db, s.principal).enable_pack(pack_id, payload.digest, payload.enabled))


@router.post("/image-assets", status_code=201)
async def upload_image(image: UploadFile = File(...), s=Depends(service)):
    from src.services.image_asset_service import save_image, MAX_IMAGE_BYTES
    try:
        content = await image.read(MAX_IMAGE_BYTES + 1)
        return save_image(s.db, s.principal, content, image.content_type)
    finally:
        await image.close()


@router.get("/plugins/templates/verified-agriculture")
def verified_template(s=Depends(service)):
    from src.skills.verified_pack import verified_pack
    return verified_pack()
