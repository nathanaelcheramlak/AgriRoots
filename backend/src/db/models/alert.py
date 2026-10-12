import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"

    alert_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(80), default="weather")
    severity: Mapped[str] = mapped_column(String(20), default="low")
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    action_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_weather: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="weather_alerts")
