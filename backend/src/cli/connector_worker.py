"""python -m src.cli.connector_worker [--once]. No provider probes occur on startup."""

import argparse
import asyncio
import sys
from src.db.schema_migrations import migrate
from src.db.session import engine
from src.integrations.jobs import work


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    migrate(engine)
    asyncio.run(work(once=args.once))
