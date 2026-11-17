"""Configuration-only packs. Import/install never runs a program or contacts a provider."""

import json
from pydantic import Field
from sqlalchemy import select
from src.db.models.connectors import PluginPack, Integration, RegisteredSkill
from src.integrations.contracts import Strict, ConnectionSpec, ToolSpec, SkillManifest, ConnectorError, digest
from src.integrations.service import audit, bump
from src.skills.service import SkillService
from src.tools.policy import require_admin


class ConnectionTemplate(Strict):
    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    configuration: ConnectionSpec
    tools: list[ToolSpec] = Field(default_factory=list, max_length=32)


class PackManifest(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,30}$")
    version: int = Field(ge=1, le=9999)
    description: str = Field(min_length=1, max_length=2000)
    connections: list[ConnectionTemplate] = Field(default_factory=list, max_length=32)
    skills: list[SkillManifest] = Field(default_factory=list, max_length=32)


def pack_view(pack):
    return {
        "id": pack.id,
        "name": pack.name,
        "version": pack.version,
        "digest": pack.digest,
        "installed": pack.installed,
        "enabled": pack.enabled,
        "resources": pack.resources,
        "manifest": pack.manifest,
    }


class PluginService(SkillService):
    def register_pack(self, manifest):
        require_admin(self.principal)
        data = PackManifest.model_validate(manifest).model_dump(mode="json")
        if len(json.dumps(data).encode()) > 131072:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Plugin manifest exceeds 128 KiB")

        # Credentials cannot be shipped inside a pack, even as literal request values.
        def inspect(item):
            if isinstance(item, dict):
                for key, value in item.items():
                    if key.lower() in {
                        "code",
                        "command",
                        "shell",
                        "packages",
                        "python",
                        "password",
                        "api_key",
                        "token",
                        "secret",
                    }:
                        raise ConnectorError(
                            "POLICY_DENIED", "Pack contains executable configuration or embedded credentials"
                        )
                    inspect(value)
            elif isinstance(item, list):
                for value in item:
                    inspect(value)

        inspect(data)
        if len({entry["template_id"] for entry in data["connections"]}) != len(data["connections"]):
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Plugin template identifiers must be distinct")
        existing = self.db.scalar(
            select(PluginPack).where(
                PluginPack.office_id == self.principal.office_id,
                PluginPack.name == data["name"],
                PluginPack.version == data["version"],
            )
        )
        if existing:
            if existing.digest != digest(data):
                raise ConnectorError("VERSION_CONFLICT", "Pack version is immutable; publish a new version")
            return existing
        row = PluginPack(
            office_id=self.principal.office_id,
            name=data["name"],
            version=data["version"],
            manifest=data,
            digest=digest(data),
            created_by=self.principal.user_id,
        )
        self.db.add(row)
        self.db.flush()
        audit(self.db, self.principal, row.id, "plugin_pack_registered", digest=row.digest)
        self.db.commit()
        return row

    def install(self, pack_id, expected_digest):
        require_admin(self.principal)
        pack = self.owned(PluginPack, pack_id, lock=True)
        if pack.digest != expected_digest:
            raise ConnectorError("VERSION_CONFLICT", "Pack digest changed")
        if pack.installed:
            return pack
        resources = {"connections": [], "tools": [], "skills": []}
        try:
            for entry in pack.manifest["connections"]:
                configuration = dict(entry["configuration"])
                configuration["name"] = f"{pack.name} v{pack.version}: {configuration['name']}"
                connection = self.create(configuration, commit=False)
                resources["connections"].append(connection.id)
                for spec in entry["tools"]:
                    tool, _ = self.register_tool(connection.id, spec, commit=False)
                    resources["tools"].append(tool.id)
            for spec in pack.manifest["skills"]:
                manifest = dict(spec)
                manifest["name"] = f"{pack.name}_v{pack.version}_{manifest['name']}"
                if len(manifest["name"]) > 63:
                    raise ConnectorError("INPUT_VALIDATION_FAILED", "Namespaced skill name exceeds 63 characters")
                skill, _ = self.create_skill(manifest, commit=False)
                resources["skills"].append(skill.id)
            pack.resources = resources
            pack.installed = True
            pack.enabled = True
            audit(
                self.db,
                self.principal,
                pack.id,
                "plugin_pack_installed",
                resources=resources,
                automatic_enablement=False,
            )
            bump(self.db, self.principal.office_id)
            self.db.commit()
            return pack
        except BaseException:
            self.db.rollback()
            raise

    def enable_pack(self, pack_id, expected_digest, enabled):
        require_admin(self.principal)
        pack = self.owned(PluginPack, pack_id, lock=True)
        if pack.digest != expected_digest or not pack.installed:
            raise ConnectorError("VERSION_CONFLICT", "Install this exact pack version first")
        pack.enabled = enabled
        if not enabled:
            for connection_id in pack.resources.get("connections", []):
                row = self.owned(Integration, connection_id, lock=True)
                row.enabled = False
                row.revision += 1
            for skill_id in pack.resources.get("skills", []):
                row = self.owned(RegisteredSkill, skill_id, lock=True)
                row.enabled = False
                row.revision += 1
        audit(
            self.db,
            self.principal,
            pack.id,
            "plugin_pack_enablement_changed",
            enabled=enabled,
            restores_child_enablement=False,
        )
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return pack
