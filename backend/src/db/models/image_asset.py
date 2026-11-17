"""Private office-owned images and durable credit-consumption receipts."""

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.workspace import now, uid


class ImageAsset(Base):
    __tablename__ = "connector_image_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    sha256: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(32))
    byte_size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class DiagnosisReceipt(Base):
    __tablename__ = "connector_diagnosis_receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    office_id: Mapped[str] = mapped_column(ForeignKey("offices.id"))
    image_sha256: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(40), default="kindwise")
    invocation_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(30), default="attempted")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("office_id", "image_sha256", "provider"),)
