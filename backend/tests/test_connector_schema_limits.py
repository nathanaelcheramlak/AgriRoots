"""Reject unsupported expensive/ignored constraints rather than silently loosening them."""

import pytest
from src.integrations.contracts import ConnectorError
from src.integrations.schema_translation import checked_schema


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string", "pattern": "(a+)+$"},
        {"type": "array", "uniqueItems": True},
        {"type": "string", "format": "custom-unchecked-format"},
        {"type": "object", "additionalProperties": {"$ref": "https://fixture.invalid/schema"}},
    ],
)
def test_unsafe_or_unchecked_schema_constraints_are_rejected(schema):
    with pytest.raises(ConnectorError) as error:
        checked_schema(schema)
    assert error.value.code == "UNSUPPORTED_SCHEMA"
