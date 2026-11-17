"""Idempotent reconciliation; credentials arrive only on protected stdin.

No network or model requests during registration. With live_test=true, each
explicit provider sample is tested once through the durable executor; only a
VALID live/fixture result can be approved/enabled. Existing unrelated work is retained.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from src.api.routes.skills import SkillExact
from src.db.models.connectors import ConnectorJob, Integration, RegisteredSkill, RegisteredTool
from src.db.session import SessionLocal
from src.integrations.contracts import ConnectorError, CredentialWrite, Enabled, ExactVersion, TestRequest, digest, now
from src.integrations.jobs import process_job
from src.integrations.service import IntegrationService, credential_scope
from src.providers.factory import template
from src.skills.service import SkillService
from src.skills.verified_pack import PROVIDERS, combined_skill, provider_skill
from src.tools.policy import principal_for, require_admin


def reconcile(actor, provider_id, credential=None):
    handler = PROVIDERS[provider_id][0]
    config = template(handler)
    with SessionLocal() as db:
        service = IntegrationService(db, actor)
        # Reuse an existing reviewed handler connection, preferring the enabled one.
        candidates = list(
            db.scalars(
                select(Integration)
                .where(Integration.office_id == actor.office_id)
                .order_by(Integration.enabled.desc(), Integration.created_at)
            )
        )
        connection = next((c for c in candidates if service.config(c).configuration.get("handler_id") == handler), None)
        if connection is None:
            connection = service.create(config["connection"])
        if credential is not None:
            from src.db.models.connectors import ConnectionCredential
            from src.integrations.secrets import decrypt

            stored = db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
            if not stored or decrypt(stored, actor.office_id, connection.id) != credential:
                service.credential(
                    connection.id,
                    CredentialWrite(value=credential, principal_scope="operator-verified-provider-account"),
                )
        operation = config["operations"][0]
        operation["policy"]["cache_ttl_seconds"] = (
            0 if provider_id == "kindwise" else 3600 if provider_id == "open_meteo" else 86400
        )
        tool = db.scalar(
            select(RegisteredTool).where(
                RegisteredTool.connection_id == connection.id, RegisteredTool.name == operation["name"]
            )
        )
        version = service.tool_version(connection.id, tool.id)[1] if tool else None
        if (
            not version
            or version.specification != operation
            or version.connection_revision != service.config(connection).revision
        ):
            tool, version = service.register_tool(
                connection.id, operation, expected_revision=tool.revision if tool else None
            )
        ss = SkillService(db, actor)
        manifest = provider_skill(provider_id)
        skill = db.scalar(
            select(RegisteredSkill).where(
                RegisteredSkill.office_id == actor.office_id, RegisteredSkill.name == manifest["name"]
            )
        )
        # Pydantic fills defaults before equality comparison to avoid spurious versions.
        from src.integrations.contracts import SkillManifest

        manifest = SkillManifest.model_validate(manifest).model_dump(mode="json")
        sv = ss.version(skill.id)[1] if skill else None
        if not sv or sv.manifest != manifest:
            skill, sv = ss.create_skill(manifest, expected_revision=skill.revision if skill else None)
        return {
            "provider_id": provider_id,
            "connection_id": connection.id,
            "tool_id": tool.id,
            "tool_version_id": version.id,
            "skill_id": skill.id,
            "implemented": True,
            "enabled": connection.enabled and tool.enabled and tool.enabled_version == version.version,
            "backend_live_test": "NOT_RUN_BY_REGISTRATION",
        }


async def activate(actor, row, sample, *, authorize_credit_use=False):
    if row["provider_id"] == "kindwise" and not authorize_credit_use:
        return {**row, "backend_live_test": "BLOCKED_CREDIT_AUTHORIZATION"}
    with SessionLocal() as db:
        service = IntegrationService(db, actor)
        conn = service.owned(Integration, row["connection_id"])
        tool, version = service.tool_version(conn.id, row["tool_id"])
        exact = ExactVersion(
            version=version.version, connection_revision=version.connection_revision, digest=version.digest
        )
        test = TestRequest(
            **exact.model_dump(),
            arguments=sample.get("arguments", {}),
            plot_ids=sample.get("plot_ids", []),
            authorize_network=True,
            authorize_credit_use=authorize_credit_use,
            request_key=f"verified:{version.id}:{credential_scope(db, conn)[:8]}:{now():%Y%m%d}:{digest(sample)[:8]}",
        )
        job = service.queue_tool_test(conn.id, tool.id, test)
        job_id = job.id
    await process_job(job_id)
    # Another worker can claim it. Bound polling; never submit a second job.
    until = time.monotonic() + 250
    while True:
        with SessionLocal() as db:
            job = db.get(ConnectorJob, job_id)
            if job.status not in ("queued", "running"):
                result = job.result or {}
                if job.status != "succeeded" or result.get("data_outcome") != "VALID":
                    return {
                        **row,
                        "backend_live_test": result.get("execution_outcome", job.status),
                        "data_outcome": result.get("data_outcome"),
                        "job_id": job_id,
                        "enabled": row["enabled"],
                    }
                service = IntegrationService(db, actor)
                service.approve_tool(row["connection_id"], row["tool_id"], exact)
                tool, _ = service.tool_version(row["connection_id"], row["tool_id"])
                service.set_tool_enabled(
                    row["connection_id"],
                    row["tool_id"],
                    Enabled(enabled=True, expected_revision=tool.revision, version=exact.version),
                )
                conn = service.owned(Integration, row["connection_id"])
                service.set_enabled(
                    conn.id, Enabled(enabled=True, expected_revision=conn.revision, version=exact.connection_revision)
                )
                ss = SkillService(db, actor)
                skill, sv = ss.version(row["skill_id"])
                payload = SkillExact(
                    version=sv.version, digest=sv.digest, request_key=f"verify-skill:{sv.id}:{exact.digest[:8]}"
                )
                ss.test_skill(skill.id, payload)
                ss.approve_skill(skill.id, payload)
                ss.enable_skill(skill.id, Enabled(enabled=True, expected_revision=skill.revision, version=sv.version))
                return {
                    **row,
                    "backend_live_test": "VALID",
                    "classification": result.get("classification"),
                    "job_id": job_id,
                    "evidence_ids": result.get("evidence_ids", []),
                    "enabled": True,
                }
        if time.monotonic() >= until:
            return {**row, "backend_live_test": "PENDING_WORKER", "job_id": job_id}
        await asyncio.sleep(1)


async def run(request):
    with SessionLocal() as db:
        actor = principal_for(db, request["principal_id"])
        require_admin(actor)
    selected = request.get("providers", list(PROVIDERS))
    if set(selected) - set(PROVIDERS):
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Unknown verified provider")
    rows = []
    for provider_id in selected:
        try:
            row = reconcile(actor, provider_id, request.get("credentials", {}).get(provider_id))
            if request.get("live_test") and provider_id in request.get("samples", {}):
                row = await activate(
                    actor,
                    row,
                    request["samples"][provider_id],
                    authorize_credit_use=request.get("authorize_credit_use", False),
                )
            rows.append(row)
        except ConnectorError as error:
            rows.append({"provider_id": provider_id, "error": error.as_dict(), "enabled": False})
    with SessionLocal() as db:
        ss = SkillService(db, actor)
        manifest = combined_skill()
        existing = db.scalar(
            select(RegisteredSkill).where(
                RegisteredSkill.office_id == actor.office_id, RegisteredSkill.name == manifest["name"]
            )
        )
        if not existing:
            existing, _ = ss.create_skill(manifest)
        combined = {"skill_id": existing.id, "enabled": existing.enabled}
        if request.get("live_test"):
            try:
                skill, version = ss.version(existing.id)
                payload = SkillExact(
                    version=version.version,
                    digest=version.digest,
                    request_key=f"verify-combined:{version.id}:{now().timestamp()}",
                )
                ss.test_skill(skill.id, payload)
                ss.approve_skill(skill.id, payload)
                ss.enable_skill(
                    skill.id, Enabled(enabled=True, expected_revision=skill.revision, version=version.version)
                )
                combined["enabled"] = True
            except ConnectorError as error:
                combined["error"] = error.as_dict()
    return {
        "generated_at": now().isoformat(),
        "providers": rows,
        "combined_skill": combined,
        "model_requests": 0,
        "farmer_delivery_performed": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(run(json.load(sys.stdin))), indent=2))
    except Exception as error:  # noqa: BLE001 -- never expose secret-bearing setup exceptions
        # Never print an exception body that may contain credential-bearing input.
        print(
            json.dumps(
                {
                    "error": error.as_dict()
                    if isinstance(error, ConnectorError)
                    else {
                        "code": "SETUP_FAILED",
                        "message": "Setup failed; input values were withheld",
                        "type": type(error).__name__,
                    }
                }
            )
        )
        raise SystemExit(1) from None
