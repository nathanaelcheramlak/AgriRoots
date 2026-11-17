"""Earth Engine SDK with all HTTP (including discovery/auth) routed through the executor."""

import asyncio
import re
import threading
from datetime import timedelta
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from src.integrations.contracts import ConnectorError, ConnectorResult
from src.providers.agriculture import date_range, numeric, require

_sdk_lock = threading.Lock()  # SDK configuration is process-global; never share two projects concurrently.


async def earth_engine(http, base, args, credential, context):
    start, end = date_range(args)
    if not isinstance(credential, dict) or not all(
        credential.get(k) for k in ("project", "refresh_token", "client_id", "client_secret")
    ):
        raise ConnectorError("AUTH_REQUIRED", "Attach an Earth Engine project and authorized-user OAuth credential")
    project = credential["project"]
    require(re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project), "Invalid Earth Engine project ID")
    try:
        import ee
        import httplib2
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise ConnectorError("UNSUPPORTED_CAPABILITY", "Install the backend earthengine dependency group") from None
    # Refresh is explicit and accounted. SDK receives a fresh token, not refresh credentials.
    login = await http.raw(
        "POST",
        "https://oauth2.googleapis.com/token",
        form={
            "grant_type": "refresh_token",
            "refresh_token": credential["refresh_token"],
            "client_id": credential["client_id"],
            "client_secret": credential["client_secret"],
        },
    )
    try:
        token = login.json()["access_token"]
    except (ValueError, KeyError):
        raise ConnectorError("AUTH_INVALID", "Earth Engine token refresh failed") from None
    require(isinstance(token, str) and token, "Missing Earth Engine access token")
    loop = asyncio.get_running_loop()

    class Transport:
        timeout = http.timeout
        follow_redirects = False
        redirect_codes = ()

        def request(self, uri, method="GET", body=None, headers=None, redirections=0, connection_type=None, **kwargs):
            parts = urlsplit(uri)
            require(parts.hostname == "earthengine.googleapis.com", "SDK attempted an unexpected destination")
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            response = asyncio.run_coroutine_threadsafe(
                http.raw(method, url, params=list(parse_qsl(parts.query)), headers=dict(headers or {}), content=body),
                loop,
            ).result()
            return httplib2.Response({"status": str(response.status_code), **dict(response.headers)}), response.content

    def compute():
        with _sdk_lock:
            # Global setup and teardown are serialized. No SDK-native network transport is used.
            ee.Reset()
            ee.data.setMaxRetries(0)
            try:
                ee.Initialize(credentials=Credentials(token=token), project=project, http_transport=Transport())
                ee.data.setMaxRetries(0)
                ee.data.setDeadline(int(http.timeout * 1000))
                area = ee.Geometry.Point([args["longitude"], args["latitude"]]).buffer(500)
                collection = (
                    ee.ImageCollection("MODIS/061/MOD13Q1")
                    .filterBounds(area)
                    .filterDate(str(start), str(end + timedelta(days=1)))
                    .sort("system:time_start", False)
                    .limit(4)
                )

                def summarize(item):
                    image = ee.Image(item)
                    raw = image.select("NDVI")
                    ndvi = (
                        raw.updateMask(raw.gte(-2000).And(raw.lte(10000)))
                        .updateMask(image.select("SummaryQA").eq(0))
                        .multiply(0.0001)
                    )
                    stats = ndvi.reduceRegion(
                        ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
                        geometry=area,
                        scale=250,
                        maxPixels=100,
                    )
                    return ee.Feature(
                        None,
                        {
                            "ndvi": stats.get("NDVI_mean"),
                            "valid_pixel_count": stats.get("NDVI_count"),
                            "observation_date": image.date().format("YYYY-MM-dd"),
                            "image_id": image.id(),
                        },
                    )

                return ee.FeatureCollection(collection.toList(4).map(summarize)).getInfo()
            finally:
                ee.Reset()

    try:
        raw = await asyncio.to_thread(compute)
    except ConnectorError:
        raise
    except Exception:  # noqa: BLE001 -- SDK errors may contain credentials or request bodies
        raise ConnectorError(
            "UPSTREAM_ERROR", "Earth Engine initialization or computation failed; inspect sanitized HTTP attempts"
        ) from None
    rows = [r.get("properties", {}) for r in raw.get("features", [])]
    require(len(rows) <= 4, "Earth Engine exceeded the composite bound")
    valid = []
    for row in rows:
        require(
            str(start) <= row.get("observation_date", "") <= str(end) and row.get("image_id"),
            "Invalid MODIS observation identity/date",
        )
        count = row.get("valid_pixel_count")
        require(numeric(count) and 0 <= count <= 100, "Invalid MODIS valid-pixel count")
        if count > 0:
            require(numeric(row.get("ndvi")) and -0.2 <= row["ndvi"] <= 1, "Invalid quality-filtered NDVI")
            valid.append(row)
    return ConnectorResult(
        data_outcome="VALID" if valid else "NO_DATA",
        data={"observations": rows, "dataset": "MODIS/061/MOD13Q1", "radius_metres": 500, "scale_metres": 250},
        source={
            "provider": "Google Earth Engine",
            "url": base + "/v1/projects/" + project + "/value:compute",
            "units": "NDVI dimensionless",
            "value_kind": "historical_vegetation_greenness",
            "valid_time_range": {"from": str(start), "to": str(end)},
        },
        limitations=[
            "Quality-filtered MODIS 16-day composites over a 500 m plot-centred buffer, not a farm boundary or current disease diagnosis. Dates identify composite starts. No valid pixels means unknown."
        ],
    )
