"""Production forms of the previously verified f-test request/validation behavior.

All requests, including authentication and asynchronous polling, use the injected
controlled HTTP client. No adapter imports the standalone test harness or its .env.
"""

import asyncio
import json
import math
from datetime import UTC, date, datetime, timedelta, timezone

from src.integrations.contracts import ConnectorError, ConnectorResult


def require(condition, message):
    if not condition:
        raise ConnectorError("OUTPUT_VALIDATION_FAILED", message)


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def date_range(arguments):
    try:
        start, end = date.fromisoformat(arguments["start"]), date.fromisoformat(arguments["end"])
    except (ValueError, KeyError):
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Historical dates must be ISO calendar dates") from None
    if not start <= end < date.today() or (end - start).days > 30:
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Use a past historical window of at most 31 days")
    return start, end


async def open_meteo(http, base, args, credential, context):
    data = await http.json(
        "GET",
        base + "/v1/forecast",
        params={
            "latitude": args["latitude"],
            "longitude": args["longitude"],
            "daily": "temperature_2m_max,precipitation_sum,et0_fao_evapotranspiration,wind_speed_10m_max",
            "forecast_days": 3,
            "timezone": "Africa/Addis_Ababa",
        },
        attempts=2,
    )
    require(
        abs(data.get("latitude", 999) - args["latitude"]) < 0.3
        and abs(data.get("longitude", 999) - args["longitude"]) < 0.3,
        "Forecast coordinates do not cover the authorized point",
    )
    daily = data.get("daily", {})
    units = data.get("daily_units", {})
    expected = {
        "temperature_2m_max": "°C",
        "precipitation_sum": "mm",
        "et0_fao_evapotranspiration": "mm",
        "wind_speed_10m_max": "km/h",
    }
    dates = daily.get("time", [])
    today = datetime.now(timezone(timedelta(hours=3))).date()
    require(
        dates == [(today + timedelta(days=i)).isoformat() for i in range(3)],
        "Forecast has missing, duplicated or stale dates",
    )
    for field, unit in expected.items():
        values = daily.get(field, [])
        require(
            units.get(field) == unit and len(values) == 3 and all(numeric(v) for v in values),
            "Invalid forecast values or units: " + field,
        )
        if field != "temperature_2m_max":
            require(all(v >= 0 for v in values), "Negative forecast precipitation, ET0 or wind")
    return ConnectorResult(
        data={"daily": daily, "units": units, "source_coordinates": [data["longitude"], data["latitude"]]},
        source={
            "provider": "Open-Meteo",
            "url": base + "/v1/forecast",
            "value_kind": "modelled_forecast",
            "valid_time_range": {"from": dates[0], "to": dates[-1]},
            "units": units,
            "attribution": "https://open-meteo.com/en/licence",
        },
        limitations=["Gridded model forecast; not a plot sensor reading. Forecast issue time was not supplied."],
    )


def validate_power(data, args):
    start, end = date_range(args)
    fields = {"T2M": "C", "PRECTOTCORR": "mm/day", "RH2M": "%", "WS2M": "m/s", "ALLSKY_SFC_SW_DWN": "MJ/m^2/day"}
    dates = {(start + timedelta(days=i)).strftime("%Y%m%d") for i in range((end - start).days + 1)}
    parameters = data.get("properties", {}).get("parameter", {})
    for name, unit in fields.items():
        values = parameters.get(name, {})
        require(
            set(values) == dates and all(numeric(v) and v not in (-999, -9999) for v in values.values()),
            "Missing POWER daily values: " + name,
        )
        require(data.get("parameters", {}).get(name, {}).get("units") == unit, "Unexpected POWER units: " + name)
    location = data.get("geometry") or data.get("location", {})
    coordinates = location.get("coordinates", [])
    require(
        len(coordinates) >= 2
        and abs(coordinates[0] - args["longitude"]) < 0.6
        and abs(coordinates[1] - args["latitude"]) < 0.6,
        "POWER coordinates do not cover the authorized point",
    )
    return {
        "daily_records": parameters,
        "parameters": data["parameters"],
        "source_location": location,
        "time_standard": (data.get("header") or data.get("meta", {})).get("time_standard"),
    }


async def nasa_power(http, base, args, credential, context):
    start, end = date_range(args)
    data = await http.json(
        "GET",
        base + "/api/temporal/daily/point",
        params={
            "latitude": args["latitude"],
            "longitude": args["longitude"],
            "community": "AG",
            "parameters": "T2M,PRECTOTCORR,RH2M,WS2M,ALLSKY_SFC_SW_DWN",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": "UTC",
        },
        attempts=2,
    )
    sample = validate_power(data, args)
    return ConnectorResult(
        data=sample,
        source={
            "provider": "NASA POWER",
            "url": base + "/api/temporal/daily/point",
            "value_kind": "historical_agroclimate",
            "valid_time_range": {"from": start.isoformat(), "to": end.isoformat()},
            "units": data["parameters"],
        },
        limitations=["Gridded historical estimates; not a current forecast or field measurement."],
    )


