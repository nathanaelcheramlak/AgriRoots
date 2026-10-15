"""Durable run checkpoints, bounded leases, evidence links and private tool logs."""
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base
from src.db.models.workspace import uid, now


class AdvisoryRun(Base):
    __tablename__ = "advisory_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    cluster_id: Mapped[str] = mapped_column(ForeignKey("workspace_records.id"))
    request_key: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_config: Mapped[dict] = mapped_column(JSON, default=dict)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    capability_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    advisory_id: Mapped[str | None] = mapped_column(ForeignKey("advisories.id"), nullable=True, unique=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("office_id", "request_key"),)


class RunEvidence(Base):
    __tablename__ = "advisory_run_evidence"
    run_id: Mapped[str] = mapped_column(ForeignKey("advisory_runs.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("workspace_records.id"))


class RunCall(Base):
    __tablename__ = "advisory_run_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("advisory_runs.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(80))
    inputs: Mapped[dict] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0)


class PublicDocument(Base):
    __tablename__ = "public_guidance_cache"
    url: Mapped[str] = mapped_column(String(1000), primary_key=True)
    retrieved_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    extract: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    source_license: Mapped[str] = mapped_column(String(100))
    server_version: Mapped[str] = mapped_column(String(40))
