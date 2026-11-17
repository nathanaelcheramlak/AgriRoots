"""Operator-only, no-network registration through the existing application services.

Input is JSON on protected stdin: manifest, optional principal_id, and optional
connection credentials. No credential is accepted in command arguments or output.
The explicit bootstrap_empty_local option is restricted to an entirely empty DB.
It creates an office-only local service identity with no global administrator role
and no known interactive password. It never inserts completed integration records.
"""

import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, func, text  # noqa: E402
from src.auth.password import hash_password  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402
from src.db.models.user import User, UserProfile  # noqa: E402
from src.db.models.workspace import Office, Membership, WorkspaceEvent  # noqa: E402
from src.db.models.connectors import Integration, ConnectionCredential  # noqa: E402
from src.integrations.contracts import CredentialWrite, ConnectorError, now  # noqa: E402
from src.integrations.secrets import decrypt  # noqa: E402
from src.skills.plugins import PluginService, PackManifest  # noqa: E402
from src.tools.policy import principal_for, require_admin  # noqa: E402


def select_actor(db, request):
    if request.get("principal_id"):
        actor = principal_for(db, request["principal_id"])
        require_admin(actor)
        return actor, False
    administrators = list(db.scalars(select(Membership).where(Membership.role.in_(["administrator", "office_admin"]))))
    if len(administrators) == 1:
        return principal_for(db, administrators[0].user_id), False
    if administrators or not request.get("bootstrap_empty_local"):
        raise ConnectorError(
            "POLICY_DENIED", "Choose an existing office administrator; empty-local bootstrap must be explicit"
        )
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(18472005)"))
    if any(db.scalar(select(func.count()).select_from(model)) for model in [User, Office, Membership]):
        raise ConnectorError("POLICY_DENIED", "Local bootstrap is refused for a nonempty database")
    user = User(phone_number="local-" + uuid4().hex[:12], password_hash=hash_password(secrets.token_urlsafe(40)))
    office = Office(name="AgriLo local API workspace")
    db.add_all([user, office])
    db.flush()
    db.add(UserProfile(user_id=user.user_id, full_name="Local API setup service identity"))
    db.add(Membership(office_id=office.id, user_id=user.user_id, role="administrator"))
    db.add(
        WorkspaceEvent(
            office_id=office.id,
            actor_id=user.user_id,
            entity_id=office.id,
            action="local_api_workspace_initialized",
            details={
                "operator_local_bootstrap": True,
                "global_administrator_granted": False,
                "interactive_password_saved": False,
            },
        )
    )
    db.commit()
    return principal_for(db, user.user_id), True


def register(request):
    manifest = PackManifest.model_validate(request["manifest"]).model_dump(mode="json")
    supplied = request.get("credentials", {})
    if set(supplied) - {entry["template_id"] for entry in manifest["connections"]}:
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Credential target is not a connection in this manifest")
    with SessionLocal() as db:
        actor, created = select_actor(db, request)
        service = PluginService(db, actor)
        pack = service.register_pack(manifest)
        pack = service.install(pack.id, pack.digest)
        connections = []
        for entry, ident in zip(pack.manifest["connections"], pack.resources["connections"], strict=True):
            provider = entry["template_id"]
            connection = service.owned(Integration, ident)
            stored = db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == ident))
            changed = False
            if provider in supplied:
                payload = CredentialWrite.model_validate(supplied[provider])
                if (
                    not stored
                    or stored.principal_scope != payload.principal_scope
                    or decrypt(stored, actor.office_id, ident) != payload.value
                ):
                    service.credential(ident, payload)
                    changed = True
                stored = db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == ident))
            views = service.view(connection)
            connections.append(
                {
                    "provider_id": provider,
                    "connection_id": ident,
                    "adapter_type": connection.adapter_type,
                    "enabled": connection.enabled,
                    "credential_stored": bool(stored),
                    "credential_changed": changed,
                    "credential_revision": stored.revision if stored else None,
                    "configuration_revision": views["config_revision"],
                    "registration_state": "DISABLED_DRAFT",
                    "current_provider_verification": "NOT_TESTED_BY_REGISTRATION",
                }
            )
        skills = []
        for ident in pack.resources["skills"]:
            skill, version = service.version(ident)
            skills.append(
                {
                    "skill_id": skill.id,
                    "name": skill.name,
                    "enabled": skill.enabled,
                    "approved": service.skill_view(skill, version)["approved"],
                    "required_capabilities": version.manifest["required_capabilities"],
                }
            )
        return {
            "registered_at_utc": now().isoformat(),
            "type": "ACTUAL_LOCAL_DATABASE_REGISTRATION",
            "office_id": actor.office_id,
            "principal_id": actor.user_id,
            "local_workspace_created": created,
            "pack_id": pack.id,
            "pack_name": pack.name,
            "pack_version": pack.version,
            "pack_digest": pack.digest,
            "installed": pack.installed,
            "connections": connections,
            "skills": skills,
            "tool_count": len(pack.resources["tools"]),
            "provider_requests": 0,
            "model_requests": 0,
            "paid_requests": 0,
            "automatic_approval": False,
            "next_steps": "Exact-version tests, review and enablement are still required. MCP discovery, WaPOR raster transport and the private image workflow remain separate.",
        }


def main():
    try:
        print(json.dumps(register(json.load(sys.stdin)), ensure_ascii=True, indent=2))
    except ConnectorError as error:
        print(json.dumps({"error": error.as_dict()}))
        raise SystemExit(1) from None
    except Exception as error:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "REGISTRATION_FAILED",
                        "type": type(error).__name__,
                        "message": "Local registration failed; secret-bearing input was not printed",
                    }
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