async def isda(http, base, args, credential, context):
    if not isinstance(credential, dict) or not credential.get("username") or not credential.get("password"):
        raise ConnectorError(
            "AUTH_REQUIRED", "This iSDA connection requires its own username/password credential object"
        )
    login = await http.json(
        "POST", base + "/login", form={"username": credential["username"], "password": credential["password"]}
    )
    token = login.get("access_token")
    require(
        isinstance(token, str) and token and login.get("token_type", "bearer").lower() == "bearer",
        "iSDA login returned no bearer token",
    )
    headers = {"Authorization": "Bearer " + token}
    layers = await http.json("GET", base + "/isdasoil/v2/layers", headers=headers)
    available = layers.get("property", {})
    require(isinstance(available, dict) and available, "No iSDA property metadata")
    properties, metadata, limitations = {}, {}, []
    wanted = [
        "ph",
        "carbon_organic",
        "clay_content",
        "sand_content",
        "silt_content",
        "nitrogen_total",
        "phosphorous_extractable",
        "potassium_extractable",
    ]
    for prop in wanted:
        layer = available.get(prop, {})
        if "0-20" not in layer.get("depths", {}).get("values", []):
            limitations.append(prop + ": requested depth unavailable")
            continue
        data = await http.json(
            "GET",
            base + "/isdasoil/v2/soilproperty",
            headers=headers,
            params={"lat": args["latitude"], "lon": args["longitude"], "property": prop, "depth": "0-20"},
        )
        rows = data.get("property", {}).get(prop, [])
        require(isinstance(rows, list) and rows, "No iSDA property values: " + prop)
        for item in rows:
            value, depth = item.get("value", {}), item.get("depth", {})
            require(numeric(value.get("value")) and value["value"] >= 0, "Invalid iSDA value: " + prop)
            require(depth.get("value") == "0-20" and depth.get("unit") == "cm", "Unexpected iSDA depth")
            require((value.get("unit") or None) == (layer.get("unit") or None), "iSDA units differ from layer metadata")
            if prop == "ph":
                require(value["value"] <= 14, "iSDA pH outside 0–14")
            if value.get("unit") == "%":
                require(value["value"] <= 100, "iSDA percentage outside 0–100")
            uncertainty = item.get("uncertainty")
            intervals = [uncertainty] if isinstance(uncertainty, dict) else uncertainty or []
            require(isinstance(intervals, list), "Invalid iSDA uncertainty")
            for interval in intervals:
                require(
                    interval.get("confidence_interval")
                    and numeric(interval.get("lower_bound"))
                    and numeric(interval.get("upper_bound"))
                    and interval["lower_bound"] <= interval["upper_bound"],
                    "Invalid iSDA uncertainty bounds",
                )
        properties[prop] = rows
        metadata[prop] = {name: layer.get(name) for name in ("description", "unit", "depths", "uncertainty")}
    require(
        "ph" in properties and "carbon_organic" in properties, "Required pH and organic-carbon estimates are missing"
    )
    return ConnectorResult(
        data={
            "requested_coordinates": [args["longitude"], args["latitude"]],
            "depth_cm": [0, 20],
            "properties": properties,
            "metadata": metadata,
        },
        source={
            "provider": "iSDAsoil",
            "url": base + "/isdasoil/v2/soilproperty",
            "value_kind": "mapped_soil_estimate",
            "depth_cm": [0, 20],
            "attribution": "iSDAsoil; CC BY 4.0",
        },
        model_data={
            "depth_cm": [0, 20],
            "properties": {
                prop: [{key: row.get(key) for key in ("value", "depth", "uncertainty")} for row in rows[:1]]
                for prop, rows in properties.items()
            },
        },
        limitations=limitations
        + ["Mapped estimates, not laboratory samples. Response does not echo coordinates or supply observation dates."],
    )


