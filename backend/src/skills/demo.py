"""Evidence first, optional AI second, using the existing approved executor and durable jobs."""

from datetime import date

from pydantic import Field
from sqlalchemy import select

from src.db.models.connectors import ConnectorJob
from src.integrations.contracts import ConnectorError, Strict
from src.integrations.service import IntegrationService
from src.tools.policy import authorized_locations, principal_for
from src.tools.registry import Registry

DEMO_CAPABILITIES = {"crop.diagnosis", "rainfall.history"}


class EvidenceRequest(Strict):
    request_key: str = Field(min_length=8, max_length=100)
    plot_ids: list[str] = Field(default_factory=list, max_length=1)
    territory_id: str | None = None
    image_asset_id: str | None = Field(default=None, min_length=36, max_length=36)
    start: date | None = None
    end: date | None = None
    authorize_network: bool = False
    authorize_credit_use: bool = False


class ExplainRequest(Strict):
    evidence_job_id: str
    task: str = Field(min_length=3, max_length=2000)
    request_key: str = Field(min_length=8, max_length=100)
    authorize_model: bool = False


def demo_snapshot(db, principal, skill_id):
    if principal.role not in ("office_admin", "extension_officer"):
        raise ConnectorError("POLICY_DENIED", "An officer is required to run skills")
    snapshot = Registry(db, principal).snapshot(skill_id)
    required = set(snapshot["manifest"]["required_capabilities"])
    if len(required) != 1 or not required <= DEMO_CAPABILITIES or snapshot["manifest"]["allowed_internal_actions"]:
        raise ConnectorError("POLICY_DENIED", "Choose a crop-photo or rainfall-history skill")
    tools = [t for t in snapshot["tools"] if set(t["capability_tags"]) == required]
    if len(tools) != 1:
        raise ConnectorError("POLICY_DENIED", "This workflow needs one approved provider tool")
    return {**snapshot, "tools": tools}, next(iter(required))


def queue_evidence(service, skill_id, payload):
    snapshot, capability = demo_snapshot(service.db, service.principal, skill_id)
    if not payload.authorize_network:
        raise ConnectorError("POLICY_DENIED", "Authorize the provider request before continuing")
    if capability == "crop.diagnosis":
        if payload.territory_id or payload.start or payload.end:
            raise ConnectorError(
                "INPUT_VALIDATION_FAILED", "Photo assessment uses an image and optional registered farm"
            )
        if not payload.image_asset_id or not payload.authorize_credit_use:
            raise ConnectorError("POLICY_DENIED", "Upload a plant photo and authorize one diagnosis credit")
        from src.services.image_asset_service import owned_image

        owned_image(service.db, service.principal, payload.image_asset_id)
    else:
        if not payload.territory_id or payload.plot_ids or payload.image_asset_id:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Rainfall requires an assigned territory")
        if not payload.start or not payload.end or not 27 <= (payload.end - payload.start).days <= 30:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Select one month of past daily rainfall (28–31 days)")
        from src.providers.agriculture import date_range

        date_range({"start": str(payload.start), "end": str(payload.end)})
    authorized_locations(service.db, service.principal, payload.plot_ids, payload.territory_id)
    request = {
        **payload.model_dump(mode="json"),
        "workflow_phase": "evidence",
        "authorize_model": False,
        "task": "Collect photo assessment" if capability == "crop.diagnosis" else "Collect monthly rainfall",
        "parameters": {"start": str(payload.start), "end": str(payload.end)} if payload.start else {},
    }
    return service.create_job("skill_run", skill_id, request, snapshot=snapshot)


def evidence_source(db, principal, job_id, skill_id):
    source = IntegrationService(db, principal).owned(ConnectorJob, job_id)
    if source.target_id != skill_id or source.kind != "skill_run" or source.request.get("workflow_phase") != "evidence":
        raise ConnectorError("POLICY_DENIED", "Use an evidence report from this skill")
    if source.status not in ("succeeded", "partial") or not (source.result or {}).get("evidence_ids"):
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Wait for valid provider evidence before asking AI")
    authorized_locations(db, principal, source.request.get("plot_ids", []), source.request.get("territory_id"))
    return source


