from sqlalchemy import select
from src.db.models.connectors import RegisteredSkill, SkillVersion, DefinitionApproval, ConnectorJob, PluginPack
from src.integrations.contracts import SkillManifest, ConnectorError, digest, now
from src.integrations.service import IntegrationService, approval, audit, bump
from src.tools.policy import require_admin, authorized_plots
from src.tools.registry import Registry


def pack_allows(db, office_id, resource_id, kind):
    for pack in db.scalars(select(PluginPack).where(PluginPack.office_id == office_id, PluginPack.installed.is_(True))):
        if resource_id in pack.resources.get(kind, []) and not pack.enabled:
            raise ConnectorError("TOOL_REVOKED", "The owning plugin pack is disabled")


class SkillService(IntegrationService):
    def create_skill(self, manifest, *, expected_revision=None, commit=True):
        require_admin(self.principal)
        data = SkillManifest.model_validate(manifest).model_dump(mode="json")
        if len(set(data["required_capabilities"])) != len(data["required_capabilities"]):
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Required capabilities must be distinct")
        row = self.db.scalar(
            select(RegisteredSkill)
            .where(RegisteredSkill.office_id == self.principal.office_id, RegisteredSkill.name == data["name"])
            .with_for_update()
        )
        if row:
            if row.revision != expected_revision:
                raise ConnectorError("VERSION_CONFLICT", "A new skill version requires its current revision")
            row.current_version += 1
            row.revision += 1
        else:
            row = RegisteredSkill(office_id=self.principal.office_id, name=data["name"])
            self.db.add(row)
            self.db.flush()
        version = SkillVersion(
            skill_id=row.id,
            version=row.current_version,
            manifest=data,
            digest=digest(data),
            created_by=self.principal.user_id,
        )
        self.db.add(version)
        self.db.flush()
        audit(self.db, self.principal, row.id, "skill_version_created", version=version.version, digest=version.digest)
        bump(self.db, self.principal.office_id)
        if commit:
            self.db.commit()
        return row, version

    def version(self, skill_id, version=None):
        skill = self.owned(RegisteredSkill, skill_id)
        row = self.db.scalar(
            select(SkillVersion).where(
                SkillVersion.skill_id == skill.id, SkillVersion.version == (version or skill.current_version)
            )
        )
        if not row:
            raise ConnectorError("VERSION_CONFLICT", "Skill version not found")
        return skill, row

    def skill_view(self, skill, version, *, include_execution=False):
        result = {
            "id": skill.id,
            "name": skill.name,
            "revision": skill.revision,
            "version": version.version,
            "digest": version.digest,
            "version_id": version.id,
            "manifest": version.manifest,
            "enabled": skill.enabled,
            "enabled_version": skill.enabled_version,
            "approved": bool(approval(self.db, version.id, self.principal.office_id)),
        }
        if include_execution:
            from src.skills.projection import execution_view
            result["execution"] = execution_view(self, skill, version)
        return result

    def exact_skill(self, skill_id, version, expected_digest):
        skill, row = self.version(skill_id, version)
        if row.digest != expected_digest:
            raise ConnectorError("VERSION_CONFLICT", "Skill digest does not match the requested version")
        return skill, row

    def test_skill(self, skill_id, payload):
        require_admin(self.principal)
        skill, version = self.exact_skill(skill_id, payload.version, payload.digest)
        snapshot = Registry(self.db, self.principal).snapshot(skill_id, version=version.version, testing=True)
        # This is a real deterministic configuration check, explicitly not an LLM/provider execution.
        request = {"request_key": payload.request_key, "version": payload.version, "digest": payload.digest}
        job = self.create_job(
            "skill_validation", version.id, request, snapshot={"skill_id": skill.id, "digest": version.digest}
        )
        if job.status == "queued":
            job.status = "succeeded"
            job.updated_at = now()
            job.result = {
                "test_type": "configuration_validation",
                "provider_request_executed": False,
                "model_request_executed": False,
                "skill_digest": version.digest,
                "resolved_tool_versions": [tool["version_id"] for tool in snapshot["tools"]],
                "missing_optional_capabilities": snapshot["missing_optional_capabilities"],
            }
            audit(self.db, self.principal, job.id, "skill_configuration_tested", skill_version=version.version)
            self.db.commit()
        return job

    def approve_skill(self, skill_id, payload):
        require_admin(self.principal)
        skill, version = self.exact_skill(skill_id, payload.version, payload.digest)
        test = self.db.scalar(
            select(ConnectorJob)
            .where(
                ConnectorJob.office_id == self.principal.office_id,
                ConnectorJob.kind == "skill_validation",
                ConnectorJob.target_id == version.id,
                ConnectorJob.status == "succeeded",
            )
            .order_by(ConnectorJob.created_at.desc())
        )
        if not test:
            raise ConnectorError("APPROVAL_REQUIRED", "Validate this exact skill configuration before approval")
        self.db.add(
            DefinitionApproval(
                office_id=self.principal.office_id,
                entity_type="skill",
                version_id=version.id,
                digest=version.digest,
                reviewer_id=self.principal.user_id,
                test_id=test.id,
            )
        )
        audit(self.db, self.principal, skill.id, "skill_version_approved", version=version.version, test_id=test.id)
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return self.skill_view(skill, version)

    def enable_skill(self, skill_id, payload):
        require_admin(self.principal)
        skill = self.owned(RegisteredSkill, skill_id, lock=True)
        _, version = self.version(skill_id, payload.version)
        if skill.revision != payload.expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Skill changed; reload its revision")
        if payload.enabled:
            pack_allows(self.db, self.principal.office_id, skill.id, "skills")
            if not approval(self.db, version.id, self.principal.office_id):
                raise ConnectorError("APPROVAL_REQUIRED", "Approve this skill version before enabling it")
        skill.enabled = payload.enabled
        skill.enabled_version = version.version if payload.enabled else skill.enabled_version
        skill.revision += 1
        audit(self.db, self.principal, skill.id, "skill_enablement_changed", enabled=payload.enabled)
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return self.skill_view(skill, version)

    def queue_run(self, skill_id, payload):
        if self.principal.role == "viewer":
            raise ConnectorError("POLICY_DENIED", "Viewers cannot start investigations")
        pack_allows(self.db, self.principal.office_id, skill_id, "skills")
        authorized_plots(self.db, self.principal, payload.plot_ids)
        if payload.image_asset_id:
            from src.services.image_asset_service import owned_image
            owned_image(self.db, self.principal, payload.image_asset_id)
        if len(str(payload.parameters).encode()) > 8192:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Skill parameters exceed the input limit")
        snapshot = Registry(self.db, self.principal).snapshot(skill_id)
        return self.create_job("skill_run", skill_id, payload.model_dump(mode="json"), snapshot=snapshot)
