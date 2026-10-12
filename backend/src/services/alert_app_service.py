import json

from sqlalchemy.orm import Session

from src.api.schemas.alert import (
    WeatherAlertDeleteResponse,
    WeatherAlertGenerateResponse,
    WeatherAlertReadResponse,
    WeatherAlertResponse,
)
from src.db.models.alert import WeatherAlert
from src.db.models.user import User
from src.repositories.alert_repository import WeatherAlertRepository
from src.repositories.user_repository import UserRepository
from src.services.alert_service import build_weather_alerts
from src.services.exceptions import ServiceError


def _decode_weather(raw_weather: str | None) -> dict | None:
    if not raw_weather:
        return None
    try:
        return json.loads(raw_weather)
    except json.JSONDecodeError:
        return None


def to_alert_response(alert: WeatherAlert) -> WeatherAlertResponse:
    return WeatherAlertResponse(
        alert_id=alert.alert_id,
        user_id=alert.user_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        title=alert.title,
        message=alert.message,
        action_text=alert.action_text,
        location_used=alert.location_used,
        raw_weather=_decode_weather(alert.raw_weather),
        is_read=alert.is_read,
        created_at=alert.created_at,
    )


class AlertAppService:
    def __init__(self, db: Session):
        self.db = db
        self.alerts = WeatherAlertRepository(db)
        self.users = UserRepository(db)

    def list_alerts(self, current_user: User, limit: int, offset: int) -> list[WeatherAlertResponse]:
        return [
            to_alert_response(alert)
            for alert in self.alerts.list_by_user(current_user.user_id, limit, offset)
        ]

    def generate_weather_alerts(
        self,
        current_user: User,
        language_code: str | None,
    ) -> WeatherAlertGenerateResponse:
        profile = self.users.get_profile(current_user.user_id)
        if not profile:
            raise ServiceError(404, "Profile not found. Complete onboarding first.")

        try:
            location_used, raw_weather, alert_payloads = build_weather_alerts(profile, language_code=language_code)
        except ValueError as exc:
            raise ServiceError(400, str(exc)) from exc
        except Exception as exc:
            raise ServiceError(502, f"Weather alert provider request failed: {exc}") from exc

        created_alerts: list[WeatherAlert] = []
        raw_weather_json = json.dumps(raw_weather, ensure_ascii=False)
        for payload in alert_payloads:
            alert = WeatherAlert(
                user_id=current_user.user_id,
                alert_type=payload["alert_type"],
                severity=payload["severity"],
                title=payload["title"],
                message=payload["message"],
                action_text=payload["action_text"],
                location_used=location_used,
                raw_weather=raw_weather_json,
            )
            self.alerts.add(alert)
            created_alerts.append(alert)

        self.db.commit()
        for alert in created_alerts:
            self.db.refresh(alert)

        return WeatherAlertGenerateResponse(
            generated_count=len(created_alerts),
            alerts=[to_alert_response(alert) for alert in created_alerts],
        )

    def mark_alert_read(self, current_user: User, alert_id: str) -> WeatherAlertReadResponse:
        alert = self.alerts.get_owned(alert_id, current_user.user_id)
        if not alert:
            raise ServiceError(404, "Alert not found")

        alert.is_read = True
        self.db.commit()
        self.db.refresh(alert)
        return WeatherAlertReadResponse(
            message="Alert marked as read",
            alert=to_alert_response(alert),
        )

    def delete_alert(self, current_user: User, alert_id: str) -> WeatherAlertDeleteResponse:
        alert = self.alerts.get_owned(alert_id, current_user.user_id)
        if not alert:
            raise ServiceError(404, "Alert not found")

        deleted_id = alert.alert_id
        self.alerts.delete(alert)
        self.db.commit()
        return WeatherAlertDeleteResponse(
            message="Alert deleted successfully",
            alert_id=deleted_id,
        )
