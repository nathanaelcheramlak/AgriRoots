from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.api.errors import raise_http_error
from src.api.schemas.alert import (
    WeatherAlertDeleteResponse,
    WeatherAlertGenerateResponse,
    WeatherAlertReadResponse,
    WeatherAlertResponse,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.services.alert_app_service import AlertAppService
from src.services.exceptions import ServiceError


router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


def _service(db: Session) -> AlertAppService:
    return AlertAppService(db)


@router.get("", response_model=list[WeatherAlertResponse])
def list_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WeatherAlertResponse]:
    try:
        return _service(db).list_alerts(current_user, limit, offset)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post(
    "/weather/generate",
    response_model=WeatherAlertGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_weather_alerts(
    language_code: str | None = Query(default=None, min_length=2, max_length=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherAlertGenerateResponse:
    try:
        return _service(db).generate_weather_alerts(current_user, language_code)
    except ServiceError as exc:
        raise_http_error(exc)


@router.patch("/{alert_id}/read", response_model=WeatherAlertReadResponse)
def mark_alert_read(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherAlertReadResponse:
    try:
        return _service(db).mark_alert_read(current_user, alert_id)
    except ServiceError as exc:
        raise_http_error(exc)


@router.delete("/{alert_id}", response_model=WeatherAlertDeleteResponse)
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherAlertDeleteResponse:
    try:
        return _service(db).delete_alert(current_user, alert_id)
    except ServiceError as exc:
        raise_http_error(exc)
