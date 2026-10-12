from sqlalchemy.orm import Session

from src.db.models.alert import WeatherAlert


class WeatherAlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: str, limit: int, offset: int) -> list[WeatherAlert]:
        return (
            self.db.query(WeatherAlert)
            .filter(WeatherAlert.user_id == user_id)
            .order_by(WeatherAlert.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_owned(self, alert_id: str, user_id: str) -> WeatherAlert | None:
        return (
            self.db.query(WeatherAlert)
            .filter(
                WeatherAlert.alert_id == alert_id,
                WeatherAlert.user_id == user_id,
            )
            .first()
        )

    def add(self, alert: WeatherAlert) -> WeatherAlert:
        self.db.add(alert)
        return alert

    def delete(self, alert: WeatherAlert) -> None:
        self.db.delete(alert)
