"""Approved environmental/photo evidence explanations, without private farm record payloads."""

from src.integrations.contracts import ConnectorError

ENVIRONMENT_CAPABILITIES = frozenset({"weather.forecast", "soil.profile", "rainfall.history", "crop.diagnosis"})


def scope_environment_snapshot(snapshot):
    manifest = snapshot["manifest"]
    required = set(manifest["required_capabilities"])
    if not required or not required <= ENVIRONMENT_CAPABILITIES or manifest["allowed_internal_actions"]:
        raise ConnectorError(
            "POLICY_DENIED",
            "This demo supports weather forecasts, soil, historical rainfall and crop-photo assessments only",
        )
    # Keep the established Home weather/soil flow focused. Rainfall and photos
    # are separately selected skills, not implicit extra calls in that flow.
    home_capabilities = {"weather.forecast", "soil.profile"}
    allowed = home_capabilities if required <= home_capabilities else ENVIRONMENT_CAPABILITIES
    tools = [
        tool for tool in snapshot["tools"] if set(tool["capability_tags"]) and set(tool["capability_tags"]) <= allowed
    ]
    if not required <= {cap for tool in tools for cap in tool["capability_tags"]}:
        raise ConnectorError("POLICY_DENIED", "An approved weather or soil tool is unavailable")
    return {
        **snapshot,
        "tools": tools,
        "model_data_policy": "environment_only",
        "missing_optional_capabilities": sorted(
            set(snapshot["missing_optional_capabilities"]) | (set(manifest["optional_capabilities"]) - allowed)
        ),
    }


def environment_prompt(request, plots, snapshot):
    return {
        "task": request["task"],
        "data_policy": "environment_only",
        "parameters": {},
        "authorized_location_count": len(plots),
        "context": "Use server-bound approved tools. Coordinates and private farm records are not provided to the model.",
        "available_capabilities": sorted(
            {cap for tool in snapshot.get("tools", []) for cap in tool["capability_tags"]}
        ),
    }