def queue_explanation(service, skill_id, payload):
    if not payload.authorize_model:
        raise ConnectorError("POLICY_DENIED", "Authorize the configured AI model")
    snapshot, _ = demo_snapshot(service.db, service.principal, skill_id)
    source = evidence_source(service.db, service.principal, payload.evidence_job_id, skill_id)
    from src.config.settings import get_settings

    if get_settings().cloud_model_data_policy == "environment_only":
        from src.agent.companion.environment_policy import scope_environment_snapshot

        snapshot = scope_environment_snapshot(snapshot)
    request = {
        **payload.model_dump(),
        "workflow_phase": "explanation",
        "plot_ids": source.request.get("plot_ids", []),
        "territory_id": source.request.get("territory_id"),
        "parameters": {},
        "authorize_network": False,
        "authorize_credit_use": False,
    }
    return service.create_job("skill_run", skill_id, request, snapshot=snapshot)


async def execute_evidence(job, principal, lease_token):
    from src.db.session import SessionLocal
    from src.tools.executor import ToolExecutor

    with SessionLocal() as db:
        current = principal_for(db, principal.user_id)
        fresh, capability = demo_snapshot(db, current, job.target_id)
        if fresh["skill_version_id"] != job.snapshot["skill_version_id"] or fresh["tools"] != job.snapshot["tools"]:
            raise ConnectorError("VERSION_CONFLICT", "Skill version changed; review it before executing")
        authorized_locations(db, current, job.request.get("plot_ids", []), job.request.get("territory_id"))
        reused = None
        if capability == "crop.diagnosis":
            from src.db.models.connectors import ToolInvocation
            from src.db.models.image_asset import DiagnosisReceipt
            from src.db.models.workspace import WorkspaceRecord
            from src.registry.access import guard_record
            from src.services.image_asset_service import owned_image

            asset = owned_image(db, current, job.request.get("image_asset_id"))
            receipt = db.scalar(
                select(DiagnosisReceipt).where(
                    DiagnosisReceipt.office_id == current.office_id,
                    DiagnosisReceipt.image_sha256 == asset.sha256,
                    DiagnosisReceipt.provider == "kindwise",
                    DiagnosisReceipt.state == "completed",
                )
            )
            prior = db.get(ToolInvocation, receipt.invocation_id) if receipt else None
            if (
                prior
                and prior.principal_id == current.user_id
                and prior.tool_version_id == fresh["tools"][0]["version_id"]
                and prior.input_metadata.get("credential_scope") == fresh["tools"][0]["credential_scope_digest"]
                and prior.status == "SUCCESS"
                and (prior.result or {}).get("data_outcome") == "VALID"
                and prior.result.get("evidence_ids")
            ):
                for ident in prior.result["evidence_ids"]:
                    evidence = db.get(WorkspaceRecord, ident)
                    if not evidence or evidence.office_id != current.office_id or evidence.kind != "evidence":
                        raise ConnectorError("POLICY_DENIED", "Saved photo evidence is unavailable")
                    guard_record(db, current, evidence)
                reused = {**prior.result, "cache_hit": True, "reused_diagnosis": True}
    tool = job.snapshot["tools"][0]
    outcome = reused or await ToolExecutor().execute(
        tool["version_id"],
        job.request.get("parameters", {}),
        principal,
        budget_id=job.budget_id,
        request_key=job.id + ":evidence",
        job_id=job.id,
        plot_ids=job.request.get("plot_ids", []),
        mode="runtime",
        lease_token=lease_token,
        authorize_network=True,
        authorize_credit_use=job.request.get("authorize_credit_use", False),
    )
    evidence_ids = outcome.get("evidence_ids", [])
    completed = outcome.get("execution_outcome") == "SUCCESS" and outcome.get("data_outcome") == "VALID"
    return {
        "status": "completed" if completed else "partial",
        "answer": "Provider evidence collected. Review the results or choose Ask AI."
        if evidence_ids
        else "No valid provider evidence was returned. Inspect the recorded error.",
        "evidence_ids": evidence_ids,
        "outcomes": [outcome],
        "skill_version": job.snapshot["skill_version"],
        "model": {"provider": "none", "model_request_executed": False},
        "delivery_performed": False,
    }
