"""Local-only first-administrator provisioning for an existing verified account."""
import argparse
from sqlalchemy import select, text
from src.db.schema_migrations import migrate
from src.db.session import engine, SessionLocal
from src.db.models.user import User
from src.db.models.workspace import Administrator, WorkspaceEvent


def provision(user_id):
    migrate(engine)
    with SessionLocal() as db:
        # Serialize the bootstrap on each supported database. There is no HTTP
        # bootstrap endpoint and no password/token accepted on the command line.
        if engine.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        elif engine.dialect.name == "postgresql":
            db.execute(text("LOCK TABLE workspace_administrators IN EXCLUSIVE MODE"))
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise SystemExit("An active registered account UUID is required")
        if db.scalar(select(Administrator)):
            raise SystemExit("Initial administrator already provisioned")
        db.add(Administrator(user_id=user_id))
        db.add(WorkspaceEvent(actor_id=user_id, entity_id=user_id, action="administrator_provisioned",
                              details={"procedure": "local bootstrap"}))
        db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True)
    provision(parser.parse_args().user_id)
