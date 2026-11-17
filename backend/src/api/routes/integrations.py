"""The future integration wizard's backend API. No route accepts executable code."""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import select, update
from src.auth.dependencies import get_current_user
from src.db.session import get_db
from src.db.models.connectors import Integration, RegisteredTool, ConnectorJob, ExecutionBudget, ConnectionCredential
from src.db.models.workspace import WorkspaceRecord, WorkspaceEvent
from src.integrations.contracts import (
    Strict,
    ConnectionSpec,
    ToolSpec,
    TestRequest,
    ExactVersion,
    Enabled,
    CredentialWrite,
    ConnectorError,
    now,
)
from src.integrations.service import IntegrationService, credential_scope, audit
from src.integrations.jobs import job_view
from src.tools.policy import principal_for, require_admin

router = APIRouter(prefix="/api/v1", tags=["Connectors"])


def service(db=Depends(get_db), user=Depends(get_current_user)):
    return IntegrationService(db, principal_for(db, user.user_id))


class ConnectionRevision(Strict):
    expected_revision: int = Field(ge=1)
    configuration: ConnectionSpec


class ToolRevision(Strict):
    expected_revision: int = Field(ge=1)
    connection_revision: int = Field(ge=1)
    specification: ToolSpec


class DiscoveryInput(Strict):
    connection_revision: int = Field(ge=1)
    authorize_network: bool = False
    request_key: str = Field(min_length=8, max_length=100)


class ConnectionTest(TestRequest):
    tool_id: str


class ProviderTest(ConnectionTest):
    connection_id: str


@router.get("/providers")
def providers(s=Depends(service)):
    from src.providers.inventory import inventory

    document = inventory()
    return {
        "items": document["providers"],
        "note": document.get("note"),
        "office_enablement": "Historical verification is separate from this office's approved enabled connections.",
    }


@router.get("/providers/{provider_id}/template")
def provider_template(provider_id: str, s=Depends(service)):
    from src.providers.inventory import inventory
    from src.providers.factory import template

    provider = next((row for row in inventory()["providers"] if row["id"] == provider_id), None)
    if not provider or not provider["handler_id"]:
        raise ConnectorError(
            "UNSUPPORTED_CAPABILITY", provider.get("blocker") if provider else "Provider not found in inventory"
        )
    return template(provider["handler_id"])


@router.post("/providers/{provider_id}/verify", status_code=202)
def verify_provider(provider_id: str, payload: ProviderTest, s=Depends(service)):
    from src.providers.inventory import inventory

    provider = next((row for row in inventory()["providers"] if row["id"] == provider_id), None)
    connection = s.owned(Integration, payload.connection_id)
    if (
        not provider
        or s.config(connection, payload.connection_revision).configuration.get("handler_id") != provider["handler_id"]
    ):
        raise ConnectorError("POLICY_DENIED", "Provider verification must target its own office-owned reviewed adapter")
    return job_view(
        s.queue_tool_test(
            connection.id,
            payload.tool_id,
            TestRequest.model_validate(payload.model_dump(exclude={"tool_id", "connection_id"})),
        )
    )


@router.get("/integrations/support")
def support(s=Depends(service)):
    return {
        "version": "0.4",
        "rest": {
            "methods": ["GET", "POST_READ_ONLY"],
            "formats": ["json"],
            "auth": ["none", "api_key_header", "bearer"],
            "fixed_paths": True,
            "pagination": False,
            "schema_dialect": "2020-12-inline-subset",
            "schema_max_bytes": 65536,
            "schema_max_depth": 12,
            "schema_references": False,
            "mapping": ["literal", "argument_json_pointer", "response_json_pointer"],
        },
        "mcp": {
            "sdk": "mcp",
            "sdk_version": "1.29.0",
            "transport": ["streamable-http"],
            "auth": ["none", "api_key_header", "bearer"],
            "catalog_max_pages": 5,
            "catalog_max_tools": 200,
            "interactive_oauth": False,
            "tenant_stdio": False,
            "protocol_2026_only": False,
        },
        "effects": ["READ_ONLY", "OPERATOR_INTERNAL_DRAFT_WRITE"],
        "openapi_import": False,
        "arbitrary_code": False,
        "new_tools_require_restart": False,
        "network_policy": "operator_exact_hosts_plus_pinned_public_ip_connect_proxy",
        "health_checks_invoke_providers": False,
    }


