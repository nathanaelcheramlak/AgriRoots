"""Bridge the existing recorded revisions; migration URL stays outside source control."""

import os

from sqlalchemy import create_engine

from alembic import context
from src.config.settings import get_settings
from src.db.base import Base

settings = get_settings()
url = os.environ.get("MIGRATION_DATABASE_URL") or settings.database_url
if context.is_offline_mode():
    raise RuntimeError("Registry upgrades require an online database and existing revision checks")
with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