async def chirps(http, base, args, credential, context):
    start, end = date_range(args)
    lat, lon = args["latitude"], args["longitude"]
    require(
        -59.999 <= lat <= 59.999 and -179.999 <= lon <= 179.999,
        "CHIRPS supports latitude -60..60 without dateline crossing",
    )
    # CHIRPS cells are 0.05 degrees. A 0.002-degree box can miss all cell centres.
    half_cell = 0.025
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - half_cell, lat - half_cell],
                [lon + half_cell, lat - half_cell],
                [lon + half_cell, lat + half_cell],
                [lon - half_cell, lat + half_cell],
                [lon - half_cell, lat - half_cell],
            ]
        ],
    }
    # Current ClimateSERV 2 developer documentation uses /api/. The legacy
    # /chirps/ routes now return the website rather than a JSON job response.
    api = base + "/api/"
    from src.integrations.contracts import digest

    fingerprint = digest({"start": str(start), "end": str(end), "polygon": polygon})
    prior = args.get("resume_invocation_id")
    if prior:
        state = http.gate.load_provider_state(prior, "chirps_job")
        require(
            state and state.get("fingerprint") == fingerprint and state.get("job_id"),
            "No matching resumable CHIRPS job",
        )
        job_id = state["job_id"]
    else:
        http.gate.save_provider_state("chirps_job", {"fingerprint": fingerprint, "state": "submission_attempted"})
        job = await http.json(
            "GET",
            api + "submitDataRequest/",
            params={
                "datatype": 0,
                "begintime": start.strftime("%m/%d/%Y"),
                "endtime": end.strftime("%m/%d/%Y"),
                "intervaltype": 0,
                "operationtype": 5,
                "geometry": json.dumps(polygon),
            },
            attempts=1,
            legacy_climateserv_json=True,
        )
        job_id = job[0] if isinstance(job, list) and job else job
        require(isinstance(job_id, str) and len(job_id) >= 20, "ClimateSERV did not return a job identifier")
    http.gate.save_provider_state("chirps_job", {"fingerprint": fingerprint, "state": "submitted", "job_id": job_id})
    for _ in range(30):
        progress = await http.json(
            "GET", api + "getDataRequestProgress/", params={"id": job_id}, legacy_climateserv_json=True
        )
        if isinstance(progress, list):
            progress = progress[0]
        require(numeric(progress) and progress >= 0, "ClimateSERV processing failed")
        if progress >= 100:
            break
        await asyncio.sleep(2)
    else:
        raise ConnectorError(
            "TIMEOUT", "ClimateSERV job remains incomplete; submission was not repeated", retryable=False
        )
    raw = await http.json("GET", api + "getDataFromRequest/", params={"id": job_id}, legacy_climateserv_json=True)
    rows = raw.get("data", [])
    if not rows:
        return ConnectorResult(
            data_outcome="NO_DATA",
            limitations=[
                "ClimateSERV returned no daily rainfall for this location and period. No values were substituted; try an older month."
            ],
        )
    dates = []
    for row in rows:
        value = row.get("value", {}).get("avg")
        day = datetime.strptime(row["date"], "%m/%d/%Y").date()
        require(numeric(value) and value >= 0 and start <= day <= end, "Invalid ClimateSERV rainfall/date")
        dates.append(day)
    require(len(set(dates)) == len(dates) == (end - start).days + 1, "Incomplete ClimateSERV daily data")
    return ConnectorResult(
        data={
            "job_id": job_id,
            "polygon": polygon,
            "units": "mm",
            "data": rows,
            "summary": {
                "total_mm": round(sum(row["value"]["avg"] for row in rows), 4),
                "day_count": len(rows),
                "from": str(start),
                "to": str(end),
                "method": "Sum of validated daily spatial-average rainfall; not a whole-territory total",
            },
        },
        source={
            "provider": "CHIRPS / ClimateSERV",
            "url": api,
            "valid_time_range": {"from": str(start), "to": str(end)},
            "units": "mm",
            "spatial_resolution": "0.05 degrees",
            "spatial_support": "0.05-degree box around the authorized territory representative point"
            if getattr(context, "territory_id", None)
            else "0.05-degree box around the authorized plot point",
        },
        limitations=[
            "Historical rainfall estimates over a representative-point 0.05-degree box, not an average of the full farm or territory boundary. Missing days are not replaced with zeros. Resume a timed-out job using its invocation ID."
        ],
    )


