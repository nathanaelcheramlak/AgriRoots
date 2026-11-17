"""Versioned tools and officer instructions for the 14 independently verified providers."""

from src.providers.factory import template

PROVIDERS = {
    "open_meteo": (
        "open_meteo.forecast",
        "weather_forecast",
        "Explain the dated short-term weather forecast, including units and model limitations. It cannot establish full-season conditions.",
    ),
    "isda_soil": (
        "isda.soil_profile",
        "soil_profile",
        "Explain mapped soil estimates, depths and uncertainty. Do not infer laboratory results, exact fertilizer doses or missing soil properties.",
    ),
    "nasa_power": (
        "nasa_power.history",
        "climate_history",
        "Use the requested past date range to explain historical climate. Historical observations are not a forecast.",
    ),
    "chirps": (
        "chirps.rainfall_history",
        "rainfall_history",
        "Explain historical rainfall over the authorized plot-centred box. Preserve dates and spatial-average units. For a saved incomplete job use resume_invocation_id; never automatically repeat an uncertain submission.",
    ),
    "fao_fpma": (
        "fpma.ethiopia_prices",
        "fpma_market_prices",
        "Explain the actual returned Ethiopian commodity and market price history, retaining observation date, currency and unit. It is not a farm-gate offer.",
    ),
    "wfp_prices": (
        "hapi.ethiopia_prices",
        "wfp_market_prices",
        "Explain dated WFP/HDX Ethiopian food prices. Preserve reference intervals, price type, flag, market, currency and unit; mismatched series are not comparable.",
    ),
    "eppo": (
        "eppo.names",
        "pest_taxonomy",
        "Look up a supplied EPPO code and explain scientific/common names. A names lookup establishes neither local occurrence nor treatment suitability. If the code is missing, ask for it; do not fabricate a code.",
    ),
    "fao_locust": (
        "fao.locust_observations",
        "locust_observations",
        "Explain dated regional reported locust observations. The regional box includes neighboring territory unless country is confirmed. No reports means unknown, not low risk.",
    ),
    "fao_wapor": (
        "wapor.evapotranspiration",
        "water_use",
        "Explain numerical evapotranspiration for the requested historical dates, with units, scale and composite period. Catalogue metadata alone is not a measurement or irrigation prescription.",
    ),
    "fao_gaez": (
        "gaez.maize_suitability",
        "maize_suitability",
        "Explain only GAEZ v4 high-input rain-fed maize suitability on the 1981-2010 baseline. This regional 0-10000 index is not probability, current yield or a complete planting recommendation. Other crops/scenarios are unavailable.",
    ),
    "fao_asis": (
        "asis.vegetation_condition",
        "vegetation_condition",
        "Explain historical normalized VCI in the 0-1 range with its full composite dates. Regional vegetation condition does not establish pest presence or independently confirm drought.",
    ),
    "google_earth_engine": (
        "gee.modis_ndvi",
        "vegetation_greenness",
        "Explain quality-filtered historical MODIS NDVI with valid-pixel counts, 16-day composite start dates and the 500 m plot-centred buffer. No valid pixels means unknown. Do not diagnose disease from NDVI.",
    ),
    "kindwise": (
        "kindwise.diagnosis",
        "crop_photo_assessment",
        "Require the attached private crop image and explicit credit authorization. Explain crop/disease candidates as uncertain photo assessments, never confirmed diagnoses or pesticide prescriptions. Do not repeat an uncertain or previously submitted image.",
    ),
    "openrouteservice": (
        "ors.driving_route",
        "driving_route",
        "Use from_plot_id and to_plot_id from the authorized plot references. Explain driving distance and estimated duration. No live traffic, road-passability guarantee, isochrones, costs or buyer offers are available.",
    ),
}


def provider_skill(provider_id):
    handler, name, instructions = PROVIDERS[provider_id]
    capability = template(handler)["operations"][0]["capability_tags"][0]
    return {
        "name": "fieldops_" + name,
        "description": name.replace("_", " "),
        "instructions": instructions,
        "required_capabilities": [capability],
        "optional_capabilities": [],
        "triggers": ["crop_image_submitted"] if provider_id == "kindwise" else ["explicit_chat_request"],
    }


def combined_skill():
    return {
        "name": "fieldops_agricultural_context",
        "description": "Explain combined plot weather and mapped soil evidence",
        "instructions": "Gather forecast and soil evidence before explaining the selected plot. Add rainfall history only when a past date range was supplied. Cite actual evidence IDs and missing capabilities. Do not invent crop calendars, agronomic thresholds, fertilizer doses or suitability rankings. This is an officer evidence explanation, not a released advisory.",
        "required_capabilities": ["weather.forecast", "soil.profile"],
        "optional_capabilities": ["rainfall.history"],
    }


def verified_pack():
    return {
        "name": "verified_agri_apis",
        "version": 2,
        "description": "Fourteen reviewed provider adapters. Installation creates disabled drafts; backend live checks and exact-version activation remain required.",
        "connections": [
            {"template_id": p, "configuration": template(v[0])["connection"], "tools": template(v[0])["operations"]}
            for p, v in PROVIDERS.items()
        ],
        "skills": [provider_skill(p) for p in PROVIDERS] + [combined_skill()],
    }
