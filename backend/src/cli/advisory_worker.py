"""Durable queue worker: python -m src.cli.advisory_worker [--once]."""
import argparse
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, or_
from src.agent.advisory.graph import execute_run
from src.db.models.advisory_run import AdvisoryRun
from src.db.schema_migrations import migrate
from src.db.session import SessionLocal, engine


async def work(once=False):
    migrate(engine)
    while True:
        with SessionLocal() as db:
            ids = list(db.scalars(select(AdvisoryRun.id).where(or_(AdvisoryRun.status == "queued",
                (AdvisoryRun.status == "running") & (AdvisoryRun.lease_until < datetime.now(timezone.utc)))
                ).order_by(AdvisoryRun.created_at).limit(1)))
        for run_id in ids:
            await execute_run(run_id)
        if once: return
        await asyncio.sleep(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--once", action="store_true")
    asyncio.run(work(parser.parse_args().once))
