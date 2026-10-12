from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WeatherAlertResponse(BaseModel):
    alert_id: UUID
    user_id: UUID
    alert_type: str
    severity: str
    title: str
    message: str
    action_text: str | None = None
    location_used: str | None = None
    raw_weather: dict | None = None
    is_read: bool
    created_at: datetime


class WeatherAlertGenerateResponse(BaseModel):
    generated_count: int
    alerts: list[WeatherAlertResponse]


class WeatherAlertReadResponse(BaseModel):
    message: str
    alert: WeatherAlertResponse


class WeatherAlertDeleteResponse(BaseModel):
    message: str
    alert_id: UUID
