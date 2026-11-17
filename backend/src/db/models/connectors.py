"""Durable connector definitions. Approved configuration bodies are immutable."""

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base
from src.db.models.workspace import uid, now


class RegistryGeneration(Base):
    __tablename__ = "connector_registry_generations"
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, default=1)


class Integration(Base):
    __tablename__ = "connector_integrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    adapter_type: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    config_revision: Mapped[int] = mapped_column(Integer, default=1)
    enabled_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health: Mapped[str] = mapped_column(String(40), default="NOT_TESTED")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class IntegrationVersion(Base):
    __tablename__ = "connector_integration_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    connection_id: Mapped[str] = mapped_column(ForeignKey("connector_integrations.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("connection_id", "revision"),)


class ConnectionCredential(Base):
    __tablename__ = "connector_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("connector_integrations.id"), unique=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    principal_scope: Mapped[str] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class RegisteredTool(Base):
    __tablename__ = "connector_tools"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("connector_integrations.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    enabled_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    revoked_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    __table_args__ = (UniqueConstraint("connection_id", "name"),)


class ToolVersion(Base):
    __tablename__ = "connector_tool_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tool_id: Mapped[str] = mapped_column(ForeignKey("connector_tools.id"), index=True)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    connection_revision: Mapped[int] = mapped_column(Integer)
    connection_digest: Mapped[str] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64))
    specification: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("tool_id", "version"),)


class DefinitionApproval(Base):
    __tablename__ = "connector_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(20))
    version_id: Mapped[str] = mapped_column(String(36), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    connection_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credential_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    test_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class ExecutionBudget(Base):
    __tablename__ = "connector_budgets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    max_calls: Mapped[int] = mapped_column(Integer, default=24)
    max_requests: Mapped[int] = mapped_column(Integer, default=80)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=4)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[object] = mapped_column(DateTime(timezone=True))
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)


class ConnectorJob(Base):
    __tablename__ = "connector_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    principal_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    kind: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_digest: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSON)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    budget_id: Mapped[str] = mapped_column(ForeignKey("connector_budgets.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("office_id", "request_key"),)


class ToolInvocation(Base):
    __tablename__ = "connector_invocations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    principal_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    tool_version_id: Mapped[str | None] = mapped_column(ForeignKey("connector_tool_versions.id"), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("connector_jobs.id"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("advisory_runs.id"), nullable=True)
    budget_id: Mapped[str] = mapped_column(ForeignKey("connector_budgets.id"))
    request_key: Mapped[str] = mapped_column(String(200))
    argument_digest: Mapped[str] = mapped_column(String(64))
    input_metadata: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), default="started")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("office_id", "request_key"),)


class InvocationAttempt(Base):
    __tablename__ = "connector_invocation_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invocation_id: Mapped[str] = mapped_column(ForeignKey("connector_invocations.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(10))
    origin_path: Mapped[str] = mapped_column(String(1000))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(40), default="DISPATCHED")
    elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("invocation_id", "ordinal"),)


class ConnectorCache(Base):
    __tablename__ = "connector_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    result: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))


class DiscoverySnapshot(Base):
    __tablename__ = "connector_discovery_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    connection_id: Mapped[str] = mapped_column(ForeignKey("connector_integrations.id"), index=True)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"))
    connection_revision: Mapped[int] = mapped_column(Integer)
    complete: Mapped[bool] = mapped_column(Boolean)
    catalog: Mapped[list] = mapped_column(JSON)
    diff: Mapped[dict] = mapped_column(JSON)
    diagnostics: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class RegisteredSkill(Base):
    __tablename__ = "connector_skills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    enabled_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("office_id", "name"),)


class SkillVersion(Base):
    __tablename__ = "connector_skill_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    skill_id: Mapped[str] = mapped_column(ForeignKey("connector_skills.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("skill_id", "version"),)


class PluginPack(Base):
    __tablename__ = "connector_plugin_packs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    resources: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    __table_args__ = (UniqueConstraint("office_id", "name", "version"),)