@router.get("/me")
def me(s=Depends(service)):
    return {"user_id": s.principal.user_id, "office_id": s.principal.office_id, "role": s.principal.role}


@router.get("/integrations")
def list_integrations(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=Depends(service)):
    rows = s.db.scalars(
        select(Integration)
        .where(Integration.office_id == s.principal.office_id)
        .order_by(Integration.created_at)
        .offset(offset)
        .limit(limit)
    )
    return {"items": [s.view(row) for row in rows], "limit": limit, "offset": offset}


@router.post("/integrations", status_code=201)
def create(payload: ConnectionSpec, s=Depends(service)):
    return s.view(s.create(payload.model_dump(mode="json")))


@router.get("/integrations/{connection_id}")
def detail(connection_id: str, s=Depends(service)):
    return s.view(s.owned(Integration, connection_id))


@router.post("/integrations/{connection_id}/versions", status_code=201)
def revise(connection_id: str, payload: ConnectionRevision, s=Depends(service)):
    return s.view(s.revise(connection_id, payload.configuration.model_dump(mode="json"), payload.expected_revision))


@router.put("/integrations/{connection_id}/credential")
def credential(connection_id: str, payload: CredentialWrite, request: Request, s=Depends(service)):
    from src.config.settings import get_settings

    if get_settings().app_env == "production" and request.url.scheme != "https":
        raise ConnectorError("POLICY_DENIED", "Credential writes require HTTPS in production")
    return s.credential(connection_id, payload)


@router.post("/integrations/{connection_id}/tools", status_code=201)
def register_tool(connection_id: str, payload: ToolSpec, s=Depends(service)):
    tool, version = s.register_tool(connection_id, payload.model_dump(mode="json"))
    return s.tool_view(tool, version)


@router.post("/integrations/{connection_id}/tools/{tool_id}/versions", status_code=201)
def revise_tool(connection_id: str, tool_id: str, payload: ToolRevision, s=Depends(service)):
    old, _ = s.tool_version(connection_id, tool_id)
    if payload.specification.name != old.name:
        raise ConnectorError("VERSION_CONFLICT", "Stable tool name is immutable")
    tool, version = s.register_tool(
        connection_id,
        payload.specification.model_dump(mode="json"),
        connection_revision=payload.connection_revision,
        expected_revision=payload.expected_revision,
    )
    return s.tool_view(tool, version)


