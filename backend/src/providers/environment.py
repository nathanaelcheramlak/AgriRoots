"""Bounded historical water, suitability and vegetation operations."""

import calendar
import json
import math
import re
from datetime import date

from src.integrations.contracts import ConnectorError, ConnectorResult
from src.providers.agriculture import date_range, numeric, require
from src.providers.raster_access import raster_pixel, wapor_object


async def gaez(http, base, args, credential, context):
    # Only this verified scenario is offered. No generic filename interpolation.
    url = base + "/gaez-v4-data/data/res05/CRUTS32/Hist/8110H/sxHr_mze.tif"
    pixel = await raster_pixel(http, url, args["longitude"], args["latitude"], full=True)
    if pixel:
        require(
            0 <= pixel["raw_value"] <= 10000 and all(abs(r - 1 / 12) < 1e-6 for r in pixel["resolution_degrees"]),
            "Invalid GAEZ index or grid",
        )
    return ConnectorResult(
        data_outcome="VALID" if pixel else "NO_DATA",
        data={
            "crop": "maize",
            "scenario": "high_input_rainfed",
            "index": pixel,
            "documented_range": [0, 10000],
            "climate_baseline": "1981-2010",
        },
        source={
            "provider": "FAO GAEZ",
            "url": url,
            "version": "v4",
            "value_kind": "regional_crop_suitability",
            "valid_time_range": {"from": "1981-01-01", "to": "2010-12-31"},
        },
        limitations=[
            "Fixed historical high-input rain-fed maize scenario, 5 arc-minute grid. Not current yield, probability or a standalone planting recommendation."
        ],
    )


async def wapor(http, base, args, credential, context):
    start, end = date_range(args)
    url = base + "/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets/L2-AETI-D"
    # Bounded catalogue scan. Missing coverage is reported, never silently replaced by another date.
    candidates = []
    for page in range(3):
        raw = await http.json("GET", url + "/rasters", params={"page": page, "pageSize": 100})
        items = raw.get("response", {}).get("items", [])
        for raster in items:
            for dimension in raster.get("dimensions", []):
                member = dimension.get("member", {})
                if member.get("startDate") and member.get("endDate"):
                    first, last = member["startDate"][:10], member["endDate"][:10]
                    if first <= str(end) and last >= str(start):
                        candidates.append((last, first, raster))
        if candidates or len(items) < 100:
            break
    if not candidates:
        return ConnectorResult(
            data_outcome="NO_DATA",
            limitations=[
                "No matching WaPOR period in the bounded catalogue scan; broader catalogue coverage is unverified."
            ],
        )
    last, first, selected = max(candidates, key=lambda row: row[0])
    require(
        selected.get("measureUnit") and numeric(selected.get("scale", 1)) and numeric(selected.get("offset", 0)),
        "Missing WaPOR units or scale",
    )
    pixel = await raster_pixel(http, wapor_object(selected), args["longitude"], args["latitude"])
    if pixel:
        pixel["scaled_value"] = pixel["raw_value"] * selected.get("scale", 1) + selected.get("offset", 0)
        require(numeric(pixel["scaled_value"]) and pixel["scaled_value"] >= 0, "Invalid evapotranspiration value")
    return ConnectorResult(
        data_outcome="VALID" if pixel else "NO_DATA",
        data={
            "sample": pixel,
            "raster_code": selected.get("code"),
            "scale": selected.get("scale", 1),
            "offset": selected.get("offset", 0),
        },
        source={
            "provider": "FAO WaPOR",
            "url": url,
            "units": selected["measureUnit"],
            "valid_time_range": {"from": first, "to": last},
            "value_kind": "actual_evapotranspiration",
        },
        limitations=[
            "Satellite-derived regional evapotranspiration. Composite dates may extend beyond the requested interval; not a standalone irrigation prescription."
        ],
    )


def dekad(day):
    return f"{day.year}-{(day.month - 1) * 3 + min((day.day - 1) // 10 + 1, 3):02d}"


