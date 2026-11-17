"""Connector configuration is data. No import strings, executable templates or URLs from model arguments."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now():
    return datetime.now(timezone.utc)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


class ConnectorError(Exception):
    def __init__(self, code: str, message: str, *, retryable=False):
        self.code, self.message, self.retryable = code, message, retryable
        super().__init__(message)

    def as_dict(self):
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Authentication(Strict):
    type: Literal["none", "api_key_header", "bearer", "provider"] = "none"
    header_name: str | None = None
    credential_ref: None = None

    @model_validator(mode="after")
    def supported_header(self):
        if self.type == "api_key_header":
            if not self.header_name or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", self.header_name):
                raise ValueError("A valid API key header name is required")
            if self.header_name.lower() in {"host", "cookie", "connection", "proxy-authorization", "authorization"}:
                raise ValueError("Use bearer authentication for Authorization; routing/cookie headers are forbidden")
            if self.header_name.lower().startswith(("proxy-", "x-forwarded-")) or self.header_name.lower() in {
                "content-length",
                "transfer-encoding",
                "te",
                "trailer",
                "upgrade",
                "accept-encoding",
            }:
                raise ValueError("Hop-by-hop and forwarding headers cannot carry API credentials")
        elif self.header_name:
            raise ValueError("header_name is only supported for API key authentication")
        return self


class ConnectionSpec(Strict):
    name: str = Field(min_length=1, max_length=200)
    adapter_type: Literal["rest", "mcp", "builtin"]
    base_url: str = Field(min_length=1, max_length=1000)
    authentication: Authentication = Field(default_factory=Authentication)
    handler_id: str | None = Field(default=None, max_length=80)
    priority: int = Field(default=100, ge=0, le=1000)
    egress_data_classes: list[Literal["public_environment", "plot_coordinates", "image", "private_record"]] = Field(
        default_factory=lambda: ["public_environment"], max_length=4
    )

    @model_validator(mode="after")
    def auth_and_handler(self):
        if self.authentication.type == "provider" and self.adapter_type != "builtin":
            raise ValueError("Provider authentication requires a reviewed built-in handler")
        if (self.adapter_type == "builtin") != bool(self.handler_id):
            raise ValueError("Only built-in connections declare an operator-registered handler_id")
        return self


class Limits(Strict):
    timeout_seconds: float = Field(default=15, ge=1, le=60)
    max_attempts: int = Field(default=2, ge=1, le=2)
    max_response_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    cache_ttl_seconds: int = Field(default=0, ge=0, le=86400 * 30)


class RequestMapping(Strict):
    method: Literal["GET", "POST"] = "GET"
    path: str = Field(default="/", max_length=500)
    query: dict = Field(default_factory=dict)
    body: dict | list | None = None


class ResponseMapping(Strict):
    format: Literal["json", "text"] = "json"
    field_mapping: dict = Field(default_factory=dict)
    normalized_output_json_schema: dict = Field(default_factory=lambda: {"type": "object"})
    provider_output_json_schema: dict | None = None
    no_data_pointer: str | None = None
    no_data_value: Any = None


class ToolSpec(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,62}$")
    description: str = Field(min_length=1, max_length=2000)
    capability_tags: list[str] = Field(min_length=1, max_length=20)
    effect_classification: Literal["READ_ONLY", "INTERNAL_DRAFT_WRITE"] = "READ_ONLY"
    allowed_roles: list[Literal["office_admin", "extension_officer"]] = Field(
        default_factory=lambda: ["office_admin", "extension_officer"], min_length=1, max_length=2
    )
    input_json_schema: dict
    request: RequestMapping = Field(default_factory=RequestMapping)
    response: ResponseMapping = Field(default_factory=ResponseMapping)
    evidence_semantics: dict = Field(default_factory=dict)
    policy: Limits = Field(default_factory=Limits)
    upstream_tool_name: str | None = Field(default=None, max_length=200)
    discovery_digest: str | None = None
    context_bindings: dict[str, Literal["plot.id", "plot.latitude", "plot.longitude", "run.image_asset_id"]] = Field(default_factory=dict)
    required_data_classes: list[Literal["public_environment", "plot_coordinates", "image", "private_record"]] = Field(
        default_factory=lambda: ["public_environment"], max_length=4
    )


class ExactVersion(Strict):
    version: int = Field(ge=1)
    connection_revision: int = Field(ge=1)
    digest: str = Field(min_length=64, max_length=64)


class TestRequest(ExactVersion):
    arguments: dict = Field(default_factory=dict)
    plot_ids: list[str] = Field(default_factory=list, max_length=5)
    authorize_network: bool = False
    authorize_credit_use: bool = False
    request_key: str = Field(min_length=8, max_length=100)


class Enabled(Strict):
    enabled: bool
    expected_revision: int = Field(ge=1)
    version: int | None = Field(default=None, ge=1)


class CredentialWrite(Strict):
    value: str | dict = Field(repr=False)
    principal_scope: str = Field(min_length=1, max_length=200)


class SkillManifest(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,62}$")
    description: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(min_length=1, max_length=8000)
    required_capabilities: list[str] = Field(default_factory=list, max_length=12)
    optional_capabilities: list[str] = Field(default_factory=list, max_length=12)
    allowed_internal_actions: list[Literal["advisory.save_draft"]] = Field(default_factory=list, max_length=1)
    max_followup_rounds: int = Field(default=2, ge=0, le=2)
    triggers: list[Literal["explicit_chat_request", "area_selected", "crop_image_submitted"]] = Field(
        default_factory=lambda: ["explicit_chat_request"], max_length=3
    )


class SkillRunRequest(Strict):
    image_asset_id: str | None = Field(default=None, min_length=36, max_length=36)
    parameters: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reviewed_parameters(self):
        allowed = {"start", "end", "market_name", "commodity_name", "eppo_code", "from_plot_id", "to_plot_id", "resume_invocation_id"}
        if set(self.parameters) - allowed or any(len(v) > 100 for v in self.parameters.values()):
            raise ValueError("Use only reviewed task parameters, each at most 100 characters")
        return self
    task: str = Field(min_length=3, max_length=2000)
    plot_ids: list[str] = Field(default_factory=list, max_length=5)
    request_key: str = Field(min_length=8, max_length=100)
    authorize_network: bool = False
    authorize_model: bool = False
    authorize_credit_use: bool = False


@dataclass(frozen=True)
class Principal:
    user_id: str
    office_id: str
    role: str


@dataclass
class ExecutionContext:
    principal: Principal
    budget_id: str
    invocation_id: str
    job_id: str | None = None
    run_id: str | None = None
    plot_ids: list[str] = field(default_factory=list)
    plots: list[dict] = field(default_factory=list)
    mode: str = "runtime"
    authorize_network: bool = False
    authorize_credit_use: bool = False
    image_asset_id: str | None = None
    deadline: float = 0
    lease_token: str | None = field(default=None, repr=False)


@dataclass
class ConnectorResult:
    execution_outcome: str = "SUCCESS"
    data_outcome: str = "VALID"
    data: Any = None
    source: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    model_data: Any = None


class Connector(Protocol):
    async def invoke(self, version, arguments: dict, context: ExecutionContext) -> ConnectorResult: ...


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
