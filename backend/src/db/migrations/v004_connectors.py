"""Revision 4: frozen additive connector schema; existing tables and records are retained."""

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    ForeignKey,
    UniqueConstraint,
    String,
    Text,
    Integer,
    DateTime,
    JSON,
    Float,
    Boolean,
)

metadata = MetaData()
Table("users", metadata, Column("user_id", String(36), primary_key=True))
Table("offices", metadata, Column("id", String(36), primary_key=True))
Table("advisory_runs", metadata, Column("id", String(36), primary_key=True))

Table(
    "connector_approvals",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("entity_type", String(length=20), nullable=False),
    Column("version_id", String(length=36), nullable=False, index=True),
    Column("digest", String(length=64), nullable=False),
    Column("connection_digest", String(length=64), nullable=True),
    Column("credential_scope", String(length=64), nullable=True),
    Column("reviewer_id", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("test_id", String(length=36), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Table(
    "connector_budgets",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("max_calls", Integer(), nullable=False),
    Column("max_requests", Integer(), nullable=False),
    Column("max_concurrency", Integer(), nullable=False),
    Column("calls", Integer(), nullable=False),
    Column("requests", Integer(), nullable=False),
    Column("active", Integer(), nullable=False),
    Column("deadline", DateTime(timezone=True), nullable=False),
    Column("cancelled", Boolean(), nullable=False),
)

Table(
    "connector_cache",
    metadata,
    Column("key", String(length=64), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("result", JSON(), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

Table(
    "connector_integrations",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("name", String(length=200), nullable=False),
    Column("adapter_type", String(length=20), nullable=False),
    Column("revision", Integer(), nullable=False),
    Column("config_revision", Integer(), nullable=False),
    Column("enabled_revision", Integer(), nullable=True),
    Column("enabled", Boolean(), nullable=False),
    Column("health", String(length=40), nullable=False),
    Column("created_by", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Table(
    "connector_plugin_packs",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("name", String(length=64), nullable=False),
    Column("version", Integer(), nullable=False),
    Column("manifest", JSON(), nullable=False),
    Column("digest", String(length=64), nullable=False),
    Column("installed", Boolean(), nullable=False),
    Column("enabled", Boolean(), nullable=False),
    Column("resources", JSON(), nullable=False),
    Column("created_by", String(length=36), ForeignKey("users.user_id"), nullable=False),
    UniqueConstraint("office_id", "name", "version"),
)

Table(
    "connector_registry_generations",
    metadata,
    Column("office_id", String(length=36), ForeignKey("offices.id"), primary_key=True, nullable=False),
    Column("generation", Integer(), nullable=False),
)

Table(
    "connector_skills",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("name", String(length=64), nullable=False),
    Column("current_version", Integer(), nullable=False),
    Column("enabled_version", Integer(), nullable=True),
    Column("revision", Integer(), nullable=False),
    Column("enabled", Boolean(), nullable=False),
    UniqueConstraint("office_id", "name"),
)

Table(
    "connector_credentials",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("connection_id", String(length=36), ForeignKey("connector_integrations.id"), nullable=False),
    Column("ciphertext", Text(), nullable=False),
    Column("principal_scope", String(length=200), nullable=False),
    Column("revision", Integer(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("connection_id"),
)

Table(
    "connector_discovery_snapshots",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("connection_id", String(length=36), ForeignKey("connector_integrations.id"), nullable=False, index=True),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False),
    Column("connection_revision", Integer(), nullable=False),
    Column("complete", Boolean(), nullable=False),
    Column("catalog", JSON(), nullable=False),
    Column("diff", JSON(), nullable=False),
    Column("diagnostics", JSON(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Table(
    "connector_integration_versions",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("connection_id", String(length=36), ForeignKey("connector_integrations.id"), nullable=False, index=True),
    Column("revision", Integer(), nullable=False),
    Column("digest", String(length=64), nullable=False),
    Column("configuration", JSON(), nullable=False),
    Column("created_by", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("connection_id", "revision"),
)

Table(
    "connector_jobs",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("principal_id", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("kind", String(length=30), nullable=False),
    Column("target_id", String(length=36), nullable=False, index=True),
    Column("request_key", String(length=100), nullable=False),
    Column("request_digest", String(length=64), nullable=False),
    Column("request", JSON(), nullable=False),
    Column("snapshot", JSON(), nullable=False),
    Column("budget_id", String(length=36), ForeignKey("connector_budgets.id"), nullable=False),
    Column("status", String(length=30), nullable=False, index=True),
    Column("result", JSON(), nullable=True),
    Column("error", JSON(), nullable=True),
    Column("lease_token", String(length=64), nullable=True),
    Column("lease_until", DateTime(timezone=True), nullable=True),
    Column("attempts", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("office_id", "request_key"),
)

Table(
    "connector_skill_versions",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("skill_id", String(length=36), ForeignKey("connector_skills.id"), nullable=False, index=True),
    Column("version", Integer(), nullable=False),
    Column("manifest", JSON(), nullable=False),
    Column("digest", String(length=64), nullable=False),
    Column("created_by", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("skill_id", "version"),
)

Table(
    "connector_tools",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("connection_id", String(length=36), ForeignKey("connector_integrations.id"), nullable=False, index=True),
    Column("name", String(length=64), nullable=False),
    Column("current_version", Integer(), nullable=False),
    Column("enabled_version", Integer(), nullable=True),
    Column("enabled", Boolean(), nullable=False),
    Column("revision", Integer(), nullable=False),
    Column("revoked_reason", String(length=200), nullable=True),
    UniqueConstraint("connection_id", "name"),
)

Table(
    "connector_tool_versions",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("tool_id", String(length=36), ForeignKey("connector_tools.id"), nullable=False, index=True),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("version", Integer(), nullable=False),
    Column("connection_revision", Integer(), nullable=False),
    Column("connection_digest", String(length=64), nullable=False),
    Column("digest", String(length=64), nullable=False),
    Column("specification", JSON(), nullable=False),
    Column("created_by", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("tool_id", "version"),
)

Table(
    "connector_invocations",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("office_id", String(length=36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("principal_id", String(length=36), ForeignKey("users.user_id"), nullable=False),
    Column("tool_version_id", String(length=36), ForeignKey("connector_tool_versions.id"), nullable=True),
    Column("job_id", String(length=36), ForeignKey("connector_jobs.id"), nullable=True, index=True),
    Column("run_id", String(length=36), ForeignKey("advisory_runs.id"), nullable=True),
    Column("budget_id", String(length=36), ForeignKey("connector_budgets.id"), nullable=False),
    Column("request_key", String(length=200), nullable=False),
    Column("argument_digest", String(length=64), nullable=False),
    Column("input_metadata", JSON(), nullable=False),
    Column("status", String(length=40), nullable=False),
    Column("result", JSON(), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("office_id", "request_key"),
)

Table(
    "connector_invocation_attempts",
    metadata,
    Column("id", String(length=36), primary_key=True, nullable=False),
    Column("invocation_id", String(length=36), ForeignKey("connector_invocations.id"), nullable=False, index=True),
    Column("ordinal", Integer(), nullable=False),
    Column("method", String(length=10), nullable=False),
    Column("origin_path", String(length=1000), nullable=False),
    Column("status_code", Integer(), nullable=True),
    Column("outcome", String(length=40), nullable=False),
    Column("elapsed_ms", Float(), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("invocation_id", "ordinal"),
)


def upgrade(connection):
    names = [table for table in metadata.sorted_tables if table.name.startswith("connector_")]
    metadata.create_all(connection, tables=names)
