"""Reviewed pest, market and route operations. No provider URLs come from model inputs."""

import base64
import re
from datetime import date

from src.integrations.contracts import ConnectorError, ConnectorResult
from src.providers.agriculture import date_range, numeric, records, require


def key(value):
    if not isinstance(value, str) or not value or any(c in value for c in "\r\n"):
        raise ConnectorError("AUTH_REQUIRED", "Attach this provider's connection-owned credential")
    return value


async def eppo(http, base, args, credential, context):
    code = args["eppo_code"]
    require(re.fullmatch(r"[0-9A-Z]{5,6}", code), "Invalid EPPO code")
    url = base + "/gd/v2/taxons/taxon/" + code + "/names"
    rows = await http.json("GET", url, headers={"X-Api-Key": key(credential)})
    require(isinstance(rows, list), "Invalid EPPO names response")
    if not rows:
        return ConnectorResult(data_outcome="NO_DATA", limitations=["No names returned for this EPPO code"])
    for row in rows:
        require(
            isinstance(row, dict)
            and isinstance(row.get("fullname"), str)
            and row["fullname"].strip()
            and isinstance(row.get("preferred"), bool)
            and isinstance(row.get("lang_iso"), str),
            "Invalid EPPO name metadata",
        )
    return ConnectorResult(
        data={"eppo_code": code, "names": rows[:100]},
        source={"provider": "EPPO Global Database", "url": url, "value_kind": "taxon_names"},
        limitations=["Names establish taxonomic references, not local occurrence or treatment suitability."],
    )


async def hapi(http, base, args, credential, context):
    start, end = date_range(args)
    url = base + "/api/v2/food-security-nutrition-poverty/food-prices-market-monitor"
    rows = records(
        await http.json(
            "GET",
            url,
            params={
                "location_code": "ETH",
                "limit": 5,
                "output_format": "json",
                "start_date": str(start),
                "end_date": str(end),
                "app_identifier": key(credential),
            },
        )
    )
    for row in rows:
        require(
            row.get("location_code") == "ETH" and numeric(row.get("price")) and row["price"] >= 0,
            "Invalid Ethiopian food price",
        )
        require(
            all(
                row.get(k)
                for k in (
                    "commodity_name",
                    "market_name",
                    "currency_code",
                    "unit",
                    "reference_period_start",
                    "resource_hdx_id",
                    "price_type",
                    "price_flag",
                )
            ),
            "Missing price provenance, units or type",
        )
        first = date.fromisoformat(row["reference_period_start"][:10])
        last = date.fromisoformat((row.get("reference_period_end") or row["reference_period_start"])[:10])
        require(first <= last and first <= end and last >= start, "Price period outside requested interval")
    return ConnectorResult(
        data_outcome="VALID" if rows else "NO_DATA",
        data={"records": rows},
        model_data={
            "records": [
                {
                    k: row.get(k)
                    for k in (
                        "price",
                        "commodity_name",
                        "market_name",
                        "currency_code",
                        "unit",
                        "reference_period_start",
                        "reference_period_end",
                        "price_type",
                        "price_flag",
                        "resource_hdx_id",
                    )
                }
                for row in rows
            ]
        },
        source={
            "provider": "WFP / HDX HAPI",
            "url": url,
            "country": "ETH",
            "valid_time_range": {"from": str(start), "to": str(end)},
            "value_kind": "historical_market_prices",
        },
        limitations=[
            "Historical market prices, not farm-gate offers. Compare only matching commodities, units, currencies and price types."
        ],
    )