async def asis(http, base, args, credential, context):
    start, end = date_range(args)
    item = await http.json(
        "GET",
        "https://www.arcgis.com/sharing/rest/content/items/dd1ddf044a7f4d28972cd7644aceaddc",
        params={"f": "json"},
    )
    url = base + "/image/rest/services/VCI_D/ImageServer"
    require(
        item.get("owner") == "giews_hqfao"
        and item.get("type") == "Image Service"
        and item.get("access") == "public"
        and item.get("url") == url,
        "Unexpected ASIS public service identity",
    )
    meta = await http.json("GET", url, params={"f": "json"})
    require(
        meta.get("bandCount") == 1
        and {"OBJECTID", "Name", "Year_Dekad"} <= {f["name"] for f in meta.get("fields", [])}
        and any(r.get("name") == "None" for r in meta.get("rasterFunctionInfos", [])),
        "Unexpected ASIS schema",
    )
    raw = await http.json(
        "GET",
        url + "/query",
        params={
            "f": "json",
            "where": f"Category = 1 AND Year_Dekad >= '{dekad(start)}' AND Year_Dekad <= '{dekad(end)}'",
            "outFields": "OBJECTID,Name,Year_Dekad",
            "orderByFields": "Year_Dekad DESC",
            "resultRecordCount": 4,
            "returnGeometry": "false",
        },
    )
    require("error" not in raw, "ASIS catalogue query failed")
    rows = raw.get("features", [])
    if not rows:
        return ConnectorResult(data_outcome="NO_DATA", limitations=["No ASIS composite overlaps the requested dates"])
    selected = rows[0]["attributes"]
    match = re.fullmatch(r"ASIS\.VCI-D\.(\d{4})-(\d{2})-D([123])", selected.get("Name", ""))
    require(match and type(selected.get("OBJECTID")) is int, "Invalid ASIS raster identity")
    year, month, part = map(int, match.groups())
    first = date(year, month, (part - 1) * 10 + 1)
    last = date(year, month, part * 10 if part < 3 else calendar.monthrange(year, month)[1])
    require(
        first <= end and last >= start and dekad(first) == selected.get("Year_Dekad"),
        "ASIS dates outside requested interval",
    )
    raw = await http.json(
        "GET",
        url + "/identify",
        params={
            "f": "json",
            "geometryType": "esriGeometryPoint",
            "geometry": json.dumps({"x": args["longitude"], "y": args["latitude"], "spatialReference": {"wkid": 4326}}),
            "mosaicRule": json.dumps({"mosaicMethod": "esriMosaicLockRaster", "lockRasterIds": [selected["OBJECTID"]]}),
            "renderingRule": json.dumps({"rasterFunction": "None"}),
            "returnCatalogItems": "true",
            "returnPixelValues": "true",
            "returnGeometry": "false",
            "maxItemCount": 1,
        },
    )
    require("error" not in raw, "ASIS pixel request failed")
    if raw.get("value") in (None, "NoData", "nodata"):
        return ConnectorResult(data_outcome="NO_DATA", limitations=["ASIS has no valid pixel at this point"])
    try:
        value = float(raw["value"])
    except (ValueError, TypeError):
        raise ConnectorError("OUTPUT_VALIDATION_FAILED", "Invalid ASIS pixel") from None
    require(numeric(value) and 0 <= value <= 1, "ASIS VCI outside normalized 0..1 range")
    require(
        any(
            r.get("attributes", {}).get("OBJECTID") == selected["OBJECTID"]
            for r in raw.get("catalogItems", {}).get("features", [])
        ),
        "ASIS did not confirm selected raster",
    )
    location = raw.get("location", {})
    wkid = location.get("spatialReference", {}).get("latestWkid") or location.get("spatialReference", {}).get("wkid")
    x, y = location.get("x"), location.get("y")
    require(numeric(x) and numeric(y) and wkid in (4326, 3857, 102100), "Invalid ASIS returned location")
    if wkid != 4326:
        x, y = math.degrees(x / 6378137), math.degrees(2 * math.atan(math.exp(y / 6378137)) - math.pi / 2)
    require(abs(x - args["longitude"]) < 0.001 and abs(y - args["latitude"]) < 0.001, "ASIS returned another location")
    return ConnectorResult(
        data={"vci": value, "documented_range": [0, 1], "raster": selected},
        source={
            "provider": "FAO ASIS",
            "url": url,
            "units": "dimensionless normalized index",
            "valid_time_range": {"from": str(first), "to": str(last)},
            "value_kind": "vegetation_condition",
        },
        limitations=[
            "Historical regional vegetation condition at approximately 1 km; not pest diagnosis or standalone drought confirmation."
        ],
    )
