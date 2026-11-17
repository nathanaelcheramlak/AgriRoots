import json
from pathlib import Path


def inventory():
    path = Path(__file__).resolve().parents[2] / "reports/provider_inventory.json"
    return (
        json.loads(path.read_text(encoding="utf-8"))
        if path.is_file()
        else {"providers": [], "note": "Historical inventory has not been imported"}
    )


# Stable public provider identities; implementations remain operator-owned in factory.
PROVIDER_HANDLERS = {
    "open_meteo": "open_meteo.forecast", "nasa_power": "nasa_power.history",
    "isda_soil": "isda.soil_profile", "chirps": "chirps.rainfall_history",
    "fao_fpma": "fpma.ethiopia_prices", "fao_locust": "fao.locust_observations",
    "eppo": "eppo.names", "wfp_prices": "hapi.ethiopia_prices",
    "openrouteservice": "ors.driving_route", "kindwise": "kindwise.diagnosis",
    "fao_gaez": "gaez.maize_suitability", "fao_wapor": "wapor.evapotranspiration",
    "fao_asis": "asis.vegetation_condition", "google_earth_engine": "gee.modis_ndvi",
}


def catalog():
    """Current implementation metadata, without rewriting historical verification."""
    from src.providers.factory import HANDLERS

    document = inventory()
    rows = []
    for original in document["providers"]:
        row = dict(original)
        handler_id = PROVIDER_HANDLERS.get(row["id"])
        definition = HANDLERS.get(handler_id)
        row.update(handler_id=handler_id if definition else None,
                   implemented=bool(definition),
                   implemented_capabilities=[definition["capability"]] if definition else [])
        # An old import's missing-handler blocker is not current implementation state.
        row["implementation_blocker"] = None if definition else row.get("blocker") or "No reviewed backend adapter"
        rows.append(row)
    return {**document, "providers": rows}
