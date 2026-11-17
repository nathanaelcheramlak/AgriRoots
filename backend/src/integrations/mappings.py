"""A typed literal/JSON Pointer mapping language; deliberately not an expression evaluator."""

from jsonpointer import resolve_pointer, JsonPointerException
from src.integrations.contracts import ConnectorError


def check_mapping(value, sources, depth=0):
    if depth > 12:
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Mapping nesting exceeds 12 levels")
    if isinstance(value, dict):
        if "source" in value:
            source = value["source"]
            allowed = {"source", "value"} if source == "literal" else {"source", "pointer", "required"}
            if source not in sources or set(value) - allowed:
                raise ConnectorError("INPUT_VALIDATION_FAILED", "Unsupported mapping source or fields")
            if source != "literal" and (
                not isinstance(value.get("pointer"), str) or value["pointer"] and not value["pointer"].startswith("/")
            ):
                raise ConnectorError("INPUT_VALIDATION_FAILED", "Mapping requires an RFC 6901 JSON Pointer")
            if source == "literal" and "value" not in value:
                raise ConnectorError("INPUT_VALIDATION_FAILED", "Literal mapping requires a value")
        else:
            for item in value.values():
                check_mapping(item, sources, depth + 1)
    elif isinstance(value, list):
        if len(value) > 100:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Mapping array is too large")
        for item in value:
            check_mapping(item, sources, depth + 1)
    else:
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Use an explicit literal mapping for constant values")


def mapped(value, arguments=None, response=None, limitations=None):
    if isinstance(value, list):
        return [mapped(v, arguments, response, limitations) for v in value]
    if "source" not in value:
        return {key: mapped(v, arguments, response, limitations) for key, v in value.items()}
    if value["source"] == "literal":
        return value["value"]
    source = arguments if value["source"] == "argument" else response
    try:
        return resolve_pointer(source, value["pointer"])
    except (JsonPointerException, KeyError, TypeError, IndexError):
        if value.get("required", True):
            raise ConnectorError(
                "OUTPUT_VALIDATION_FAILED" if value["source"] == "response" else "INPUT_VALIDATION_FAILED",
                "Required mapping pointer is absent: " + value["pointer"],
            ) from None
        if limitations is not None:
            limitations.append("Optional source field is missing: " + value["pointer"])
        return None
