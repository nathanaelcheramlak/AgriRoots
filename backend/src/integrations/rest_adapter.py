"""A generic, bounded JSON connector driven solely by reviewed configuration."""

from jsonpointer import resolve_pointer, JsonPointerException
from src.integrations.contracts import ConnectorError, ConnectorResult, digest
from src.integrations.safe_http import fixed_url
from src.integrations.mappings import mapped
from src.integrations.schema_translation import validate


class RestConnector:
    def __init__(self, http, configuration, headers):
        self.http, self.configuration, self.headers = http, configuration, headers

    async def invoke(self, version, arguments, context):
        spec = version.specification
        request, response = spec["request"], spec["response"]
        query = mapped(request["query"], arguments=arguments)
        if any(not isinstance(v, (str, int, float, bool, list, type(None))) for v in query.values()):
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Query mapping must produce scalar values or scalar arrays")
        body = mapped(request["body"], arguments=arguments) if request["body"] is not None else None
        url = fixed_url(self.configuration["base_url"], request["path"])
        raw = await self.http.json(
            request["method"],
            url,
            headers=self.headers,
            params=query,
            body=body,
            attempts=spec["policy"]["max_attempts"] if request["method"] == "GET" else 1,
        )
        if raw is None:
            return ConnectorResult(
                data_outcome="NO_DATA", source={"url": url}, limitations=["Provider returned HTTP 204"]
            )
        if response.get("provider_output_json_schema"):
            validate(raw, response["provider_output_json_schema"], output=True)
        if response.get("no_data_pointer") is not None:
            try:
                empty = resolve_pointer(raw, response["no_data_pointer"]) == response.get("no_data_value")
            except JsonPointerException:
                raise ConnectorError("OUTPUT_VALIDATION_FAILED", "Declared no-data indicator is missing") from None
            if empty:
                return ConnectorResult(data_outcome="NO_DATA", source={"url": url})
        limitations = []
        data = (
            mapped(response["field_mapping"], response=raw, limitations=limitations)
            if response["field_mapping"]
            else raw
        )
        validate(data, response["normalized_output_json_schema"], output=True)
        return ConnectorResult(
            data=data,
            source={"url": url, "semantics": spec["evidence_semantics"], "raw_response_digest": digest(raw)},
            limitations=limitations,
        )
