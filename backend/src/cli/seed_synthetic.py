"""Create a labelled local demonstration office in an empty database only."""
from sqlalchemy import select
from src.auth.password import hash_password
from src.common.utils.phone import normalize_phone
from src.db.models.user import User, UserProfile
from src.db.schema_migrations import migrate
from src.db.session import engine, SessionLocal
from src.cli.provision_admin import provision
from src.services.workspace_service import WorkspaceService
from src.api.schemas.workspace import RecordInput, MemberInput


def main():
    migrate(engine)
    with SessionLocal() as db:
        if db.scalar(select(User)):
            raise SystemExit("Synthetic seed requires an empty database; existing data was left intact")
        accounts = []
        for name, phone in [("Administrator", "+251900000001"), ("Officer", "+251900000002"), ("Farmer", "+251900000003")]:
            user = User(phone_number=normalize_phone(phone), password_hash=hash_password("SyntheticDemo123!"))
            db.add(user); db.flush()
            db.add(UserProfile(user_id=user.user_id, full_name=f"SYNTHETIC {name}", preferred_language="en",
                               onboarding_completed=True, user_type="beginner"))
            accounts.append(user.user_id)
        db.commit()
    provision(accounts[0])
    with SessionLocal() as db:
        s = WorkspaceService(db, db.get(User, accounts[0]))
        office = s.create_office("SYNTHETIC extension office — development only")
        for account, role in zip(accounts[1:], ["officer", "farmer"]):
            s.assign_member(office.id, MemberInput(user_id=account, role=role))
        s = WorkspaceService(db, db.get(User, accounts[1]))
        def record(kind, data):
            return s.save_record(office.id, RecordInput(kind=kind, data=data))
        cluster = record("cluster", {"name": "SYNTHETIC cluster", "assigned_officer_id": accounts[1], "synthetic": True})
        household = record("household", {"name": "SYNTHETIC household", "farmer_user_id": accounts[2],
            "cluster_id": cluster.id, "assigned_officer_id": accounts[1], "synthetic": True})
        plot = record("plot", {"name": "SYNTHETIC plot", "household_id": household.id, "latitude": 9.03,
            "longitude": 38.74, "area": 1, "area_unit": "ha", "agroclimatic_zone": "Synthetic demonstration zone"})
        record("season", {"plot_id": plot.id, "crop": "maize", "planting_date": "2026-05-01",
                          "harvest_date": "2026-10-01", "previous_yield": 0, "yield_unit": "kg/ha"})
        record("evidence", {"source_name": "SYNTHETIC rainfall example", "source_reference": "internal:synthetic-rain-001",
            "observed_at": "2026-10-14T08:00:00Z", "retrieved_at": "2026-10-15T08:00:00Z",
            "valid_from": "2026-10-14T08:00:00Z", "valid_until": "2026-10-20T08:00:00Z",
            "location": "SYNTHETIC plot", "crop": "maize", "units": "mm", "values": {"rainfall": 20},
            "snapshot": "SYNTHETIC observation: 20 mm. Demonstration only; not real weather.",
            "classification": "synthetic", "plot_id": plot.id})
    print("Synthetic accounts created. Local demo password: SyntheticDemo123!")
    for role, account in zip(["Administrator", "Officer", "Farmer"], accounts):
        print(f"{role}: {account}")


if __name__ == "__main__":
    main()
