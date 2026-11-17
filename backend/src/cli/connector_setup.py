"""One migration owner, then a restricted application role. Never log DSNs or passwords."""

import asyncio
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from psycopg import sql
import psycopg

from src.config.settings import get_settings
from src.db.schema_migrations import migrate


def setup():
    settings = get_settings()
    migration_url = os.environ.get("MIGRATION_DATABASE_URL") or settings.database_url
    migration_engine = create_engine(migration_url)
    migrate(migration_engine)
    if migration_engine.dialect.name != "postgresql":
        return
    app_url = make_url(settings.database_url)
    owner_url = make_url(migration_url).set(drivername="postgresql").render_as_string(hide_password=False)
    if app_url.username != "agrilo_app":
        raise RuntimeError("Compose provisioning expects the dedicated agrilo_app role")
    with psycopg.connect(owner_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", ("agrilo_app",)).fetchone()
        if not exists:
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier("agrilo_app"), sql.Literal(app_url.password)
                )
            )
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO agrilo_app").format(sql.Identifier(app_url.database)))
        conn.execute("GRANT USAGE ON SCHEMA public TO agrilo_app")

    async def checkpoints():
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(owner_url) as saver:
            await saver.setup()

    asyncio.run(checkpoints())
    with psycopg.connect(owner_url, autocommit=True) as conn:
        conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO agrilo_app")
        conn.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agrilo_app")
        conn.execute(
            "REVOKE UPDATE, DELETE ON workspace_events, connector_approvals, connector_tool_versions, connector_integration_versions, connector_skill_versions FROM agrilo_app"
        )
    print(
        "Migrations/checkpoints prepared; application role cannot alter approval/version bodies or update/delete audit events."
    )


if __name__ == "__main__":
    setup()
