"""Four run-bound MCP tools. The capability is never part of model context."""
from datetime import datetime, timedelta, timezone, date
from time import perf_counter
import asyncio
import math
import logging
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from src.api.schemas.advisory_run import EmptyInput, Candidates, ToolResult, ToolError, HistoryOutput, EvidenceOutput, RiskOutput, SaveOutput
from src.api.schemas.workspace import Evidence
from src.config.settings import get_settings
from src.db.models.workspace import WorkspaceRecord
from src.db.models.advisory_run import AdvisoryRun, RunEvidence, RunCall
from src.db.session import SessionLocal
from src.services.run_service import authorize_capability, utc
from src.services.workspace_service import WorkspaceService, fail
from src.agent.advisory.evidence import validate_candidates

TOOL_SCHEMAS = {"get_cluster_plot_history": EmptyInput, "get_weather_evidence": EmptyInput,
                "get_crop_risk_context": EmptyInput, "save_advisory_draft": Candidates}


class AdvisoryTools:
    def __init__(self, run_id, capability):
        self.run_id, self.capability = run_id, capability

    def authorized(self, db):
        return authorize_capability(db, self.run_id, self.capability)

    async def call(self, name, arguments):
        started = perf_counter()
        call_id = None
        try:
            with SessionLocal() as db:
                run, officer = self.authorized(db)
                if name not in TOOL_SCHEMAS:
                    fail(422, "Unknown tool; approval and publication tools do not exist")
                schema = TOOL_SCHEMAS[name]
                inputs = schema.model_validate(arguments)
                result = db.execute(update(AdvisoryRun).where(AdvisoryRun.id == run.id,
                    AdvisoryRun.tool_calls < get_settings().advisory_max_tool_calls).values(tool_calls=AdvisoryRun.tool_calls + 1))
                if not result.rowcount:
                    fail(429, "Tool budget exhausted")
                log = RunCall(run_id=run.id, attempt=run.attempt, tool_name=name, inputs=inputs.model_dump(mode="json"))
                db.add(log); db.flush(); call_id = log.id; db.commit()
            handler = {"get_cluster_plot_history": self.history, "get_weather_evidence": self.weather,
                       "get_crop_risk_context": self.risk, "save_advisory_draft": self.save}[name]
            output = await handler(inputs)
            output = {"get_cluster_plot_history": HistoryOutput, "get_weather_evidence": EvidenceOutput,
                      "get_crop_risk_context": RiskOutput, "save_advisory_draft": SaveOutput}[name].model_validate(output).model_dump(mode="json")
            response = ToolResult(ok=True, data=output)
        except (HTTPException, ValidationError, ValueError) as exc:
            message = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            response = ToolResult(ok=False, error=ToolError(code="invalid_evidence" if isinstance(exc, HTTPException) and exc.status_code == 422 else "tool_rejected",
                message=message[:1500]))
        except (httpx.HTTPError, TimeoutError):
            response = ToolResult(ok=False, error=ToolError(code="upstream_unavailable", message="Weather service unavailable or timed out", retryable=True))
        except Exception:
            logging.getLogger(__name__).exception("Advisory MCP tool failed: %s", name)
            response = ToolResult(ok=False, error=ToolError(code="tool_failure", message="Tool failed; inspect the private server log"))
        with SessionLocal() as db:
            # Rejected calls, including invalid credentials/inputs, have a failure
            # audit when a real run exists. Never log the supplied capability.
            run = db.get(AdvisoryRun, self.run_id)
            if run:
                log = db.get(RunCall, call_id) if call_id else RunCall(run_id=run.id, attempt=run.attempt,
                    tool_name=name[:80], inputs={"validation": "rejected before execution"})
                log.output = response.data if response.ok else None
                log.error = response.error.model_dump() if response.error else None
                log.finished_at = datetime.now(timezone.utc); log.duration_ms = round((perf_counter() - started) * 1000)
                db.add(log); db.commit()
        return response.model_dump(mode="json")

    def rows(self, db, run, kind):
        return list(db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.office_id == run.office_id,
                                                            WorkspaceRecord.kind == kind)))

    def plots(self, db, run):
        households = [r for r in self.rows(db, run, "household") if r.data["cluster_id"] == run.cluster_id]
        household_map = {h.id: h for h in households}
        if not households:
            fail(422, "Cluster has no households; officer follow-up required")
        plots = [r for r in self.rows(db, run, "plot") if r.data["household_id"] in household_map]
        if not plots or len(plots) > 5:
            fail(422, "Select a cluster containing one to five plots")
        today = datetime.now(timezone.utc).date().isoformat()
        planning_limit = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        seasons = self.rows(db, run, "season")
        result = []
        for row in plots:
            active = [s for s in seasons if s.data["plot_id"] == row.id
                      and s.data["planting_date"] <= (planning_limit if s.data.get("stage") == "planned" else today)
                      and s.data.get("harvest_date") and today <= s.data["harvest_date"]]
            if len(active) != 1:
                fail(422, "Each plot requires one unambiguous current crop season with planting and harvest dates")
            result.append({"id": row.id, **row.data, "synthetic": household_map[row.data["household_id"]].data["synthetic"],
                           "season_id": active[0].id, "season": active[0].data})
        return result

    def evidence(self, db, run, officer, plot, kind, source, snapshot, *, values=None,
                 classification=None, observed=None, expires=None, units="record", reference=None):
        key = f"{kind}:{plot['id']}"
        link = db.get(RunEvidence, (run.id, key))
        now = datetime.now(timezone.utc)
        if link:
            old = db.get(WorkspaceRecord, link.record_id)
            if utc(datetime.fromisoformat(old.data["valid_until"])) > now and (
                    kind != "weather" or (now - utc(datetime.fromisoformat(old.data["retrieved_at"]))).total_seconds() < 21600):
                return old.id
        context = {"kind": kind, "latitude": plot["latitude"], "longitude": plot["longitude"],
                   "agroclimatic_zone": plot["agroclimatic_zone"], "season_id": plot["season_id"], **(values or {})}
        end = expires or datetime.combine(date.fromisoformat(plot["season"]["harvest_date"]), datetime.max.time(), timezone.utc)
        data = Evidence(source_name=source, source_reference=reference or "internal:" + plot["season_id"],
            observed_at=observed or now, retrieved_at=now, valid_from=now.replace(hour=0, minute=0, second=0, microsecond=0),
            valid_until=end, location=f"{plot['latitude']},{plot['longitude']}", crop=plot["season"]["crop"], units=units,
            values=context, snapshot=snapshot[:12000], classification=classification or ("synthetic" if plot["synthetic"] else "officer-entered"),
            plot_id=plot["id"]).model_dump(mode="json")
        record = WorkspaceRecord(office_id=run.office_id, kind="evidence", data=data, created_by=officer.user_id)
        db.add(record); db.flush()
        if link: link.record_id = record.id
        else: db.add(RunEvidence(run_id=run.id, key=key, record_id=record.id))
        WorkspaceService(db, officer).event(run.office_id, record.id, "agent_evidence_created", run_id=run.id, kind=kind)
        return record.id

    async def history(self, inputs):
        with SessionLocal() as db:
            run, officer = self.authorized(db); plots = self.plots(db, run)
            ids = []
            for plot in plots:
                ids.append(self.evidence(db, run, officer, plot, "history", "Office plot and crop-season records",
                    str(plot["season"]), values={"season": plot["season"]}))
            self.authorized(db); db.commit()
            return {"plots": plots, "evidence_ids": ids}

    async def weather(self, inputs):
        with SessionLocal() as db:
            run, officer = self.authorized(db); plots = self.plots(db, run)
            ids = []
            now = datetime.now(timezone.utc)
            sources = {}
            for plot in plots:
                sources[plot["id"]] = [r for r in self.rows(db, run, "evidence") if plot["synthetic"]
                    and r.data.get("plot_id") == plot["id"] and r.data.get("classification") == "synthetic"
                    and r.data.get("values", {}).get("kind") == "synthetic_forecast"
                    and utc(datetime.fromisoformat(r.data["valid_until"])) > now
                    and 0 <= (now - utc(datetime.fromisoformat(r.data["retrieved_at"]))).total_seconds() < 21600]
            locations = {(p["latitude"], p["longitude"]) for p in plots if not sources[p["id"]]}
            async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
                async def fetch(location):
                    response = await client.get("https://api.open-meteo.com/v1/forecast", params={
                        "latitude": location[0], "longitude": location[1], "timezone": "UTC", "forecast_days": 4,
                        "daily": "temperature_2m_max,temperature_2m_min,rain_sum,wind_speed_10m_max"})
                    response.raise_for_status()
                    return location, response.json()
                forecasts = dict(await asyncio.gather(*(fetch(location) for location in locations)))
            for plot in plots:
                now = datetime.now(timezone.utc)
                synthetic = sources[plot["id"]]
                if synthetic:
                    source = synthetic[-1].data
                    days = source["values"]["forecast_days"]
                    classification = "synthetic"
                else:
                    raw = forecasts[(plot["latitude"], plot["longitude"])]; d = raw["daily"]
                    u = raw["daily_units"]
                    if (u.get("rain_sum") != "mm" or u.get("temperature_2m_max") != "°C" or u.get("wind_speed_10m_max") != "km/h"
                            or abs(raw["latitude"] - plot["latitude"]) > .25 or abs(raw["longitude"] - plot["longitude"]) > .25):
                        fail(422, "Weather units or geographic coverage are invalid")
                    days = [{"date": day, "rain_mm": d["rain_sum"][i], "temp_max_c": d["temperature_2m_max"][i],
                             "wind_kph": d["wind_speed_10m_max"][i]} for i, day in enumerate(d["time"])]
                    classification = "live"
                if len(days) < 2 or any(not all(isinstance(day.get(k), (int, float)) and math.isfinite(day[k])
                    for k in ("rain_mm", "temp_max_c", "wind_kph")) for day in days):
                    fail(422, "Forecast contains missing values or invalid units")
                if any(day["rain_mm"] < 0 or day["wind_kph"] < 0 for day in days):
                    fail(422, "Forecast rainfall and wind values cannot be negative")
                if len({day["date"] for day in days}) != len(days) or now.date().isoformat() not in {day["date"] for day in days}:
                    fail(422, "Forecast dates are duplicated or do not cover today")
                self.authorized(db)
                ids.append(self.evidence(db, run, officer, plot, "weather", "Synthetic forecast" if synthetic else "Open-Meteo forecast",
                    str(days), values={"forecast_days": days, "source_latitude": plot["latitude"] if synthetic else raw["latitude"],
                        "source_longitude": plot["longitude"] if synthetic else raw["longitude"]}, classification=classification,
                    observed=datetime.fromisoformat(synthetic[-1].data["observed_at"]) if synthetic else now,
                    expires=datetime.combine(date.fromisoformat(days[-1]["date"]), datetime.max.time(), timezone.utc),
                    units="mm, degC, km/h", reference="internal:synthetic-forecast" if synthetic else "https://api.open-meteo.com/v1/forecast"))
            db.commit(); return {"evidence_ids": ids}

    async def risk(self, inputs):
        with SessionLocal() as db:
            run, officer = self.authorized(db); plots = self.plots(db, run); ids = []; warnings = []
            now = datetime.now(timezone.utc)
            for plot in plots:
                for kind in ("guidance", "calendar"):
                    matches = [r for r in self.rows(db, run, kind) if r.data["crop"] == plot["season"]["crop"]
                        and r.data["agroclimatic_zone"] == plot["agroclimatic_zone"]
                        and 0 <= (now.date() - date.fromisoformat(r.data["reviewed_on"])).days <= 365]
                    if kind == "calendar":
                        matches = [r for r in matches if r.data["planting_start"] <= plot["season"]["planting_date"] <= r.data["planting_end"]
                            and r.data["harvest_start"] <= plot["season"]["harvest_date"] <= r.data["harvest_end"]]
                    else:
                        matches = [r for r in matches if r.data.get("supported_actions")]
                    if not matches:
                        fail(422, f"Missing current, locally reviewed {kind} for crop and agroclimatic zone")
                    row = max(matches, key=lambda r: (r.data["reviewed_on"], r.created_at, r.id))
                    ids.append(self.evidence(db, run, officer, plot, kind, f"Locally reviewed {kind}", row.data["text"],
                        values={"supported_actions": row.data.get("supported_actions", []),
                                "planting_rule": row.data.get("planting_rule"),
                                **({k: row.data[k] for k in ("planting_start", "planting_end", "harvest_start", "harvest_end")} if kind == "calendar" else {})}, reference="internal:" + row.id,
                        observed=datetime.combine(date.fromisoformat(row.data["reviewed_on"]), datetime.min.time(), timezone.utc),
                        expires=min(now + timedelta(days=30), datetime.combine(date.fromisoformat(row.data["reviewed_on"]) + timedelta(days=365), datetime.max.time(), timezone.utc))))
                signals = [r.data for r in self.rows(db, run, "evidence") if r.data.get("plot_id") == plot["id"]
                           and r.data["values"].get("kind") == "pest_signal"]
                if signals:
                    warnings.append({"plot_id": plot["id"], "message": "Recorded pest signals need officer field verification", "conflict": len({str(s["values"].get("status")) for s in signals}) > 1, "signals": signals})
            self.authorized(db); db.commit(); return {"evidence_ids": ids, "warnings": warnings}

    async def save(self, inputs):
        with SessionLocal() as db:
            run, officer = self.authorized(db)
            if run.advisory_id:
                return {"advisory_id": run.advisory_id, "version": 1, "status": "draft"}
            payload = validate_candidates(db, run, inputs)
            # Reserve the run link before saving. A second client cannot create
            # another draft during a lost response or concurrent retry.
            claim = db.execute(update(AdvisoryRun).where(AdvisoryRun.id == run.id,
                AdvisoryRun.advisory_id.is_(None), AdvisoryRun.capability_hash == run.capability_hash,
                AdvisoryRun.lease_until > datetime.now(timezone.utc)).values(stage="saving").execution_options(synchronize_session=False))
            if not claim.rowcount: fail(409, "Run changed during save")
            version = WorkspaceService(db, officer).save_advisory(run.office_id, payload, commit=False)
            run.advisory_id = version.advisory_id
            db.commit()
            return {"advisory_id": version.advisory_id, "version": 1, "status": "draft"}
