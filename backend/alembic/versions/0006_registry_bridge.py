"""Adopt recorded revisions 1–5 and apply the additive PostGIS registry revision."""

from sqlalchemy import select, text

from alembic import op
from src.db.schema_migrations import MIGRATIONS, revisions

revision = "0006_registry"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(18472004)"))
    revisions.create(connection, checkfirst=True)
    applied = set(connection.scalars(select(revisions.c.version)))
    for version, migration in MIGRATIONS:
        if version not in applied:
            migration.upgrade(connection)
            connection.execute(revisions.insert().values(version=version))


def downgrade():
    raise RuntimeError("Registry downgrade is destructive; restore a reviewed backup instead")