async def route(http, base, args, credential, context):
    points = {p["id"]: p for p in context.plots}
    require(
        args["from_plot_id"] in points and args["to_plot_id"] in points and args["from_plot_id"] != args["to_plot_id"],
        "Route requires two distinct authorized plot references",
    )
    targets = [[points[args[k]]["longitude"], points[args[k]]["latitude"]] for k in ("from_plot_id", "to_plot_id")]
    url = base + "/openrouteservice/v2/directions/driving-car/geojson"
    raw = await http.json(
        "POST",
        url,
        headers={"Authorization": key(credential), "Accept": "application/geo+json"},
        body={"coordinates": targets},
    )
    rows = raw.get("features", [])
    require(rows, "No driving route returned")
    summary = rows[0].get("properties", {}).get("summary", {})
    require(all(numeric(summary.get(k)) and summary[k] > 0 for k in ("distance", "duration")), "Invalid route summary")
    geometry = rows[0].get("geometry", {})
    coords = geometry.get("coordinates", [])
    require(
        geometry.get("type") == "LineString"
        and len(coords) >= 2
        and all(
            isinstance(c, list)
            and len(c) >= 2
            and numeric(c[0])
            and numeric(c[1])
            and -180 <= c[0] <= 180
            and -90 <= c[1] <= 90
            for c in coords
        ),
        "Invalid route geometry",
    )
    require(
        all(
            abs(a - b) < 0.1
            for actual, target in ((coords[0], targets[0]), (coords[-1], targets[-1]))
            for a, b in zip(actual[:2], target)
        ),
        "Unexpected route endpoints",
    )
    return ConnectorResult(
        data={
            "distance": summary["distance"],
            "duration": summary["duration"],
            "from_plot_id": args["from_plot_id"],
            "to_plot_id": args["to_plot_id"],
            "route_start": coords[0],
            "route_end": coords[-1],
            "geometry_point_count": len(coords),
        },
        model_data={
            "distance": summary["distance"],
            "duration": summary["duration"],
            "from_plot_id": args["from_plot_id"],
            "to_plot_id": args["to_plot_id"],
        },
        source={
            "provider": "OpenRouteService",
            "url": url,
            "units": {"distance": "metres", "duration": "seconds"},
            "value_kind": "estimated_driving_route",
        },
        limitations=[
            "Estimated driving time, not live traffic or verified road passability. No isochrones or cost estimates."
        ],
    )


async def kindwise(http, base, args, credential, context):
    from src.services.image_asset_service import claim_diagnosis, complete_diagnosis

    if not context.authorize_credit_use:
        raise ConnectorError("POLICY_DENIED", "This diagnosis requires credit-use authorization")
    # Claim is committed before transmission. An interrupted/ambiguous request cannot silently spend again.
    api_key = key(credential)
    image, asset_digest = claim_diagnosis(context, args["image_asset_id"])
    url = base + "/api/v1/identification"
    raw = await http.json(
        "POST", url, headers={"Api-Key": api_key}, body={"images": [base64.b64encode(image).decode("ascii")]}
    )
    result = raw.get("result", {})
    crops = result.get("crop", {}).get("suggestions", [])
    diseases = result.get("disease", {}).get("suggestions", [])
    require(crops and diseases, "No crop and disease candidates returned")
    for row in crops + diseases:
        require(
            isinstance(row.get("name"), str)
            and row["name"]
            and numeric(row.get("probability"))
            and 0 <= row["probability"] <= 1,
            "Invalid crop-health candidate",
        )
    data = {
        "image_sha256": asset_digest,
        "crop_candidates": [
            {"name": r["name"], "probability": r["probability"], "confidence_percent": round(r["probability"] * 100, 2)}
            for r in crops[:3]
        ],
        "disease_candidates": [
            {"name": r["name"], "probability": r["probability"], "confidence_percent": round(r["probability"] * 100, 2)}
            for r in diseases[:3]
        ],
    }
    complete_diagnosis(context, asset_digest)
    return ConnectorResult(
        data=data,
        source={"provider": "Kindwise Crop.health", "url": url, "value_kind": "photo_diagnosis_candidates"},
        limitations=["Photo candidates are not a confirmed diagnosis, field validation or a treatment prescription."],
    )
