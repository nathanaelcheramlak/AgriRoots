"""Bounded WGS84 topology checks and geodesic metrics, never square-degree areas."""

import json
import math

from pyproj import Geod
from shapely.geometry import shape
from shapely.ops import orient

from src.integrations.contracts import ConnectorError

GEOD = Geod(ellps="WGS84")


def invalid(message):
    raise ConnectorError("INPUT_VALIDATION_FAILED", message)


def area(geometry):
    # Orient each polygon so holes subtract and multipolygon members add.
    return abs(GEOD.geometry_area_perimeter(orient(geometry, sign=1.0))[0])


def validate_geometry(value, *, plot=False):
    if not isinstance(value, dict) or set(value) != {"type", "coordinates"}:
        invalid("Use a WGS84 GeoJSON geometry with type and coordinates only")
    if value["type"] not in ("Polygon", "MultiPolygon") or len(json.dumps(value)) > 150000:
        invalid("Use a bounded Polygon or MultiPolygon")
    polygons = [value["coordinates"]] if value["type"] == "Polygon" else value["coordinates"]
    if not isinstance(polygons, list) or not 1 <= len(polygons) <= 50:
        invalid("Invalid polygon count")
    count = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not 1 <= len(polygon) <= 50:
            invalid("Invalid ring count")
        for ring in polygon:
            if not isinstance(ring, list) or not 4 <= len(ring) <= 2000 or ring[0] != ring[-1]:
                invalid("Polygon rings must be closed with at least four coordinates")
            for point in ring:
                if (
                    not isinstance(point, (list, tuple))
                    or len(point) != 2
                    or any(
                        isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in point
                    )
                    or not -180 <= point[0] <= 180
                    or not -90 <= point[1] <= 90
                ):
                    invalid("Coordinates must be finite [longitude, latitude] in WGS84")
            count += len(ring)
    if count > 4000:
        invalid("Geometry exceeds 4000 vertices")
    geometry = shape(value)
    if geometry.is_empty or not geometry.is_valid or geometry.bounds[2] - geometry.bounds[0] > 180:
        invalid("Invalid topology or antimeridian crossing")
    size = area(geometry)
    if not 1 <= size <= (10000000 if plot else 10000000000):
        invalid("Geometry area is outside supported limits")
    return geometry, size


def point(geometry):
    return {"type": "Point", "coordinates": [geometry.x, geometry.y]}
