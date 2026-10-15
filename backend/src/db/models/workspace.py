"""Office boundaries and immutable, explicitly published advisory versions."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Administrator(Base):
    __tablename__ = "workspace_administrators"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)


class Office(Base):
    __tablename__ = "offices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))


class Membership(Base):
    __tablename__ = "office_memberships"
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint("user_id"),)


class WorkspaceRecord(Base):
    """Typed office records. Payloads are validated by the API schema registry."""
    __tablename__ = "workspace_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    farmer_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, unique=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Advisory(Base):
    __tablename__ = "advisories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class AdvisoryVersion(Base):
    __tablename__ = "advisory_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    advisory_id: Mapped[str] = mapped_column(ForeignKey("advisories.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    content: Mapped[dict] = mapped_column(JSON)
    recipient_user_ids: Mapped[list] = mapped_column(JSON)
    evidence_snapshots: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("advisory_id", "version"),)


class WorkspaceEvent(Base):
    __tablename__ = "workspace_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str | None] = mapped_column(ForeignKey("offices.id"), nullable=True, index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
