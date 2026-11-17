"""Database-authoritative snapshots: a new approved tool needs neither graph edits nor process restarts."""

from sqlalchemy import select
from src.config.settings import get_settings
from src.db.models.connectors import (
    RegistryGeneration,
    Integration,
    IntegrationVersion,
    RegisteredTool,
    ToolVersion,
    RegisteredSkill,
    SkillVersion,
)
from src.integrations.contracts import ConnectorError, digest, now
from datetime import timedelta
from src.integrations.service import approval, credential_scope
from src.integrations.schema_translation import model_schema
from src.tools.policy import principal_for


def alias(version_id):
    return "tool_" + version_id.replace("-", "")


class Registry:
    def __init__(self, db, principal):
        self.db, self.principal = db, principal_for(db, principal.user_id)
        if self.principal.office_id != principal.office_id:
            raise ConnectorError("POLICY_DENIED", "Office membership changed")

    def tools(self, capabilities):
        capabilities = set(capabilities)
        eligible = []
        query = (
            select(RegisteredTool, Integration)
            .join(Integration, Integration.id == RegisteredTool.connection_id)
            .where(
                RegisteredTool.office_id == self.principal.office_id,
                Integration.office_id == self.principal.office_id,
                RegisteredTool.enabled.is_(True),
                Integration.enabled.is_(True),
                RegisteredTool.revoked_reason.is_(None),
            )
        )
        for tool, connection in self.db.execute(query):
            version = self.db.scalar(
                select(ToolVersion).where(ToolVersion.tool_id == tool.id, ToolVersion.version == tool.enabled_version)
            )
            if not version or version.connection_revision != connection.enabled_revision:
                continue
            spec = version.specification
            if self.principal.role not in spec.get("allowed_roles", ["office_admin", "extension_officer"]):
                continue
            if not capabilities.intersection(spec["capability_tags"]):
                continue
            if not approval(
                self.db,
                version.id,
                self.principal.office_id,
                connection_digest=version.connection_digest,
                credential_scope=credential_scope(self.db, connection),
            ):
                continue
            config = self.db.scalar(
                select(IntegrationVersion).where(
                    IntegrationVersion.connection_id == connection.id,
                    IntegrationVersion.revision == version.connection_revision,
                )
            )
            eligible.append(
                {
                    "alias": alias(version.id),
                    "version_id": version.id,
                    "tool_id": tool.id,
                    "connection_id": connection.id,
                    "connection_revision": version.connection_revision,
                    "credential_scope_digest": credential_scope(self.db, connection),
                    "configuration_digest": version.connection_digest,
                    "digest": version.digest,
                    "capability_tags": spec["capability_tags"],
                    "description": spec["description"],
                    "input_schema": model_schema(spec),
                    "effect_classification": spec["effect_classification"],
                    "priority": config.configuration.get("priority", 100),
                }
            )
        return sorted(eligible, key=lambda item: (item["priority"], item["tool_id"]))

    def snapshot(self, skill_id, *, version=None, testing=False):
        skill = self.db.get(RegisteredSkill, skill_id)
        if not skill or skill.office_id != self.principal.office_id:
            raise ConnectorError("POLICY_DENIED", "Skill is outside the authenticated office")
        if not testing and not skill.enabled:
            raise ConnectorError("TOOL_REVOKED", "Skill is disabled")
        from src.skills.service import pack_allows

        pack_allows(self.db, self.principal.office_id, skill.id, "skills")
        version = self.db.scalar(
            select(SkillVersion).where(
                SkillVersion.skill_id == skill.id,
                SkillVersion.version == (version or skill.enabled_version or skill.current_version),
            )
        )
        if not version:
            raise ConnectorError("VERSION_CONFLICT", "Skill version not found")
        if not testing and not approval(self.db, version.id, self.principal.office_id):
            raise ConnectorError("APPROVAL_REQUIRED", "Skill version is not approved")
        generation = self.db.get(RegistryGeneration, self.principal.office_id)
        cache_key = digest(
            {
                "registry": True,
                "office": self.principal.office_id,
                "role": self.principal.role,
                "generation": generation.generation if generation else 0,
                "skill_version_id": version.id,
            }
        )
        from src.tools import cache

        saved = cache.get(cache_key) if not testing else None
        if saved:
            return saved
        manifest = version.manifest
        required = manifest["required_capabilities"]
        optional = manifest["optional_capabilities"]
        allowed = required + optional + manifest["allowed_internal_actions"]
        candidates = self.tools(allowed)
        selected = []
        for capability in allowed:
            match = next((tool for tool in candidates if capability in tool["capability_tags"]), None)
            if match and match not in selected:
                selected.append(match)
        missing = [
            capability for capability in required if not any(capability in t["capability_tags"] for t in selected)
        ]
        if missing:
            raise ConnectorError(
                "AUTH_REQUIRED", "No approved enabled tool for required capabilities: " + ", ".join(missing)
            )
        maximum = get_settings().connector_max_model_tools
        if len(selected) > maximum:
            raise ConnectorError("BUDGET_EXCEEDED", "Skill needs more model-visible tools than the configured cap")
        result = {
            "generation": generation.generation if generation else 0,
            "skill_id": skill.id,
            "skill_version": version.version,
            "skill_version_id": version.id,
            "skill_digest": version.digest,
            "manifest": manifest,
            "tools": selected,
            "missing_optional_capabilities": [
                cap for cap in optional if not any(cap in t["capability_tags"] for t in selected)
            ],
        }
        if not testing:
            cache.put(cache_key, result, now() + timedelta(minutes=5))
        return result
