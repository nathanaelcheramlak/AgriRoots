"""Decisions from dated evidence and officer-entered thresholds, never model prose."""
from datetime import timedelta
from src.api.schemas.workspace import PlantingRule
from src.services.workspace_service import fail


def eligible_decision(plot, evidence, proposed_date, conflicts):
    by_kind = {e["values"]["kind"]: e for e in evidence if e.get("plot_id") == plot["id"]}
    guidance = by_kind.get("guidance", {}).get("values", {})
    supported = set(guidance.get("supported_actions", []))
    if any(w.get("plot_id") == plot["id"] and w.get("conflict") for w in conflicts):
        return {"actions": sorted(supported & {"request_field_visit"}),
                "basis": "Recorded pest reports disagree. A field visit is required before a planting decision."}
    if plot["season"].get("stage", "growing") != "planned":
        return {"actions": sorted(supported - {"plant_crop", "hold_planting"}),
                "basis": "The recorded crop is already growing; local guidance supports inspection and officer follow-up."}
    raw_rule = guidance.get("planting_rule")
    if not raw_rule:
        fail(422, "Planned crops require explicit locally reviewed planting rules")
    rule = PlantingRule.model_validate(raw_rule)
    calendar = by_kind.get("calendar", {}).get("values", {})
    start, end = calendar.get("planting_start"), calendar.get("planting_end")
    if not start or not end:
        fail(422, "Planting decisions require a reviewed calendar window")
    days = by_kind.get("weather", {}).get("values", {}).get("forecast_days", [])
    forecast = {d["date"]: d for d in days}
    required = [(proposed_date + timedelta(days=i)).isoformat() for i in range(rule.rain_days)]
    if any(day not in forecast for day in required):
        fail(422, "Forecast does not cover the entire locally reviewed rainfall window")
    selected = [forecast[day] for day in required]
    rain = sum(d["rain_mm"] for d in selected)
    temperature = max(d["temp_max_c"] for d in selected)
    wind = max(d["wind_kph"] for d in selected)
    reasons = []
    if not start <= proposed_date.isoformat() <= end: reasons.append("outside the reviewed planting window")
    if not rule.minimum_rain_mm <= rain <= rule.maximum_rain_mm: reasons.append("rainfall outside the reviewed range")
    if temperature > rule.maximum_temperature_c: reasons.append("temperature above the reviewed limit")
    if wind > rule.maximum_wind_kph: reasons.append("wind above the reviewed limit")
    action = "hold_planting" if reasons else "plant_crop"
    basis = (f"Forecast {required[0]}–{required[-1]}: rain {rain:g} mm "
             f"(reviewed range {rule.minimum_rain_mm:g}–{rule.maximum_rain_mm:g} mm), "
             f"maximum temperature {temperature:g} °C (limit {rule.maximum_temperature_c:g} °C), "
             f"maximum wind {wind:g} km/h (limit {rule.maximum_wind_kph:g} km/h). "
             f"Reviewed planting window {start}–{end}. "
             + ("Hold: " + "; ".join(reasons) + "." if reasons else "Forecast meets the office's recorded thresholds; field readiness remains unverified."))
    return {"actions": [action] if action in supported else [], "basis": basis}
