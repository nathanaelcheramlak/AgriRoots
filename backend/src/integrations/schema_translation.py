"""Bounded JSON Schema documents and lossless model declarations for the supported subset."""

import copy
import json
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from src.integrations.contracts import ConnectorError

FORBIDDEN = {
    "pattern",  # Python's regex validator has no execution deadline.
    "uniqueItems",  # Avoid quadratic comparisons on untrusted large arrays.
    "$dynamicRef",
    "$dynamicAnchor",
    "unevaluatedProperties",
    "unevaluatedItems",
    "patternProperties",
    "if",
    "then",
    "else",
    "dependentSchemas",
    "contains",
    "contentEncoding",
    "contentMediaType",
}
SCHEMA_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "description",
    "title",
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minProperties",
    "maxProperties",
    "format",
    "anyOf",
    "allOf",
    "oneOf",
    "not",
    "$schema",
    "$id",
    "$defs",
    "$ref",
    "multipleOf",
}


def checked_schema(schema: dict, *, inputs=False):
    try:
        raw = json.dumps(schema, allow_nan=False)
        if len(raw.encode()) > 65536:
            raise ValueError("schema exceeds 64 KiB")
        count = 0

        def walk(value, path="$", depth=0):
            nonlocal count
            count += 1
            if depth > 12 or count > 1000:
                raise ValueError(f"{path}: schema depth/node limit exceeded")
            if not isinstance(value, dict):
                if isinstance(value, bool):
                    return
                raise ValueError(f"{path}: schema must be an object or boolean")
            for key in value:
                if key in FORBIDDEN or key not in SCHEMA_KEYS:
                    raise ValueError(f"{path}/{key}: unsupported schema keyword")
            if "$id" in value:
                raise ValueError(f"{path}/$id: external/base identifiers are not supported")
            if "$ref" in value:
                # A bounded, explicit first-release subset. Never install a network resolver.
                raise ValueError(f"{path}/$ref: references are not supported; provide an inline bounded schema")
            if "format" in value and value["format"] not in {
                "date",
                "date-time",
                "uuid",
                "uri",
                "ipv4",
                "ipv6",
                "hostname",
                "email",
            }:
                raise ValueError(f"{path}/format: unsupported format; constraints are not silently ignored")
            for key in ("properties", "$defs"):
                entries = value.get(key, {})
                if len(entries) > 100:
                    raise ValueError(f"{path}/{key}: too many properties")
                for name, sub in entries.items():
                    walk(sub, f"{path}/{key}/{name}", depth + 1)
            if "items" in value:
                walk(value["items"], path + "/items", depth + 1)
            if isinstance(value.get("additionalProperties"), dict):
                walk(value["additionalProperties"], path + "/additionalProperties", depth + 1)
            for key in ("anyOf", "oneOf", "allOf"):
                for index, sub in enumerate(value.get(key, [])):
                    walk(sub, f"{path}/{key}/{index}", depth + 1)
            if "not" in value:
                walk(value["not"], path + "/not", depth + 1)

        walk(schema)
        Draft202012Validator.check_schema(schema)
        if inputs and (schema.get("type") != "object" or schema.get("additionalProperties") is not False):
            raise ValueError("Tool inputs require type object and additionalProperties=false")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ConnectorError("UNSUPPORTED_SCHEMA", str(exc)) from None
    except Exception:
        raise ConnectorError("UNSUPPORTED_SCHEMA", "Invalid JSON Schema document") from None
    return schema


def validate(value, schema, *, output=False):
    try:
        if len(json.dumps(value, allow_nan=False).encode()) > 1048576:
            raise ValueError("value exceeds schema processing limit")
        error = next(
            Draft202012Validator(schema, registry=Registry(), format_checker=FormatChecker()).iter_errors(value), None
        )
        if error:
            # Validator messages may contain secrets supplied as invalid values. Return paths and keyword only.
            raise ValueError("/" + "/".join(map(str, error.absolute_path)) + ": failed " + str(error.validator))
    except Exception as exc:
        raise ConnectorError(
            "OUTPUT_VALIDATION_FAILED" if output else "INPUT_VALIDATION_FAILED",
            str(exc) if isinstance(exc, ValueError) else "Schema validation failed",
        ) from None


def model_schema(spec):
    schema = copy.deepcopy(spec["input_json_schema"])
    # These fields have an explicit, reviewed server binding; they are not model inputs.
    for name in spec.get("context_bindings", {}):
        schema.get("properties", {}).pop(name, None)
        schema["required"] = [key for key in schema.get("required", []) if key != name]
    checked_schema(schema, inputs=True)
    return schema
