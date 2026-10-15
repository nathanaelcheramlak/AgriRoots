"""Ordered, recorded schema upgrades shared by startup and the CLI.

Run one migration process before starting multiple production workers.
"""
from sqlalchemy import Column, Integer, Table, select
from src.db.base import Base
from src.db.migrations import v001_legacy, v002_workspace, v003_advisory_runs

revisions = Table("schema_revisions", Base.metadata, Column("version", Integer, primary_key=True))
MIGRATIONS = ((1, v001_legacy), (2, v002_workspace), (3, v003_advisory_runs))


def migrate(engine):
    with engine.begin() as connection:
        revisions.create(connection, checkfirst=True)
        applied = set(connection.scalars(select(revisions.c.version)))
        for version, migration in MIGRATIONS:
            if version not in applied:
                migration.upgrade(connection)
                connection.execute(revisions.insert().values(version=version))


def ensure_chat_message_storage_columns(engine):
    """Compatibility entrypoint for existing tooling."""
    from sqlalchemy import inspect
    if inspect(engine).has_table("chat_messages"):
        with engine.begin() as connection:
            v001_legacy.upgrade(connection)


if __name__ == "__main__":
    from src.db.session import engine
    migrate(engine)
