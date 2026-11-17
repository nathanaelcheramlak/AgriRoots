"""Persistent office registry. Spatial columns are installed by revision 6 on PostgreSQL."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.workspace import now, uid


class Territory(Base):
    __tablename__ = "registry_territories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(100), default="")
    district: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(String(600), default="")
    boundary: Mapped[dict] = mapped_column(JSON)
    area_m2: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending-approval", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TerritoryAssignment(Base):
    __tablename__ = "registry_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    territory_id: Mapped[str] = mapped_column(ForeignKey("registry_territories.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="manager")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Farmer(Base):
    __tablename__ = "registry_farmers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    territory_id: Mapped[str] = mapped_column(ForeignKey("registry_territories.id"), index=True)
    reference: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(120), index=True)
    village: Mapped[str] = mapped_column(String(100), default="", index=True)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    private_ciphertext: Mapped[str] = mapped_column(Text)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("office_id", "reference"),)


class RegisteredPlot(Base):
    __tablename__ = "registry_plots"
    id: Mapped[str] = mapped_column(ForeignKey("workspace_records.id"), primary_key=True)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    territory_id: Mapped[str] = mapped_column(ForeignKey("registry_territories.id"), index=True)
    boundary: Mapped[dict] = mapped_column(JSON)
    area_m2: Mapped[float] = mapped_column(Float)
    centroid: Mapped[dict] = mapped_column(JSON)
    sampling_point: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="registered")
    overlaps: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    request_key: Mapped[str] = mapped_column(String(100))
    request_digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("office_id", "request_key"),)


class FarmerPlot(Base):
    __tablename__ = "registry_farmer_plots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    plot_id: Mapped[str] = mapped_column(ForeignKey("registry_plots.id"), index=True)
    farmer_id: Mapped[str] = mapped_column(ForeignKey("registry_farmers.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="operator")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CropSeason(Base):
    __tablename__ = "registry_seasons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("registry_plots.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FarmObservation(Base):
    __tablename__ = "registry_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("registry_plots.id"), index=True)
    provenance: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlotRun(Base):
    __tablename__ = "registry_plot_runs"
    plot_id: Mapped[str] = mapped_column(ForeignKey("workspace_records.id"), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("connector_jobs.id"), primary_key=True)
    __table_args__ = (Index("ix_registry_plot_runs_job", "job_id"),)
