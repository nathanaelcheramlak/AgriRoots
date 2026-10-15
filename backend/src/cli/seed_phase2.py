"""Seed a fresh synthetic Phase 2 office with current, locally reviewed records."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from src.cli.seed_synthetic import main as seed_phase1
from src.db.session import SessionLocal
from src.db.models.workspace import WorkspaceRecord, Membership
from src.db.models.user import User
from src.api.schemas.workspace import RecordInput
from src.services.workspace_service import WorkspaceService


def main():
    seed_phase1()
    today = datetime.now(timezone.utc).date()
    with SessionLocal() as db:
        officer = db.scalar(select(Membership).where(Membership.role == "officer"))
        plot = db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.kind == "plot"))
        service = WorkspaceService(db, db.get(User, officer.user_id))
        def record(kind, data): service.save_record(officer.office_id, RecordInput(kind=kind, data=data))
        planting = today.isoformat(); harvest = (today + timedelta(days=60)).isoformat()
        record("season", {"plot_id": plot.id, "crop": "maize", "stage": "planned", "planting_date": planting, "harvest_date": harvest,
                          "previous_yield": None, "yield_unit": None})
        guidance = {"crop": "maize", "agroclimatic_zone": plot.data["agroclimatic_zone"],
                    "text": "SYNTHETIC planting/hold thresholds for software demonstration only; not validated agronomic advice. The officer must confirm field readiness before planting.",
                    "source": "internal:synthetic-local-guide", "reviewed_on": today.isoformat(),
                    "supported_actions": ["plant_crop", "hold_planting", "request_field_visit"],
                    "planting_rule": {"rain_days": 2, "minimum_rain_mm": 10, "maximum_rain_mm": 50,
                                      "maximum_temperature_c": 35, "maximum_wind_kph": 30}}
        record("guidance", guidance)
        record("calendar", {**guidance, "planting_start": planting, "planting_end": (today + timedelta(days=7)).isoformat(),
                            "harvest_start": harvest, "harvest_end": harvest})
    print("Phase 2 synthetic records ready; forecasts will be fetched live.")


if __name__ == "__main__": main()
