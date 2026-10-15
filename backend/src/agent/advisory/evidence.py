"""Deterministic scope, date, unit and support checks; no model is trusted here."""
import re
from datetime import datetime, timezone
from src.api.schemas.advisory_run import ACTIONS, Candidates
from src.api.schemas.workspace import AdvisoryInput
from src.services.workspace_service import fail
from src.services.run_service import utc
from src.agent.advisory.decisions import eligible_decision

REQUIRED_KINDS = {"history", "weather", "guidance", "calendar", "public_document"}


def validate_candidates(db, run, candidates: Candidates, *, now=None, require_all=True):
    from src.db.models.advisory_run import RunEvidence
    from src.db.models.workspace import WorkspaceRecord
    from sqlalchemy import select
    now = now or datetime.now(timezone.utc)
    history = run.state.get("history", {})
    plots = {p["id"]: p for p in history.get("plots", [])}
    links = list(db.scalars(select(RunEvidence).where(RunEvidence.run_id == run.id)))
    records = {link.record_id: db.get(WorkspaceRecord, link.record_id) for link in links}
    output = []
    targeted = set()
    for candidate in candidates.recommendations:
        plot = plots.get(candidate.plot_id)
        if not plot or candidate.crop != plot["season"]["crop"]:
            fail(422, "Candidate crop or plot is outside the authorized season")
        if plot["id"] in targeted:
            fail(422, "Each plot must have exactly one recommendation")
        day = candidate.proposed_date
        season = plot["season"]
        if (day.isoformat() > season["harvest_date"] or day < now.date()
                or (season.get("stage", "growing") != "planned" and day.isoformat() < season["planting_date"])):
            fail(422, "Proposed action is outside the current crop season")
        kinds = set(); supported = set()
        for evidence_id in set(candidate.evidence_ids):
            record = records.get(evidence_id)
            if not record or record.office_id != run.office_id:
                fail(422, "Invented or unauthorized evidence identifier")
            e = record.data; context = e["values"]
            if (e.get("plot_id") != plot["id"] or e["crop"] != candidate.crop
                    or context.get("season_id") != plot["season_id"]
                    or context.get("agroclimatic_zone") != plot["agroclimatic_zone"]
                    or context.get("latitude") != plot["latitude"] or context.get("longitude") != plot["longitude"]):
                fail(422, "Evidence does not apply to this plot, crop, location and season")
            start, end = datetime.fromisoformat(e["valid_from"]), datetime.fromisoformat(e["valid_until"])
            retrieved = datetime.fromisoformat(e["retrieved_at"])
            if not utc(start).date() <= day <= utc(end).date() or utc(end) < now or utc(retrieved) > now:
                fail(422, "Evidence is expired or does not cover the proposed date")
            kind = context.get("kind"); kinds.add(kind)
            if kind == "weather":
                if day.isoformat() not in {d["date"] for d in context.get("forecast_days", [])}:
                    fail(422, "Weather forecast does not cover the proposed date")
                if (now - utc(retrieved)).total_seconds() > 6 * 3600 or e["units"] != "mm, degC, km/h":
                    fail(422, "Weather freshness or units are invalid")
            if kind == "guidance":
                supported.update(context.get("supported_actions", []))
        if not REQUIRED_KINDS <= kinds:
            fail(422, "Recommendation needs history, weather, local guidance, calendar and public-document citations")
        conflicts = run.state.get("get_crop_risk_context", {}).get("warnings", [])
        if any(w.get("plot_id") == plot["id"] and w.get("conflict") for w in conflicts) and candidate.action_code != "request_field_visit":
            fail(422, "Conflicting pest signals require an officer field visit")
        if candidate.action_code not in supported:
            fail(422, "The proposed action is not supported by locally reviewed guidance")
        decision = eligible_decision(plot, [records[e].data for e in candidate.evidence_ids], day, conflicts)
        if candidate.action_code not in decision["actions"]:
            fail(422, "Action contradicts the locally reviewed planting rules or crop stage")
        if re.search(r"\d|\b(dose|spray|pesticide|fertilizer|guarantee|exactly)\b", candidate.rationale + " " + candidate.uncertainty, re.I):
            fail(422, "Unsupported precision or input prescription in generated narrative")
        output.append({"action": plot["name"] + ": " + ACTIONS[candidate.action_code], "proposed_date": day.isoformat(),
                       "evidence_ids": candidate.evidence_ids,
                       "basis": decision["basis"],
                       "uncertainty": "This draft uses dated records and forecasts. Current field conditions still require confirmation by the extension officer."})
        targeted.add(plot["id"])
    if require_all and targeted != set(plots):
        fail(422, "Every selected plot needs a supported recommendation or an explicit insufficient-evidence result")
    return AdvisoryInput(title="Climate advisory: " + ", ".join(sorted({p["season"]["crop"] for p in plots.values()}))[:150], household_ids=sorted({p["household_id"] for p in plots.values()}),
        plot_ids=sorted(plots), assigned_officer_id=run.officer_id, language="en", recommendations=output,
        missing_information="Current field observations and officer confirmation are required.")
