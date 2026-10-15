"""Create a separate labelled synthetic cluster for real capacity/planting checks."""
import argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from src.api.schemas.workspace import RecordInput
from src.db.models.workspace import Membership, WorkspaceRecord
from src.db.models.user import User
from src.db.session import SessionLocal
from src.services.workspace_service import WorkspaceService


def main(count=5, planned=False):
    with SessionLocal() as db:
        households = list(db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.kind == "household")))
        if not households or any(not h.data["synthetic"] for h in households):
            raise SystemExit("Capacity fixtures are restricted to an exclusively synthetic database")
        officer = db.scalar(select(Membership).where(Membership.role == "officer"))
        original = next(h for h in households if h.office_id == officer.office_id)
        plot = next(p for p in db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.kind == "plot"))
                    if p.data["household_id"] == original.id)
        service = WorkspaceService(db, db.get(User, officer.user_id))
        def record(kind, data): return service.save_record(officer.office_id, RecordInput(kind=kind, data=data))
        cluster = record("cluster", {"name": f"SYNTHETIC {'planting' if planned else 'capacity'} cluster ({count} plots)",
            "assigned_officer_id": officer.user_id, "synthetic": True})
        # One linked household with several plots: measured capacity is stated explicitly.
        # Household↔farmer ownership is immutable; use a new synthetic farmer account.
        from src.auth.password import hash_password
        from src.db.models.user import UserProfile
        import secrets
        phone = "2519" + "".join(str(secrets.randbelow(10)) for _ in range(8))
        user = User(phone_number=phone, password_hash=hash_password("SyntheticDemo123!"))
        db.add(user); db.flush()
        db.add(UserProfile(user_id=user.user_id, full_name="SYNTHETIC benchmark farmer", onboarding_completed=True, preferred_language="en"))
        db.add(Membership(office_id=officer.office_id, user_id=user.user_id, role="farmer")); db.commit()
        service.event(officer.office_id, user.user_id, "synthetic_benchmark_farmer_created", cluster_id=cluster.id)
        db.commit()
        household = record("household", {**original.data, "name": "SYNTHETIC benchmark household", "cluster_id": cluster.id,
            "farmer_user_id": user.user_id})
        today = datetime.now(timezone.utc).date()
        planting = today if planned else today - timedelta(days=40)
        harvest = today + timedelta(days=60)
        zone = "Synthetic benchmark zone " + cluster.id
        for index in range(count):
            new_plot = record("plot", {**plot.data, "household_id": household.id, "name": f"SYNTHETIC benchmark plot {index + 1}",
                "latitude": plot.data["latitude"] + index * .002, "agroclimatic_zone": zone})
            record("season", {"plot_id": new_plot.id, "crop": "maize", "stage": "planned" if planned else "growing",
                "planting_date": planting.isoformat(), "harvest_date": harvest.isoformat(), "previous_yield": None, "yield_unit": None})
        guidance = {"crop": "maize", "agroclimatic_zone": zone, "source": "internal:synthetic-benchmark-guidance",
            "text": "SYNTHETIC test thresholds and guidance. Not validated agronomic advice. Officer must verify field readiness.",
            "reviewed_on": today.isoformat(), "supported_actions": ["inspect_crop", "request_field_visit"]}
        if planned:
            guidance.update(supported_actions=["plant_crop", "hold_planting", "request_field_visit"],
                planting_rule={"rain_days": 2, "minimum_rain_mm": 10, "maximum_rain_mm": 50,
                               "maximum_temperature_c": 35, "maximum_wind_kph": 30})
        record("guidance", guidance)
        record("calendar", {**guidance, "planting_start": planting.isoformat(), "planting_end": (planting + timedelta(days=7)).isoformat(),
            "harvest_start": harvest.isoformat(), "harvest_end": harvest.isoformat()})
        print(cluster.id)
        return {"cluster_id": cluster.id, "cluster_name": cluster.data["name"], "farmer_phone": phone}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plots", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--planned", action="store_true")
    args = parser.parse_args(); main(args.plots, args.planned)
