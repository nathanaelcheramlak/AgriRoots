"""Only operator-reviewed handler identifiers resolve to Python functions."""

from src.integrations.contracts import ConnectorError, ToolSpec
from src.providers import agriculture
from src.providers import references, environment, earth_engine

HANDLERS = {
    "open_meteo.forecast": {
        "base_url": "https://api.open-meteo.com",
        "call": agriculture.open_meteo,
        "capability": "weather.forecast",
        "auth": "none",
        "coordinates": True,
    },
    "nasa_power.history": {
        "base_url": "https://power.larc.nasa.gov",
        "call": agriculture.nasa_power,
        "capability": "climate.history",
        "auth": "none",
        "coordinates": True,
        "dates": True,
    },
    "isda.soil_profile": {
        "base_url": "https://api.isda-africa.com",
        "call": agriculture.isda,
        "capability": "soil.profile",
        "auth": "provider",
        "coordinates": True,
    },
    "chirps.rainfall_history": {
        "base_url": "https://climateserv.servirglobal.net",
        "call": agriculture.chirps,
        "capability": "rainfall.history",
        "auth": "none",
        "coordinates": True,
        "dates": True,
    },
    "fpma.ethiopia_prices": {
        "base_url": "https://fpma.fao.org",
        "call": agriculture.fpma,
        "capability": "market.prices",
        "auth": "none",
        "coordinates": False,
    },
    "fao.locust_observations": {
        "base_url": "https://www.arcgis.com",
        "call": agriculture.locust,
        "capability": "pests.regional_reports",
        "auth": "none",
        "coordinates": False,
    },
}

HANDLERS.update({
    "eppo.names": {"base_url": "https://api.eppo.int", "call": references.eppo,
                   "capability": "pests.taxonomy", "auth": "provider", "coordinates": False,
                   "properties": {"eppo_code": {"type": "string", "minLength": 5, "maxLength": 6}}, "required": ["eppo_code"]},
    "hapi.ethiopia_prices": {"base_url": "https://hapi.humdata.org", "call": references.hapi,
                   "capability": "market.wfp_prices", "auth": "provider", "coordinates": False, "dates": True},
    "ors.driving_route": {"base_url": "https://api.heigit.org", "call": references.route,
                   "capability": "logistics.route", "auth": "provider", "coordinates": False, "geo": True,
                   "properties": {k: {"type": "string", "minLength": 36, "maxLength": 36} for k in ("from_plot_id", "to_plot_id")},
                   "required": ["from_plot_id", "to_plot_id"]},
    "kindwise.diagnosis": {"base_url": "https://crop.kindwise.com", "call": references.kindwise,
                   "capability": "crop.diagnosis", "auth": "provider", "coordinates": False, "image": True,
                   "properties": {"image_asset_id": {"type": "string", "minLength": 36, "maxLength": 36}},
                   "required": ["image_asset_id"]},
    "gaez.maize_suitability": {"base_url": "https://storage.googleapis.com", "call": environment.gaez,
                   "capability": "crop.maize_suitability", "auth": "none", "coordinates": True, "binary": True},
    "wapor.evapotranspiration": {"base_url": "https://data.apps.fao.org", "call": environment.wapor,
                   "capability": "water.evapotranspiration", "auth": "none", "coordinates": True, "dates": True, "binary": True},
    "asis.vegetation_condition": {"base_url": "https://asis-esri.fao.org", "call": environment.asis,
                   "capability": "vegetation.condition", "auth": "none", "coordinates": True, "dates": True},
    "gee.modis_ndvi": {"base_url": "https://earthengine.googleapis.com", "call": earth_engine.earth_engine,
                   "capability": "vegetation.ndvi", "auth": "provider", "coordinates": True, "dates": True, "binary": True},
})
HANDLERS["fpma.ethiopia_prices"]["properties"] = {k: {"type": "string", "minLength": 1, "maxLength": 100} for k in ("market_name", "commodity_name")}
HANDLERS["chirps.rainfall_history"]["properties"] = {
    "resume_invocation_id": {"type": "string", "minLength": 36, "maxLength": 36}}


def handler_definition(handler_id):
    if handler_id not in HANDLERS:
        raise ConnectorError(
            "UNSUPPORTED_CAPABILITY", "Handler is not in the operator-reviewed implementation inventory"
        )
    return HANDLERS[handler_id]


def template(handler_id):
    handler = handler_definition(handler_id)
    properties, required, bindings = {}, [], {}
    properties.update(handler.get("properties", {}))
    required.extend(handler.get("required", []))
    if handler["coordinates"]:
        properties.update(
            latitude={"type": "number", "minimum": -90, "maximum": 90},
            longitude={"type": "number", "minimum": -180, "maximum": 180},
        )
        bindings.update(latitude="plot.latitude", longitude="plot.longitude")
        required.extend(["latitude", "longitude"])
    if handler.get("dates"):
        properties.update(
            start={"type": "string", "format": "date", "maxLength": 10},
            end={"type": "string", "format": "date", "maxLength": 10},
        )
        required.extend(["start", "end"])
    data_classes = ["plot_coordinates"] if handler["coordinates"] or handler.get("geo") else ["public_environment"]
    if handler.get("image"):
        data_classes = ["image"]
        bindings["image_asset_id"] = "run.image_asset_id"
    operation = ToolSpec(
        name=handler_id.replace(".", "_"),
        description="Reviewed agricultural operation: " + handler_id + ("; controlled runtime revision 2" if handler_id in ("gee.modis_ndvi", "gaez.maize_suitability", "wapor.evapotranspiration") else ""),
        capability_tags=[handler["capability"]],
        input_json_schema={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        context_bindings=bindings,
        required_data_classes=data_classes,
        response={"normalized_output_json_schema": {"type": "object"}},
        evidence_semantics={"value_kind": handler["capability"]},
        policy={"max_attempts": 1, "max_response_bytes": 4194304 if handler.get("binary") else 1048576,
                "cache_ttl_seconds": 0},
    )
    return {
        "connection": {
            "name": handler_id,
            "adapter_type": "builtin",
            "handler_id": handler_id,
            "base_url": handler["base_url"],
            "authentication": {"type": handler["auth"]},
            "egress_data_classes": data_classes,
        },
        "operations": [operation.model_dump(mode="json")],
    }


class BuiltInProviderConnector:
    def __init__(self, http, configuration, headers, credential):
        self.http, self.configuration, self.headers, self.credential = http, configuration, headers, credential

    async def invoke(self, version, arguments, context):
        handler = handler_definition(self.configuration["handler_id"])
        if self.configuration["authentication"]["type"] != handler["auth"]:
            raise ConnectorError(
                "UNSUPPORTED_AUTH", "Built-in authentication does not match the verified provider contract"
            )
        result = await handler["call"](
            self.http, self.configuration["base_url"].rstrip("/"), arguments, self.credential, context
        )
        if result.data_outcome == "VALID":
            from src.integrations.schema_translation import validate

            validate(result.data, version.specification["response"]["normalized_output_json_schema"], output=True)
        return result
