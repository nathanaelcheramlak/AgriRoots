"""Execute a real local-model/MCP run on labelled synthetic records and save its results."""
import argparse
import asyncio
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from sqlalchemy import select
from src.api.schemas.advisory_run import RunRequest
from src.agent.advisory.graph import execute_run
from src.db.session import SessionLocal
from src.db.models.workspace import WorkspaceRecord, Membership, AdvisoryVersion
from src.db.models.advisory_run import AdvisoryRun, RunCall
from src.db.models.user import User
from src.services.run_service import create_run, run_view


async def check(output, cluster_id=None):
    with SessionLocal() as db:
        households = list(db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.kind == "household")))
        if not households or any(not h.data["synthetic"] for h in households):
            raise SystemExit("This public validation command requires labelled synthetic households only")
        officer = db.scalar(select(Membership).where(Membership.role == "officer"))
        cluster = db.get(WorkspaceRecord, cluster_id) if cluster_id else db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.kind == "cluster", WorkspaceRecord.office_id == officer.office_id))
        if not cluster or cluster.office_id != officer.office_id or cluster.kind != "cluster":
            raise SystemExit("Choose a synthetic cluster in the officer's office")
        run = create_run(db, officer.office_id, RunRequest(cluster_id=cluster.id,
            task="Inspect current crop conditions and identify observations needed for officer review.", request_key=str(uuid4())), db.get(User, officer.user_id))
        run_id = run.id
    start = perf_counter(); await execute_run(run_id)
    with SessionLocal() as db:
        run = db.get(AdvisoryRun, run_id)
        calls = list(db.scalars(select(RunCall).where(RunCall.run_id == run_id).order_by(RunCall.started_at)))
        report = {"executed_at": datetime.now(timezone.utc).isoformat(), "data": "labelled synthetic households",
            "host": {"system": platform.system(), "architecture": platform.machine(), "processor": platform.processor()},
            "run_id": run_id, "status": run.status, "stage": run.stage, "error": run.error,
            "model": run.model_config, "elapsed_seconds": round(perf_counter() - start, 2),
            "advisory_id": run.advisory_id,
            "calls": [{"tool": c.tool_name, "duration_ms": c.duration_ms, "error": c.error, "usage": c.usage,
                       "estimated_cost_usd": c.estimated_cost_usd,
                       "public_source_cache_hits": c.output.get("cache_hits") if c.output and c.tool_name == "borrowed_mcp.fetch" else None} for c in calls]}
        if run.advisory_id:
            version = db.scalar(select(AdvisoryVersion).where(AdvisoryVersion.advisory_id == run.advisory_id))
            report["saved_status"] = version.status; report["evidence_count"] = len(version.evidence_snapshots)
            report["recommendations"] = version.content["recommendations"]
            report["plot_count"] = len(version.content["plot_ids"])
            report["household_count"] = len(version.content["household_ids"])
        seconds = sum((c.duration_ms or 0) / 1000 for c in calls if c.tool_name.startswith("model."))
        rate = run.model_config.get("compute_cost_per_hour_usd", 0)
        report["cost"] = {"status": "estimated" if rate else "unpriced", "assumed_hourly_host_usd": rate,
            "model_seconds": round(seconds, 3), "inference_usd": round(seconds * rate / 3600, 6) if rate else None,
            "wall_time_host_usd": round(report["elapsed_seconds"] * rate / 3600, 6) if rate else None,
            "exclusions": "Provider fees, idle time, electricity and first-start downloads; rate is an operator assumption"}
        report["under_fifteen_minutes"] = report["elapsed_seconds"] < 900
        Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"status": run.status, "elapsed_seconds": report["elapsed_seconds"], "report": str(output)}))
        if run.status != "pending_review": raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", required=True)
    parser.add_argument("--cluster-id")
    args = parser.parse_args()
    asyncio.run(check(args.output, args.cluster_id))