def records(data):
    if isinstance(data, list):
        return data
    for key in ("results", "data", "items", "features", "response"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


async def fpma(http, base, args, credential, context):
    api = base + "/giews/v4/global/price_module/api/v1/"
    raw = await http.json("GET", api + "FpmaSerie/", params={"iso3_country_codes": "ETH"})
    series = [row for row in records(raw) if row.get("iso3_country_code") == "ETH" and row.get("periodicity")]
    if not series:
        return ConnectorResult(data_outcome="NO_DATA", limitations=["No Ethiopian series returned"])
    for field in ("market_name", "commodity_name"):
        if args.get(field):
            series = [row for row in series if row.get(field, "").casefold() == args[field].casefold()]
    if not series:
        return ConnectorResult(
            data_outcome="NO_DATA", limitations=["No Ethiopian series matches the requested market/commodity"]
        )
    chosen = max(
        series,
        key=lambda row: (
            row.get("market_name", "").lower().startswith("adama"),
            max(p.get("end_date", "") for p in row["periodicity"]),
        ),
    )
    periodicity = max(chosen["periodicity"], key=lambda p: p.get("end_date", ""))
    data = await http.json(
        "GET", api + "FpmaSeriePrice/", params={"uuid__in": chosen["uuid"], "periodicity": periodicity["period"]}
    )
    prices = [
        point for row in records(data) if row.get("uuid") == chosen["uuid"] for point in row.get("datapoints", [])
    ]
    if not prices:
        return ConnectorResult(data_outcome="NO_DATA", limitations=["No price datapoints for the selected series"])
    for point in prices:
        require(
            numeric(point.get("price_value"))
            and point["price_value"] > 0
            and date.fromisoformat(point["date"]) <= date.today(),
            "Invalid FPMA price/date",
        )
    for field in ("currency", "measure_unit_label", "commodity_name", "market_name"):
        require(chosen.get(field), "FPMA series metadata missing: " + field)
    return ConnectorResult(
        data={"series_metadata": chosen, "last_five_prices": sorted(prices, key=lambda row: row["date"])[-5:]},
        source={
            "provider": "FAO FPMA",
            "url": api,
            "observed_at": max(p["date"] for p in prices),
            "currency": chosen["currency"],
            "units": chosen["measure_unit_label"],
            "country": "ETH",
        },
        limitations=["Historical indicative market prices; not farm-gate quotes or binding offers."],
    )


async def locust(http, base, args, credential, context):
    search = await http.json(
        "GET",
        base + "/sharing/rest/search",
        params={"f": "json", "q": 'owner:faodlis_hqfao AND type:"Feature Service"', "num": 20},
    )
    candidates = [
        r
        for r in search.get("results", [])
        if r.get("owner") == "faodlis_hqfao" and "observation" in r.get("title", "").lower()
    ]
    require(candidates, "No public FAO-owned locust observation service")
    item = candidates[0]
    service = item.get("url", "")
    require(service.startswith("https://services5.arcgis.com/sjP4Ugu5s0dZWLjd/"), "Unexpected FAO service owner/origin")
    meta = await http.json("GET", service, params={"f": "json"})
    require(meta.get("layers"), "Locust observation layers missing")
    layer = str(meta["layers"][0]["id"])
    details = await http.json("GET", service + "/" + layer, params={"f": "json"})
    fields = [f["name"] for f in details.get("fields", [])]
    country = next((f for f in fields if f.lower() in ("country", "country_name", "countryname")), None)
    date_field = next((f for f in ("Obs_Date", "Day") if f in fields), None)
    require(date_field, "No recognized locust observation date field")
    params = {
        "f": "json",
        "where": f"{country} = 'Ethiopia'" if country else "1=1",
        "geometry": "33,3,48,15",
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(
            f for f in [country, date_field, "Region", "Locust_Presence", "Locust_Type"] if f and f in fields
        ),
        "returnGeometry": "true",
        "outSR": 4326,
        "resultRecordCount": 5,
    }
    if details.get("advancedQueryCapabilities", {}).get("supportsOrderBy"):
        params["orderByFields"] = date_field + " DESC"
    raw = await http.json("GET", service + "/" + layer + "/query", params=params)
    require("error" not in raw, "ArcGIS query returned an error")
    observations = raw.get("features", [])
    if not observations:
        return ConnectorResult(
            data_outcome="NO_DATA", limitations=["No matching locust observations; not evidence of low risk"]
        )
    for row in observations:
        geometry, values = row.get("geometry", {}), row.get("attributes", {})
        require(
            numeric(geometry.get("x"))
            and numeric(geometry.get("y"))
            and 33 <= geometry["x"] <= 48
            and 3 <= geometry["y"] <= 15,
            "Locust observation lies outside requested region",
        )
        require(numeric(values.get(date_field)), "Locust observation timestamp is missing")
        observed = datetime.fromtimestamp(values[date_field] / 1000, UTC)
        require(1980 <= observed.year and observed <= datetime.now(UTC), "Invalid locust observation date")
        if country:
            require(values.get(country) == "Ethiopia", "Locust country filter was not respected")
        row["observed_at"] = observed.isoformat()
    return ConnectorResult(
        data={"observations": observations, "country_field": country},
        source={
            "provider": "FAO Locust Hub",
            "url": service,
            "source_item_id": item["id"],
            "value_kind": "reported_locust_observations",
        },
        limitations=[
            "Historical observations, not a current outbreak warning. Regional bounding box includes neighboring territory when country is absent."
        ],
    )
