"""One policy boundary for runtime calls, exact-version tests and MCP transport requests."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import time
from uuid import uuid4

from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError

from src.config.settings import get_settings
from src.db.session import SessionLocal
from src.db.models.connectors import (
    Integration,
    IntegrationVersion,
    RegisteredTool,
    ToolVersion,
    ConnectionCredential,
    ExecutionBudget,
    ConnectorJob,
    ToolInvocation,
    InvocationAttempt,
    ConnectorCache,
)
from src.db.models.workspace import WorkspaceRecord
from src.integrations.contracts import ConnectorError, ExecutionContext, digest, now, utc
from src.integrations.secrets import decrypt, redact
from src.integrations.schema_translation import validate
from src.integrations.service import approval, credential_scope, audit
from src.integrations.safe_http import SafeHttp, destination
from src.tools.policy import principal_for, require_admin, authorized_plots, bind_and_check_arguments


def flatten_secrets(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for val in value.values() for item in flatten_secrets(val)]
    return []


def ensure_budget(db, context):
    budget = db.get(ExecutionBudget, context.budget_id)
    if not budget or budget.office_id != context.principal.office_id:
        raise ConnectorError("POLICY_DENIED", "Execution budget belongs to another office")
    if budget.cancelled:
        raise ConnectorError("CANCELLED", "Execution was cancelled")
    if utc(budget.deadline) <= now():
        raise ConnectorError("TIMEOUT", "Execution deadline expired")
    return budget


class DispatchGate:
    def __init__(self, context, version_id=None, connection_id=None, connection_revision=None):
        self.context, self.version_id = context, version_id
        self.connection_id, self.connection_revision = connection_id, connection_revision

    def check(self, db, *, lock=False):
        principal = principal_for(db, self.context.principal.user_id)
        if principal.office_id != self.context.principal.office_id or principal.role == "viewer":
            raise ConnectorError("POLICY_DENIED", "Actor no longer has execution permission")
        ensure_budget(db, self.context)
        if self.context.plots:
            authorized_plots(db, principal, [p["id"] for p in self.context.plots])
        if self.context.job_id:
            lease = db.get(ConnectorJob, self.context.job_id)
            if (
                not lease
                or lease.status != "running"
                or lease.lease_token != self.context.lease_token
                or not lease.lease_until
                or utc(lease.lease_until) <= now()
            ):
                raise ConnectorError("CANCELLED", "Worker lease is no longer current")
            if lease.kind == "skill_run" and self.version_id not in {
                tool["version_id"] for tool in lease.snapshot.get("tools", [])
            }:
                raise ConnectorError("POLICY_DENIED", "Tool version is outside the run's pinned skill snapshot")
        connection_query = select(Integration).where(
            Integration.id == self.connection_id, Integration.office_id == principal.office_id
        )
        connection = db.scalar(connection_query.with_for_update(nowait=True) if lock else connection_query)
        if not connection:
            raise ConnectorError("POLICY_DENIED", "Connection is outside this office")
        from src.skills.service import pack_allows

        pack_allows(db, principal.office_id, connection.id, "connections")
        config = db.scalar(
            select(IntegrationVersion).where(
                IntegrationVersion.connection_id == connection.id,
                IntegrationVersion.revision == self.connection_revision,
            )
        )
        if not config:
            raise ConnectorError("VERSION_CONFLICT", "Connection version no longer exists")
        version = db.get(ToolVersion, self.version_id) if self.version_id else None
        if version and principal.role not in version.specification.get(
            "allowed_roles", ["office_admin", "extension_officer"]
        ):
            raise ConnectorError("POLICY_DENIED", "Actor role is not permitted by this tool version")
        if version and (version.office_id != principal.office_id or version.connection_digest != config.digest):
            raise ConnectorError("VERSION_CONFLICT", "Tool is not bound to this exact connection configuration")
        if self.context.job_id:
            job = db.get(ConnectorJob, self.context.job_id)
            if job.kind == "skill_run":
                pinned = next(tool for tool in job.snapshot["tools"] if tool["version_id"] == self.version_id)
                if pinned.get("credential_scope_digest") != credential_scope(db, connection):
                    raise ConnectorError("VERSION_CONFLICT", "The run's pinned credential scope was rotated")
        if self.context.mode in ("test", "discovery"):
            require_admin(principal)
            job = db.get(ConnectorJob, self.context.job_id)
            if (
                not job
                or job.office_id != principal.office_id
                or job.principal_id != principal.user_id
                or job.status != "running"
                or not job.lease_until
                or utc(job.lease_until) <= now()
                or not job.request.get("authorize_network")
                or job.snapshot.get("connection_id") != connection.id
                or job.snapshot.get("connection_revision") != config.revision
                or self.context.mode == "test"
                and job.target_id != self.version_id
            ):
                raise ConnectorError("POLICY_DENIED", "Exact-version test authorization is missing or expired")
            cred = db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
            if job.snapshot.get("credential_scope") != credential_scope(db, connection) or job.snapshot.get(
                "credential_revision"
            ) != (cred.revision if cred else None):
                raise ConnectorError("VERSION_CONFLICT", "Credentials changed after the test was authorized")
        else:
            if not connection.enabled or connection.enabled_revision != config.revision:
                raise ConnectorError("TOOL_REVOKED", "Connection is disabled or this revision is no longer active")
            if not version:
                raise ConnectorError("APPROVAL_REQUIRED", "Runtime dispatch requires an approved tool version")
            tool = db.get(RegisteredTool, version.tool_id)
            if not tool or tool.connection_id != connection.id or not tool.enabled or tool.revoked_reason:
                raise ConnectorError("TOOL_REVOKED", "Tool is disabled or revoked")
            if not approval(
                db,
                version.id,
                principal.office_id,
                connection_digest=config.digest,
                credential_scope=credential_scope(db, connection),
            ):
                raise ConnectorError("APPROVAL_REQUIRED", "Exact tool/configuration version lacks current approval")
        if version and version.specification["effect_classification"] != "READ_ONLY":
            # Only reviewed internal handlers can ever implement draft writes.
            if connection.adapter_type != "builtin":
                raise ConnectorError("POLICY_DENIED", "User-installed modifying operations are forbidden")
        return connection, config, version

    def reserve_http(self, method, endpoint):
        with SessionLocal() as db:
            self.check(db)
            budget = ExecutionBudget
            changed = db.execute(
                update(budget)
                .where(
                    budget.id == self.context.budget_id,
                    budget.requests < budget.max_requests,
                    budget.cancelled.is_(False),
                    budget.deadline > now(),
                )
                .values(requests=budget.requests + 1)
                .execution_options(synchronize_session=False)
            ).rowcount
            if not changed:
                raise ConnectorError("BUDGET_EXCEEDED", "Shared provider-request budget is exhausted")
            ordinal = (
                db.scalar(
                    select(func.count())
                    .select_from(InvocationAttempt)
                    .where(InvocationAttempt.invocation_id == self.context.invocation_id)
                )
                + 1
            )
            row = InvocationAttempt(
                invocation_id=self.context.invocation_id, ordinal=ordinal, method=method, origin_path=endpoint
            )
            db.add(row)
            db.flush()
            ident = row.id
            db.commit()
            return ident

    def record_payload(self, value, *, kind="provider_json"):
        """Retain a response hash without persisting its unprojected private body."""
        with SessionLocal() as db:
            row = db.get(ToolInvocation, self.context.invocation_id)
            payloads = list(row.input_metadata.get("response_digests", []))
            payloads.append({"kind": kind, "sha256": value["sha256"], "bytes": value["bytes"]} if kind == "provider_binary" else {"kind": kind, "sha256": digest(value)})
            row.input_metadata = {**row.input_metadata, "response_digests": payloads}
            db.commit()

    def save_provider_state(self, namespace, state):
        with SessionLocal() as db:
            self.check(db)
            row = db.get(ToolInvocation, self.context.invocation_id)
            row.input_metadata = {**row.input_metadata, namespace: state}
            db.commit()

    def load_provider_state(self, invocation_id, namespace):
        with SessionLocal() as db:
            self.check(db)
            row = db.get(ToolInvocation, invocation_id)
            if not row or row.office_id != self.context.principal.office_id or row.tool_version_id != self.version_id:
                raise ConnectorError("POLICY_DENIED", "Provider job is outside this office or tool version")
            return row.input_metadata.get(namespace)

    @asynccontextmanager
    async def dispatch_lock(self):
        with SessionLocal() as db:
            while True:
                try:
                    self.check(db, lock=True)
                    break
                except OperationalError as error:
                    db.rollback()
                    original = getattr(error, "orig", None)
                    if getattr(original, "pgcode", None) != "55P03" and getattr(original, "sqlstate", None) != "55P03":
                        raise
                    if time.monotonic() >= self.context.deadline:
                        raise ConnectorError("TIMEOUT", "Dispatch lock deadline expired") from None
                    await asyncio.sleep(0.02)
            try:
                yield
                db.commit()
            finally:
                db.rollback()

    def finish_http(self, attempt_id, status, outcome, elapsed):
        with SessionLocal() as db:
            row = db.get(InvocationAttempt, attempt_id)
            row.status_code, row.outcome, row.elapsed_ms = status, outcome, elapsed
            db.commit()


def connection_headers(db, connection, config):
    kind = config["authentication"]["type"]
    if kind == "none":
        return {}, None, None
    record = db.scalar(
        select(ConnectionCredential).where(
            ConnectionCredential.connection_id == connection.id, ConnectionCredential.office_id == connection.office_id
        )
    )
    if not record:
        raise ConnectorError("AUTH_REQUIRED", "Attach an office-owned credential to this connection")
    value = decrypt(record, connection.office_id, connection.id)
    if kind == "provider":
        return {}, value, record.revision
    if not isinstance(value, str) or not value or any(c in value for c in "\r\n"):
        raise ConnectorError("AUTH_INVALID", "Header authentication requires a nonempty single-line credential")
    header = config["authentication"].get("header_name") if kind == "api_key_header" else "Authorization"
    return {header: value if kind == "api_key_header" else "Bearer " + value}, value, record.revision


class ToolExecutor:
    def record_failure(self, context, result, *, acquired=False):
        """A denied replay must never rewrite an earlier terminal result."""
        with SessionLocal() as db:
            row = db.get(ToolInvocation, context.invocation_id)
            if row.finished_at:
                original = row.id
                row = ToolInvocation(
                    office_id=context.principal.office_id,
                    principal_id=context.principal.user_id,
                    tool_version_id=row.tool_version_id,
                    job_id=context.job_id,
                    budget_id=context.budget_id,
                    request_key=f"denied-replay:{original}:{uuid4().hex}",
                    argument_digest=row.argument_digest,
                    input_metadata={"replay_of": original},
                )
                db.add(row)
                db.flush()
                result["invocation_id"] = row.id
            row.status = result["execution_outcome"]
            row.result = result
            row.finished_at = now()
            audit(
                db,
                context.principal,
                row.id,
                "tool_invocation_failed" if acquired else "tool_invocation_denied",
                code=result["execution_outcome"],
            )
            db.commit()

    async def execute_legacy(self, name, arguments, run_id, capability):
        """Compatibility for five fixed operator-reviewed domain operations.

        This entry point is not an HTTP registration feature. It preserves existing
        run capabilities and DTOs while sharing durable budgets, transport and audits.
        User-installed operations never enter this path.
        """
        from pathlib import Path
        from uuid import uuid4
        from src.mcp.advisory_tools import AdvisoryTools, TOOL_SCHEMAS
        from src.services.run_service import authorize_capability
        from src.api.schemas.advisory_run import ToolResult, ToolError
        from fastapi import HTTPException

        if name not in {*TOOL_SCHEMAS, "get_public_guidance"}:
            return await AdvisoryTools(run_id, capability)._call_reviewed(name, arguments)
        acquired = False
        context = None
        try:
            with SessionLocal() as db:
                try:
                    run, officer = authorize_capability(db, run_id, capability)
                except HTTPException:
                    return await AdvisoryTools(run_id, capability)._call_reviewed(name, arguments)
                actor = principal_for(db, officer.user_id)
                if db.bind.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert
                else:
                    from sqlalchemy.dialects.sqlite import insert
                db.execute(
                    insert(ExecutionBudget)
                    .values(
                        id=run.id,
                        office_id=run.office_id,
                        max_calls=get_settings().advisory_max_tool_calls,
                        max_requests=get_settings().connector_max_provider_requests,
                        max_concurrency=get_settings().connector_max_concurrency,
                        calls=0,
                        requests=0,
                        active=0,
                        deadline=run.lease_until,
                        cancelled=False,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )
                budget = db.get(ExecutionBudget, run.id)
                # An authorized run retry receives a new bounded lease, not a new spending budget.
                budget.deadline = run.lease_until
                invocation = ToolInvocation(
                    office_id=actor.office_id,
                    principal_id=actor.user_id,
                    run_id=run.id,
                    budget_id=run.id,
                    request_key=f"{run.id}:legacy:{uuid4().hex}",
                    argument_digest=digest(arguments),
                    input_metadata={
                        "operator_handler": name,
                        "handler_version": digest(
                            {
                                "executor": Path(__file__).read_text(encoding="utf-8"),
                                "domain": Path(__file__)
                                .parents[1]
                                .joinpath("mcp/advisory_tools.py")
                                .read_text(encoding="utf-8"),
                            }
                        ),
                        "argument_names": sorted(arguments),
                    },
                )
                db.add(invocation)
                db.flush()
                context = ExecutionContext(
                    actor,
                    budget.id,
                    invocation.id,
                    run_id=run.id,
                    mode="internal",
                    authorize_network=True,
                    deadline=time.monotonic() + max(0, (utc(run.lease_until) - now()).total_seconds()),
                )
                changed = db.execute(
                    update(ExecutionBudget)
                    .where(
                        ExecutionBudget.id == budget.id,
                        ExecutionBudget.calls < ExecutionBudget.max_calls,
                        ExecutionBudget.active < ExecutionBudget.max_concurrency,
                        ExecutionBudget.cancelled.is_(False),
                    )
                    .values(calls=ExecutionBudget.calls + 1, active=ExecutionBudget.active + 1)
                    .execution_options(synchronize_session=False)
                ).rowcount
                if not changed:
                    raise ConnectorError("BUDGET_EXCEEDED", "Shared internal-operation budget is exhausted")
                acquired = True
                audit(db, actor, invocation.id, "internal_tool_started", handler=name)
                db.commit()
            gate = LegacyDispatchGate(context, run_id, capability)
            if name == "get_public_guidance":
                from src.agent.advisory.graph import _public_guidance_reviewed

                output = await _public_guidance_reviewed(run_id, capability)
                successful = True
            else:
                output = await AdvisoryTools(run_id, capability, http=SafeHttp(gate))._call_reviewed(name, arguments)
                successful = output.get("ok", False)
            with SessionLocal() as db:
                log = db.get(ToolInvocation, context.invocation_id)
                log.status = "SUCCESS" if successful else "POLICY_DENIED"
                log.result = redact(output)
                log.finished_at = now()
                audit(db, actor, log.id, "internal_tool_completed", handler=name, success=successful)
                db.commit()
            return output
        except ConnectorError as error:
            if context:
                with SessionLocal() as db:
                    log = db.get(ToolInvocation, context.invocation_id)
                    if log:
                        log.status = error.code
                        log.finished_at = now()
                        log.result = {"error": error.as_dict()}
                        db.commit()
            if name == "get_public_guidance":
                raise ValueError(error.message) from None
            return ToolResult(
                ok=False, error=ToolError(code=error.code, message=error.message, retryable=error.retryable)
            ).model_dump(mode="json")
        finally:
            if acquired and context:
                with SessionLocal() as db:
                    db.execute(
                        update(ExecutionBudget)
                        .where(ExecutionBudget.id == context.budget_id, ExecutionBudget.active > 0)
                        .values(active=ExecutionBudget.active - 1)
                    )
                    db.commit()

    async def execute(
        self,
        version_id,
        arguments,
        principal,
        *,
        budget_id,
        request_key,
        job_id=None,
        mode="runtime",
        plot_ids=(),
        authorize_network=False,
        authorize_credit_use=False,
        lease_token=None,
    ):
        context = None
        acquired = False
        secret_values = []
        try:
            if not isinstance(arguments, dict) or len(json.dumps(arguments, allow_nan=False).encode()) > 65536:
                raise ConnectorError("INPUT_VALIDATION_FAILED", "Arguments must be a JSON object smaller than 64 KiB")
            with SessionLocal() as db:
                current = principal_for(db, principal.user_id)
                if current.office_id != principal.office_id:
                    raise ConnectorError("POLICY_DENIED", "Office membership changed")
                prior = db.scalar(
                    select(ToolInvocation).where(
                        ToolInvocation.office_id == current.office_id, ToolInvocation.request_key == request_key
                    )
                )
                if prior and (
                    prior.argument_digest != digest(arguments)
                    or prior.tool_version_id != version_id
                    or prior.principal_id != current.user_id
                ):
                    raise ConnectorError("VERSION_CONFLICT", "Invocation key identifies different arguments or actor")
                version = db.get(ToolVersion, version_id)
                own_version = version if version and version.office_id == current.office_id else None
                if not prior:
                    prior = ToolInvocation(
                        office_id=current.office_id,
                        principal_id=current.user_id,
                        tool_version_id=own_version.id if own_version else None,
                        job_id=job_id,
                        budget_id=budget_id,
                        request_key=request_key,
                        argument_digest=digest(arguments),
                        input_metadata={
                            "argument_names": sorted(arguments),
                            "mode": mode,
                            "plot_ids": sorted(plot_ids),
                        },
                    )
                    db.add(prior)
                    try:
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        return {
                            "execution_outcome": "AMBIGUOUS_OUTCOME",
                            "data_outcome": "INVALID",
                            "error": {
                                "code": "VERSION_CONFLICT",
                                "message": "Concurrent invocation; inspect its saved result",
                                "retryable": False,
                            },
                        }
                context = ExecutionContext(
                    current,
                    budget_id,
                    prior.id,
                    job_id=job_id,
                    plot_ids=list(plot_ids),
                    mode=mode,
                    authorize_network=authorize_network,
                    authorize_credit_use=authorize_credit_use,
                    lease_token=lease_token,
                )
                budget = ensure_budget(db, context)
                context.deadline = time.monotonic() + max(0, (utc(budget.deadline) - now()).total_seconds())
                if not own_version:
                    raise ConnectorError("POLICY_DENIED", "Tool version is not available in this office")
                tool = db.get(RegisteredTool, version.tool_id)
                gate = DispatchGate(context, version.id, tool.connection_id, version.connection_revision)
                connection, config, version = gate.check(db)
                context.plots = authorized_plots(db, current, list(plot_ids))
                if job_id:
                    context.image_asset_id = db.get(ConnectorJob, job_id).request.get("image_asset_id")
                # Operator tests provide the opaque asset ID explicitly; runtime uses the pinned run asset.
                image_argument = arguments.get("image_asset_id") if mode == "test" else context.image_asset_id
                effective_arguments = dict(arguments)
                if mode == "test" and "image_asset_id" in version.specification.get("context_bindings", {}):
                    effective_arguments.pop("image_asset_id", None)
                bound = bind_and_check_arguments(version.specification, effective_arguments, context.plots,
                                                  image_asset_id=image_argument)
                validate(bound, version.specification["input_json_schema"])
                if prior.finished_at:
                    if prior.input_metadata.get(
                        "credential_scope", credential_scope(db, connection)
                    ) != credential_scope(db, connection) or prior.input_metadata.get("plot_ids") != sorted(plot_ids):
                        raise ConnectorError(
                            "VERSION_CONFLICT", "Invocation replay scope no longer matches the original request"
                        )
                    return {**prior.result, "idempotency_replay": True}
                if prior.status == "executing":
                    return {
                        "execution_outcome": "AMBIGUOUS_OUTCOME",
                        "data_outcome": "INVALID",
                        "evidence_ids": [],
                        "error": {
                            "code": "AMBIGUOUS_OUTCOME",
                            "message": "Invocation is in progress or its remote outcome is uncertain",
                            "retryable": False,
                        },
                    }
                required = set(version.specification["required_data_classes"])
                if not required <= set(config.configuration["egress_data_classes"]):
                    raise ConnectorError("POLICY_DENIED", "Connection does not permit this data transfer")
                if "image" in required:
                    if config.configuration.get("handler_id") != "kindwise.diagnosis" or not authorize_credit_use:
                        raise ConnectorError("POLICY_DENIED", "Image transfer requires the reviewed diagnosis handler and credit authorization")
                    from src.services.image_asset_service import owned_image
                    owned_image(db, current, bound.get("image_asset_id"))
                if "private_record" in required:
                    raise ConnectorError(
                        "POLICY_DENIED", "This release requires a separately reviewed private-data/image asset workflow"
                    )
                if not authorize_network:
                    raise ConnectorError("POLICY_DENIED", "This run did not authorize outbound provider requests")
                headers, credential, credential_revision = connection_headers(db, connection, config.configuration)
                secret_values = flatten_secrets(credential)
                cache_key = digest(
                    {
                        "office": current.office_id,
                        "tool_version": version.id,
                        "digest": version.digest,
                        "connection": config.digest,
                        "credential_scope": credential_scope(db, connection),
                        "credential_revision": credential_revision,
                        "arguments": bound,
                        "plot_ids": sorted(plot_ids),
                    }
                )
                prior.input_metadata = {
                    **prior.input_metadata,
                    "credential_scope": credential_scope(db, connection),
                    "plot_ids": sorted(plot_ids),
                    "execution_fingerprint": cache_key,
                }
                if mode == "runtime":
                    completed = db.scalar(
                        select(ToolInvocation)
                        .where(
                            ToolInvocation.budget_id == budget_id,
                            ToolInvocation.principal_id == current.user_id,
                            ToolInvocation.office_id == current.office_id,
                            ToolInvocation.id != prior.id,
                            ToolInvocation.status == "SUCCESS",
                            ToolInvocation.input_metadata["execution_fingerprint"].as_string() == cache_key,
                            ToolInvocation.finished_at.is_not(None),
                        )
                        .order_by(ToolInvocation.finished_at)
                        .limit(1)
                    )
                    if completed:
                        result = {
                            **completed.result,
                            "invocation_id": prior.id,
                            "same_run_reuse": True,
                            "reused_invocation_id": completed.id,
                        }
                        prior.status = "SUCCESS"
                        prior.result = result
                        prior.finished_at = now()
                        audit(db, current, prior.id, "tool_same_run_reuse", original_invocation_id=completed.id)
                        db.commit()
                        return result
                cache = db.get(ConnectorCache, cache_key)
                from src.tools import cache as shared_cache

                saved = shared_cache.get(cache_key) if mode == "runtime" else None
                if mode == "runtime" and (saved or cache and utc(cache.expires_at) > now()):
                    result = {**(saved or cache.result), "cache_hit": True, "invocation_id": prior.id}
                    prior.status = "SUCCESS"
                    prior.result = result
                    prior.finished_at = now()
                    audit(db, current, prior.id, "tool_cache_hit", tool_version_id=version.id)
                    db.commit()
                    return result
                claimed = db.execute(
                    update(ToolInvocation)
                    .where(ToolInvocation.id == prior.id, ToolInvocation.status == "started")
                    .values(status="executing")
                ).rowcount
                if not claimed:
                    db.rollback()
                    return {
                        "execution_outcome": "AMBIGUOUS_OUTCOME",
                        "data_outcome": "INVALID",
                        "evidence_ids": [],
                        "error": {
                            "code": "AMBIGUOUS_OUTCOME",
                            "message": "Invocation was claimed by another worker",
                            "retryable": False,
                        },
                    }
                changed = db.execute(
                    update(ExecutionBudget)
                    .where(
                        ExecutionBudget.id == budget_id,
                        ExecutionBudget.calls < ExecutionBudget.max_calls,
                        ExecutionBudget.active < ExecutionBudget.max_concurrency,
                        ExecutionBudget.cancelled.is_(False),
                        ExecutionBudget.deadline > now(),
                    )
                    .values(calls=ExecutionBudget.calls + 1, active=ExecutionBudget.active + 1)
                    .execution_options(synchronize_session=False)
                ).rowcount
                if not changed:
                    raise ConnectorError("BUDGET_EXCEEDED", "Shared invocation/concurrency budget is exhausted")
                acquired = True
                prior.input_metadata = {
                    **prior.input_metadata,
                    "dispatched": True,
                    "credential_scope": credential_scope(db, connection),
                    "plot_ids": sorted(plot_ids),
                }
                audit(db, current, prior.id, "tool_invocation_started", tool_version_id=version.id, mode=mode)
                configuration = config.configuration.copy()
                # Detached immutable specification snapshots only; no live DB sessions across adapter work.
                specification = version.specification.copy()
                self_version = type(
                    "PinnedTool",
                    (),
                    {
                        "specification": specification,
                        "id": version.id,
                        "version": version.version,
                        "digest": version.digest,
                    },
                )()
                adapter_type = connection.adapter_type
                db.commit()
            limits = specification["policy"]
            http = SafeHttp(
                gate,
                timeout=min(limits["timeout_seconds"], get_settings().connector_http_timeout),
                limit=min(limits["max_response_bytes"], get_settings().connector_max_response_bytes),
            )
            async with asyncio.timeout(max(0.001, context.deadline - time.monotonic())):
                if adapter_type == "rest":
                    from src.integrations.rest_adapter import RestConnector

                    output = await RestConnector(http, configuration, headers).invoke(self_version, bound, context)
                elif adapter_type == "mcp":
                    from src.integrations.mcp_client import McpConnector

                    output = await McpConnector(http, configuration, headers).invoke(self_version, bound, context)
                else:
                    from src.providers.factory import BuiltInProviderConnector

                    output = await BuiltInProviderConnector(http, configuration, headers, credential).invoke(
                        self_version, bound, context
                    )
            clean_data = redact(output.data, secret_values)
            model_data = redact(output.model_data, secret_values) if output.model_data is not None else clean_data
            # API output redaction occurs before both evidence storage and model context.
            source = redact(output.source, secret_values)
            retrieved = now().isoformat()
            _, is_fixture = destination(configuration["base_url"])
            with SessionLocal() as db:
                gate.check(db)
                evidence_ids = []
                if output.data_outcome in ("VALID", "UNSTRUCTURED", "PARTIAL"):
                    envelope = {
                        "schema_version": 2,
                        "tool_version_id": self_version.id,
                        "invocation_id": context.invocation_id,
                        "source": source,
                        "retrieved_at": retrieved,
                        "observed_at": source.get("observed_at"),
                        "valid_time_range": source.get("valid_time_range"),
                        "validation_status": output.data_outcome,
                        "classification": "fixture" if is_fixture else "live",
                        "input_synthetic": all(p["synthetic"] for p in context.plots) if context.plots else None,
                        "plot_id": context.plot_ids[0] if len(context.plot_ids) == 1 else None,
                        "permitted_plot_ids": context.plot_ids,
                        "payload_digest": digest(clean_data),
                        "provider_response_digests": db.get(ToolInvocation, context.invocation_id).input_metadata.get(
                            "response_digests", []
                        ),
                        "limitations": output.limitations,
                        "values": {
                            "kind": specification["evidence_semantics"].get("value_kind", "connector_evidence"),
                            "payload": clean_data,
                        },
                    }
                    row = WorkspaceRecord(
                        office_id=context.principal.office_id,
                        kind="evidence",
                        data=envelope,
                        created_by=context.principal.user_id,
                    )
                    db.add(row)
                    db.flush()
                    evidence_ids.append(row.id)
                encoded = json.dumps(model_data, ensure_ascii=False)
                result = {
                    "execution_outcome": output.execution_outcome,
                    "data_outcome": output.data_outcome,
                    "invocation_id": context.invocation_id,
                    "tool_version_id": self_version.id,
                    "evidence_ids": evidence_ids,
                    "data": model_data if len(encoded.encode()) <= 8192 else None,
                    "large_result": len(encoded.encode()) > 8192,
                    "payload_digest": digest(clean_data),
                    "source": source,
                    "retrieved_at": retrieved,
                    "limitations": output.limitations,
                    "cache_hit": False,
                    "classification": "fixture" if is_fixture else "live",
                    "actual_cost_usd": None,
                    "estimated_cost_usd": None,
                }
                invocation = db.get(ToolInvocation, context.invocation_id)
                invocation.status = output.execution_outcome
                invocation.result = result
                invocation.finished_at = now()
                ttl = limits["cache_ttl_seconds"]
                if ttl and output.data_outcome in ("VALID", "UNSTRUCTURED"):
                    db.merge(
                        ConnectorCache(
                            key=cache_key,
                            office_id=context.principal.office_id,
                            result=result,
                            expires_at=now() + timedelta(seconds=ttl),
                        )
                    )
                audit(
                    db,
                    context.principal,
                    invocation.id,
                    "tool_invocation_completed",
                    data_outcome=output.data_outcome,
                    evidence_ids=evidence_ids,
                )
                db.commit()
                if ttl and output.data_outcome in ("VALID", "UNSTRUCTURED"):
                    shared_cache.put(cache_key, result, now() + timedelta(seconds=ttl))
                return result
        except (ConnectorError, asyncio.TimeoutError, asyncio.CancelledError) as exc:
            error = (
                exc
                if isinstance(exc, ConnectorError)
                else ConnectorError(
                    "CANCELLED" if isinstance(exc, asyncio.CancelledError) else "TIMEOUT",
                    "Execution cancelled" if isinstance(exc, asyncio.CancelledError) else "Execution deadline exceeded",
                )
            )
            result = {
                "execution_outcome": error.code,
                "data_outcome": "INVALID",
                "error": error.as_dict(),
                "invocation_id": context.invocation_id if context else None,
                "evidence_ids": [],
            }
            if context:
                self.record_failure(context, result, acquired=acquired)
            return result
        except Exception as exc:
            # Never interpolate an exception containing provider response bodies, URLs or credentials.
            import logging
            import traceback

            logging.getLogger(__name__).error(
                "Connector internal exception %s at %s",
                type(exc).__name__,
                [(frame.name, frame.lineno) for frame in traceback.extract_tb(exc.__traceback__)[-3:]],
            )
            result = {
                "execution_outcome": "UPSTREAM_ERROR",
                "data_outcome": "INVALID",
                "evidence_ids": [],
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": "Connector execution failed; inspect sanitized attempt records",
                    "retryable": False,
                },
            }
            if context:
                self.record_failure(context, result, acquired=acquired)
            return result
        finally:
            if acquired and context:
                with SessionLocal() as db:
                    db.execute(
                        update(ExecutionBudget)
                        .where(ExecutionBudget.id == context.budget_id, ExecutionBudget.active > 0)
                        .values(active=ExecutionBudget.active - 1)
                    )
                    db.commit()


class LegacyDispatchGate(DispatchGate):
    def __init__(self, context, run_id, capability):
        super().__init__(context)
        self.run_id, self.capability = run_id, capability

    def check(self, db, *, lock=False):
        from src.services.run_service import authorize_capability
        from src.db.models.advisory_run import AdvisoryRun
        from fastapi import HTTPException

        try:
            if lock:
                db.scalar(select(AdvisoryRun).where(AdvisoryRun.id == self.run_id).with_for_update(nowait=True))
            authorize_capability(db, self.run_id, self.capability)
            ensure_budget(db, self.context)
        except HTTPException:
            raise ConnectorError("POLICY_DENIED", "Internal run capability was revoked or expired") from None