@router.get("/integrations/{connection_id}/tools")
def list_tools(
    connection_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=Depends(service)
):
    s.owned(Integration, connection_id)
    rows = list(
        s.db.scalars(
            select(RegisteredTool)
            .where(RegisteredTool.connection_id == connection_id, RegisteredTool.office_id == s.principal.office_id)
            .order_by(RegisteredTool.name)
            .offset(offset)
            .limit(limit)
        )
    )
    return {
        "items": [s.tool_view(tool, s.tool_version(connection_id, tool.id)[1]) for tool in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/integrations/{connection_id}/tools/{tool_id}/preview")
def preview(connection_id: str, tool_id: str, payload: TestRequest, s=Depends(service)):
    return s.preview(connection_id, tool_id, payload)


@router.post("/integrations/{connection_id}/tools/{tool_id}/test", status_code=202)
def test_tool(connection_id: str, tool_id: str, payload: TestRequest, s=Depends(service)):
    return job_view(s.queue_tool_test(connection_id, tool_id, payload))


@router.post("/integrations/{connection_id}/test", status_code=202)
def test_connection(connection_id: str, payload: ConnectionTest, s=Depends(service)):
    args = TestRequest.model_validate(payload.model_dump(exclude={"tool_id"}))
    return job_view(s.queue_tool_test(connection_id, payload.tool_id, args))


@router.post("/integrations/{connection_id}/tools/{tool_id}/approve")
def approve_tool(connection_id: str, tool_id: str, payload: ExactVersion, s=Depends(service)):
    return s.approve_tool(connection_id, tool_id, payload)


@router.patch("/integrations/{connection_id}/tools/{tool_id}/enabled")
def enable_tool(connection_id: str, tool_id: str, payload: Enabled, s=Depends(service)):
    return s.set_tool_enabled(connection_id, tool_id, payload)


@router.patch("/integrations/{connection_id}/enabled")
def enable_connection(connection_id: str, payload: Enabled, s=Depends(service)):
    return s.set_enabled(connection_id, payload)


@router.post("/integrations/{connection_id}/discover", status_code=202)
def discover(connection_id: str, payload: DiscoveryInput, s=Depends(service)):
    require_admin(s.principal)
    connection = s.owned(Integration, connection_id)
    config = s.config(connection, payload.connection_revision)
    from src.config.settings import get_settings
    from src.integrations.safe_http import destination

    _, fixture = destination(config.configuration["base_url"])
    if not fixture and not get_settings().live_tests_enabled:
        raise ConnectorError("POLICY_DENIED", "Set LIVE_TESTS_ENABLED=true before a real-server discovery test")
    if connection.adapter_type != "mcp":
        raise ConnectorError(
            "UNSUPPORTED_CAPABILITY", "Only MCP tool catalogs support discovery; register REST operations explicitly"
        )
    if not payload.authorize_network:
        raise ConnectorError("POLICY_DENIED", "Discovery requires explicit network authorization")
    credential = s.db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
    return job_view(
        s.create_job(
            "discovery",
            connection.id,
            payload.model_dump(mode="json"),
            snapshot={
                "connection_id": connection.id,
                "connection_revision": config.revision,
                "credential_scope": credential_scope(s.db, connection),
                "credential_revision": credential.revision if credential else None,
            },
        )
    )


@router.get("/integrations/{connection_id}/tests")
def tests(connection_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=Depends(service)):
    s.owned(Integration, connection_id)
    rows = s.db.scalars(
        select(ConnectorJob)
        .where(
            ConnectorJob.office_id == s.principal.office_id,
            ConnectorJob.kind.in_(["tool_test", "discovery"]),
            ConnectorJob.snapshot["connection_id"].as_string() == connection_id,
        )
        .order_by(ConnectorJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return {"items": [job_view(row) for row in rows], "limit": limit, "offset": offset}


@router.get("/connector-jobs/{job_id}")
@router.get("/runs/{job_id}")
def job(job_id: str, s=Depends(service)):
    return job_view(s.owned(ConnectorJob, job_id))


@router.get("/runs/{job_id}/results")
def results(job_id: str, s=Depends(service)):
    row = s.owned(ConnectorJob, job_id)
    return {"id": row.id, "status": row.status, "result": row.result, "error": row.error}


@router.post("/runs/{job_id}/cancel")
def cancel(job_id: str, s=Depends(service)):
    row = s.owned(ConnectorJob, job_id, lock=True)
    if s.principal.role == "viewer":
        raise ConnectorError("POLICY_DENIED", "Viewers cannot cancel jobs")
    if s.principal.role != "office_admin" and row.principal_id != s.principal.user_id:
        raise ConnectorError("POLICY_DENIED", "Only the initiating officer or office administrator can cancel this job")
    if row.status in ("queued", "running"):
        s.db.execute(update(ExecutionBudget).where(ExecutionBudget.id == row.budget_id).values(cancelled=True))
        row.status = "cancelled"
        row.error = ConnectorError(
            "CANCELLED", "Cancellation requested; already dispatched work may still finish"
        ).as_dict()
        row.updated_at = now()
        audit(s.db, s.principal, row.id, "connector_job_cancelled")
        s.db.commit()
    return job_view(row)


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: str, s=Depends(service)):
    row = s.owned(WorkspaceRecord, evidence_id)
    if row.kind != "evidence":
        raise ConnectorError("NOT_FOUND", "Evidence not found")
    return {"id": row.id, "data": row.data}


@router.get("/audit")
def audit_events(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=Depends(service)):
    require_admin(s.principal)
    rows = s.db.scalars(
        select(WorkspaceEvent)
        .where(WorkspaceEvent.office_id == s.principal.office_id)
        .order_by(WorkspaceEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "entity_id": row.entity_id,
                "actor_id": row.actor_id,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }
