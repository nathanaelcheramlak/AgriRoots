"""Office-scoped lifecycle operations. Tests, approval and enablement are separate transactions."""

from datetime import timedelta
from sqlalchemy import select, update

from src.config.settings import get_settings
from src.db.models.connectors import (
    Integration,
    IntegrationVersion,
    ConnectionCredential,
    RegisteredTool,
    ToolVersion,
    DefinitionApproval,
    RegistryGeneration,
    ConnectorJob,
    ExecutionBudget,
)
from src.db.models.connectors import DiscoverySnapshot
from src.db.models.workspace import WorkspaceEvent
from src.integrations.contracts import ConnectionSpec, ToolSpec, ConnectorError, digest, now
from src.integrations.mappings import check_mapping, mapped
from src.integrations.schema_translation import checked_schema, validate, model_schema
from src.integrations.safe_http import destination, fixed_url
from src.integrations.secrets import encrypt, redact, SENSITIVE
from src.tools.policy import require_admin, principal_for, authorized_plots, bind_and_check_arguments


def audit(db, principal, entity_id, action, **details):
    db.add(
        WorkspaceEvent(
            office_id=principal.office_id,
            actor_id=principal.user_id,
            entity_id=entity_id,
            action=action,
            details=redact(details),
        )
    )


def bump(db, office_id):
    table = RegistryGeneration.__table__
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(
        insert(table)
        .values(office_id=office_id, generation=1)
        .on_conflict_do_update(index_elements=["office_id"], set_={"generation": table.c.generation + 1})
    )


def approval(db, version_id, office_id, *, connection_digest=None, credential_scope=None):
    clauses = [DefinitionApproval.version_id == version_id, DefinitionApproval.office_id == office_id]
    if connection_digest is not None:
        clauses.append(DefinitionApproval.connection_digest == connection_digest)
    if credential_scope is not None:
        clauses.append(DefinitionApproval.credential_scope == credential_scope)
    return db.scalar(select(DefinitionApproval).where(*clauses).order_by(DefinitionApproval.created_at.desc()))


def credential_scope(db, connection):
    cred = db.scalar(
        select(ConnectionCredential).where(
            ConnectionCredential.connection_id == connection.id, ConnectionCredential.office_id == connection.office_id
        )
    )
    return (
        digest(
            {"credential_id": cred.id, "principal_scope": cred.principal_scope, "credential_revision": cred.revision}
        )
        if cred
        else digest({"auth": "none"})
    )


class IntegrationService:
    def __init__(self, db, principal):
        self.db = db
        self.principal = principal_for(db, principal.user_id)
        if self.principal.office_id != principal.office_id:
            raise ConnectorError("POLICY_DENIED", "Office membership changed")

    def owned(self, cls, ident, *, lock=False):
        query = select(cls).where(cls.id == ident, cls.office_id == self.principal.office_id)
        if lock:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if not row:
            raise ConnectorError("NOT_FOUND", "Object was not found in the authenticated office")
        return row

    def config(self, connection, revision=None):
        row = self.db.scalar(
            select(IntegrationVersion).where(
                IntegrationVersion.connection_id == connection.id,
                IntegrationVersion.revision == (revision or connection.config_revision),
            )
        )
        if not row:
            raise ConnectorError("VERSION_CONFLICT", "Connection revision was not found")
        return row

    def tool_version(self, connection_id, tool_id, version=None):
        tool = self.owned(RegisteredTool, tool_id)
        if tool.connection_id != connection_id:
            raise ConnectorError("NOT_FOUND", "Tool does not belong to this connection")
        row = self.db.scalar(
            select(ToolVersion).where(
                ToolVersion.tool_id == tool.id, ToolVersion.version == (version or tool.current_version)
            )
        )
        if not row:
            raise ConnectorError("VERSION_CONFLICT", "Tool version was not found")
        return tool, row

    def view(self, connection):
        versions = list(
            self.db.scalars(
                select(IntegrationVersion)
                .where(IntegrationVersion.connection_id == connection.id)
                .order_by(IntegrationVersion.revision)
            )
        )
        cred = self.db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
        return {
            "id": connection.id,
            "name": connection.name,
            "adapter_type": connection.adapter_type,
            "revision": connection.revision,
            "config_revision": connection.config_revision,
            "enabled_revision": connection.enabled_revision,
            "enabled": connection.enabled,
            "health": connection.health,
            "credential": {"reference": cred.id, "revision": cred.revision, "updated_at": cred.updated_at}
            if cred
            else None,
            "versions": [
                {"revision": v.revision, "digest": v.digest, "configuration": v.configuration} for v in versions
            ],
        }

    def tool_view(self, tool, version):
        connection = self.owned(Integration, tool.connection_id)
        approved = approval(
            self.db,
            version.id,
            self.principal.office_id,
            connection_digest=version.connection_digest,
            credential_scope=credential_scope(self.db, connection),
        )
        return {
            "id": tool.id,
            "version_id": version.id,
            "name": tool.name,
            "revision": tool.revision,
            "version": version.version,
            "digest": version.digest,
            "connection_revision": version.connection_revision,
            "connection_digest": version.connection_digest,
            "approved": bool(approved),
            "enabled": tool.enabled,
            "enabled_version": tool.enabled_version,
            "revoked_reason": tool.revoked_reason,
            "specification": version.specification,
        }

    def validate_connection(self, spec):
        config = ConnectionSpec.model_validate(spec).model_dump(mode="json")
        destination(config["base_url"], fixed_origin=config["adapter_type"] != "mcp")
        if config["adapter_type"] == "builtin":
            from src.providers.factory import handler_definition

            definition = handler_definition(config["handler_id"])
            if definition["base_url"] != config["base_url"].rstrip("/"):
                raise ConnectorError("POLICY_DENIED", "A built-in handler must use its reviewed provider origin")
        return config

    def create(self, spec, *, commit=True):
        require_admin(self.principal)
        config = self.validate_connection(spec)
        row = Integration(
            office_id=self.principal.office_id,
            name=config["name"],
            adapter_type=config["adapter_type"],
            created_by=self.principal.user_id,
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(
            IntegrationVersion(
                connection_id=row.id,
                revision=1,
                digest=digest(config),
                configuration=config,
                created_by=self.principal.user_id,
            )
        )
        self.db.flush()
        bump(self.db, self.principal.office_id)
        audit(self.db, self.principal, row.id, "integration_draft_created", adapter_type=row.adapter_type)
        if commit:
            self.db.commit()
        return row

    def revise(self, connection_id, spec, expected_revision):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id, lock=True)
        if connection.revision != expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Connection changed; reload before editing")
        config = self.validate_connection(spec)
        if config["adapter_type"] != connection.adapter_type:
            raise ConnectorError("VERSION_CONFLICT", "Adapter type is immutable; create a separate connection")
        changed = self.db.execute(
            update(Integration)
            .where(Integration.id == connection.id, Integration.revision == expected_revision)
            .values(revision=Integration.revision + 1, config_revision=Integration.config_revision + 1)
        ).rowcount
        if not changed:
            raise ConnectorError("VERSION_CONFLICT", "Concurrent connection revision")
        self.db.refresh(connection)
        self.db.add(
            IntegrationVersion(
                connection_id=connection.id,
                revision=connection.config_revision,
                digest=digest(config),
                configuration=config,
                created_by=self.principal.user_id,
            )
        )
        audit(self.db, self.principal, connection.id, "integration_revision_created", digest=digest(config))
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return connection

    def credential(self, connection_id, payload):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id, lock=True)
        if self.config(connection).configuration["authentication"]["type"] == "none":
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Anonymous connections do not accept credentials")
        value = payload.value
        if not isinstance(value, (str, dict)) or not value:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "A nonempty credential is required")
        if isinstance(value, str) and any(c in value for c in "\r\n"):
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Credential cannot contain header delimiters")
        from src.integrations.secrets import reject_platform_credentials

        reject_platform_credentials(value)
        ciphertext = encrypt(value)
        row = self.db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
        changed_scope = bool(row and row.principal_scope != payload.principal_scope)
        if row:
            row.ciphertext = ciphertext
            row.principal_scope = payload.principal_scope
            row.revision += 1
            row.updated_at = now()
        else:
            row = ConnectionCredential(
                office_id=self.principal.office_id,
                connection_id=connection.id,
                ciphertext=ciphertext,
                principal_scope=payload.principal_scope,
            )
            self.db.add(row)
        # Rotation always suspends dispatch until explicitly tested and re-enabled.
        connection.enabled = False
        connection.revision += 1
        connection.health = "AUTH_REQUIRED"
        self.db.flush()
        audit(
            self.db,
            self.principal,
            connection.id,
            "credential_rotated",
            changed_scope=changed_scope,
            credential_revision=row.revision,
        )
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return {
            "reference": row.id,
            "revision": row.revision,
            "connection_revision": connection.revision,
            "retest_required": True,
        }

    def register_tool(self, connection_id, spec, *, connection_revision=None, expected_revision=None, commit=True):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id, lock=True)
        config = self.config(connection, connection_revision)
        tool_spec = ToolSpec.model_validate(spec).model_dump(mode="json")
        checked_schema(tool_spec["input_json_schema"], inputs=True)
        checked_schema(tool_spec["response"]["normalized_output_json_schema"])
        if tool_spec["response"].get("provider_output_json_schema"):
            checked_schema(tool_spec["response"]["provider_output_json_schema"])
        model_schema(tool_spec)
        if connection.adapter_type == "rest":
            fixed_url(config.configuration["base_url"], tool_spec["request"]["path"])
            if tool_spec["effect_classification"] != "READ_ONLY" or tool_spec["response"]["format"] != "json":
                raise ConnectorError("POLICY_DENIED", "Custom REST tools support read-only JSON operations")
            if tool_spec["upstream_tool_name"]:
                raise ConnectorError("INPUT_VALIDATION_FAILED", "REST tools cannot name an MCP tool")
        if connection.adapter_type == "builtin":
            from src.providers.factory import handler_definition

            definition = handler_definition(config.configuration["handler_id"])
            if definition.get("image") and (tool_spec["required_data_classes"] != ["image"] or
                    tool_spec["context_bindings"] != {"image_asset_id": "run.image_asset_id"}):
                raise ConnectorError("POLICY_DENIED", "Diagnosis requires the reviewed server-bound image asset contract")
            if definition.get("geo") and "plot_coordinates" not in tool_spec["required_data_classes"]:
                raise ConnectorError("POLICY_DENIED", "Route coordinates require reviewed geographic data transfer")
            if (
                tool_spec["capability_tags"] != [definition["capability"]]
                or tool_spec["effect_classification"] != "READ_ONLY"
            ):
                raise ConnectorError(
                    "POLICY_DENIED", "Built-in capabilities/effects must match the reviewed handler contract"
                )
        if connection.adapter_type != "builtin" and any(
            tag.startswith(("admin.", "auth.", "credentials.", "advisory.", "integrations."))
            for tag in tool_spec["capability_tags"]
        ):
            raise ConnectorError(
                "POLICY_DENIED", "Trusted internal capabilities cannot be supplied by installed external tools"
            )
        if "weather.forecast" in tool_spec["capability_tags"] and tool_spec["policy"]["cache_ttl_seconds"] > 21600:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "Forecast cache lifetime cannot exceed six hours")
        if connection.adapter_type == "mcp" and not tool_spec.get("discovery_digest"):
            raise ConnectorError("APPROVAL_REQUIRED", "MCP tool definitions must originate from discovery")
        if connection.adapter_type == "mcp":
            from src.integrations.discovery import input_schema

            snapshots = self.db.scalars(
                select(DiscoverySnapshot)
                .where(
                    DiscoverySnapshot.connection_id == connection.id,
                    DiscoverySnapshot.connection_revision == config.revision,
                )
                .order_by(DiscoverySnapshot.created_at.desc())
            )
            discovered = next(
                (
                    entry
                    for snapshot in snapshots
                    for entry in snapshot.catalog
                    if entry["name"] == tool_spec["upstream_tool_name"]
                    and digest(entry) == tool_spec["discovery_digest"]
                ),
                None,
            )
            if not discovered or input_schema(discovered["inputSchema"]) != tool_spec["input_json_schema"]:
                raise ConnectorError(
                    "VERSION_CONFLICT", "Tool schema/digest does not match an actual discovery snapshot"
                )
        if connection.adapter_type != "builtin" and tool_spec["effect_classification"] != "READ_ONLY":
            raise ConnectorError("POLICY_DENIED", "External side effects are not supported")
        for part in (tool_spec["request"]["query"], tool_spec["request"]["body"]):
            if part is not None:
                check_mapping(part, {"argument", "literal"})

                def reject_secret_fields(item):
                    if isinstance(item, dict):
                        for key, val in item.items():
                            if key not in {"source", "pointer", "required", "value"} and SENSITIVE.search(key):
                                raise ConnectorError(
                                    "POLICY_DENIED", "Credentials belong in header authentication, not mappings"
                                )
                            reject_secret_fields(val)
                    elif isinstance(item, list):
                        for val in item:
                            reject_secret_fields(val)

                reject_secret_fields(part)
        check_mapping(tool_spec["response"]["field_mapping"], {"response", "literal"})
        if not set(tool_spec["required_data_classes"]) <= set(config.configuration["egress_data_classes"]):
            raise ConnectorError("POLICY_DENIED", "Tool data classes exceed connection egress policy")
        tool = self.db.scalar(
            select(RegisteredTool).where(
                RegisteredTool.connection_id == connection.id, RegisteredTool.name == tool_spec["name"]
            )
        )
        if tool:
            if expected_revision is None or tool.revision != expected_revision:
                raise ConnectorError("VERSION_CONFLICT", "Existing tool requires its current expected_revision")
            tool.current_version += 1
            tool.revision += 1
        else:
            tool = RegisteredTool(
                office_id=self.principal.office_id, connection_id=connection.id, name=tool_spec["name"]
            )
            self.db.add(tool)
            self.db.flush()
        version = ToolVersion(
            tool_id=tool.id,
            office_id=self.principal.office_id,
            version=tool.current_version,
            connection_revision=config.revision,
            connection_digest=config.digest,
            digest=digest(tool_spec),
            specification=tool_spec,
            created_by=self.principal.user_id,
        )
        self.db.add(version)
        self.db.flush()
        audit(self.db, self.principal, tool.id, "tool_version_created", version=version.version, digest=version.digest)
        bump(self.db, self.principal.office_id)
        if commit:
            self.db.commit()
        return tool, version

    def exact(self, connection, tool_id, payload):
        tool, version = self.tool_version(connection.id, tool_id, payload.version)
        if version.digest != payload.digest or version.connection_revision != payload.connection_revision:
            raise ConnectorError("VERSION_CONFLICT", "Expected tool and connection digests do not match")
        return tool, version

    def preview(self, connection_id, tool_id, payload):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id)
        _, version = self.exact(connection, tool_id, payload)
        plots = authorized_plots(self.db, self.principal, payload.plot_ids)
        supplied = dict(payload.arguments)
        image_id = supplied.pop("image_asset_id", None) if "image_asset_id" in version.specification.get("context_bindings", {}) else None
        if image_id:
            from src.services.image_asset_service import owned_image
            owned_image(self.db, self.principal, image_id)
        arguments = bind_and_check_arguments(version.specification, supplied, plots, image_asset_id=image_id)
        validate(arguments, version.specification["input_json_schema"])
        request = version.specification["request"]
        config = self.config(connection, version.connection_revision).configuration
        if connection.adapter_type in ("mcp", "builtin"):
            result = {
                "adapter_type": connection.adapter_type,
                "arguments": arguments,
                "network_request_executed": False,
                "authentication": config["authentication"]["type"],
            }
            if connection.adapter_type == "mcp":
                result.update(
                    protocol_method="tools/call", upstream_tool_name=version.specification["upstream_tool_name"]
                )
            else:
                result.update(
                    handler_id=config["handler_id"], note="Reviewed handler may perform multiple bounded requests"
                )
            audit(self.db, self.principal, tool_id, "tool_request_previewed", version=version.version)
            self.db.commit()
            return redact(result)
        result = {
            "method": request["method"],
            "url": fixed_url(config["base_url"], request["path"])
            if connection.adapter_type != "mcp"
            else config["base_url"],
            "query": mapped(request["query"], arguments=arguments),
            "body": mapped(request["body"], arguments=arguments) if request["body"] is not None else None,
            "authentication": config["authentication"]["type"],
            "network_request_executed": False,
        }
        audit(self.db, self.principal, tool_id, "tool_request_previewed", version=version.version)
        self.db.commit()
        return redact(result)

    def approve_tool(self, connection_id, tool_id, payload):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id, lock=True)
        tool, version = self.exact(connection, tool_id, payload)
        if any(tag.startswith("unreviewed.") for tag in version.specification["capability_tags"]):
            raise ConnectorError(
                "APPROVAL_REQUIRED", "Assign reviewed capabilities and a trusted description before approval"
            )
        test = self.db.scalar(
            select(ConnectorJob)
            .where(
                ConnectorJob.office_id == self.principal.office_id,
                ConnectorJob.kind == "tool_test",
                ConnectorJob.target_id == version.id,
                ConnectorJob.status == "succeeded",
            )
            .order_by(ConnectorJob.created_at.desc())
        )
        current_scope = credential_scope(self.db, connection)
        if not test or test.snapshot.get("credential_scope") != current_scope:
            raise ConnectorError(
                "APPROVAL_REQUIRED", "A successful authorized test of this exact version/credential scope is required"
            )
        cred = self.db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
        if cred and test.snapshot.get("credential_revision") != cred.revision:
            raise ConnectorError("APPROVAL_REQUIRED", "Credential was rotated after the successful test")
        row = DefinitionApproval(
            office_id=self.principal.office_id,
            entity_type="tool",
            version_id=version.id,
            digest=version.digest,
            connection_digest=version.connection_digest,
            credential_scope=current_scope,
            reviewer_id=self.principal.user_id,
            test_id=test.id,
        )
        self.db.add(row)
        audit(self.db, self.principal, tool.id, "tool_version_approved", version=version.version, test_id=test.id)
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return self.tool_view(tool, version)

    def set_tool_enabled(self, connection_id, tool_id, payload):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id, lock=True)
        tool, version = self.tool_version(connection.id, tool_id, payload.version)
        if tool.revision != payload.expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Tool changed; reload before changing enablement")
        if payload.enabled and not approval(
            self.db,
            version.id,
            self.principal.office_id,
            connection_digest=version.connection_digest,
            credential_scope=credential_scope(self.db, connection),
        ):
            raise ConnectorError("APPROVAL_REQUIRED", "Approve the exact tool and connection version first")
        tool.enabled = payload.enabled
        tool.enabled_version = version.version if payload.enabled else tool.enabled_version
        tool.revoked_reason = None if payload.enabled else "disabled_by_administrator"
        tool.revision += 1
        audit(self.db, self.principal, tool.id, "tool_enablement_changed", enabled=payload.enabled)
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return self.tool_view(tool, version)

    def set_enabled(self, connection_id, payload):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id, lock=True)
        if connection.revision != payload.expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Connection changed; reload before changing enablement")
        config = self.config(connection, payload.version)
        if payload.enabled:
            versions = self.db.scalars(
                select(ToolVersion)
                .join(RegisteredTool, ToolVersion.tool_id == RegisteredTool.id)
                .where(RegisteredTool.connection_id == connection.id, ToolVersion.connection_digest == config.digest)
            )
            scope = credential_scope(self.db, connection)
            if not any(
                approval(
                    self.db, v.id, self.principal.office_id, connection_digest=config.digest, credential_scope=scope
                )
                for v in versions
            ):
                raise ConnectorError(
                    "APPROVAL_REQUIRED", "Connection requires an approved tested operation for this revision"
                )
        connection.enabled = payload.enabled
        connection.enabled_revision = config.revision if payload.enabled else connection.enabled_revision
        connection.revision += 1
        audit(self.db, self.principal, connection.id, "integration_enablement_changed", enabled=payload.enabled)
        bump(self.db, self.principal.office_id)
        self.db.commit()
        return self.view(connection)

    def create_job(self, kind, target_id, request, *, snapshot=None):
        require_admin(self.principal) if kind != "skill_run" else None
        if self.principal.role == "viewer":
            raise ConnectorError("POLICY_DENIED", "Viewers cannot execute investigations")
        existing = self.db.scalar(
            select(ConnectorJob).where(
                ConnectorJob.office_id == self.principal.office_id, ConnectorJob.request_key == request["request_key"]
            )
        )
        request_hash = digest({"kind": kind, "target_id": target_id, "request": request})
        if existing:
            if existing.request_digest != request_hash or existing.principal_id != self.principal.user_id:
                raise ConnectorError("VERSION_CONFLICT", "Idempotency key belongs to a different request")
            return existing
        settings = get_settings()
        budget = ExecutionBudget(
            office_id=self.principal.office_id,
            max_calls=settings.connector_max_tool_calls,
            max_requests=settings.connector_max_provider_requests,
            max_concurrency=settings.connector_max_concurrency,
            deadline=now() + timedelta(seconds=settings.connector_run_seconds),
        )
        self.db.add(budget)
        self.db.flush()
        row = ConnectorJob(
            office_id=self.principal.office_id,
            principal_id=self.principal.user_id,
            kind=kind,
            target_id=target_id,
            request_key=request["request_key"],
            request_digest=request_hash,
            request=request,
            snapshot=snapshot or {},
            budget_id=budget.id,
        )
        self.db.add(row)
        self.db.flush()
        audit(self.db, self.principal, row.id, "connector_job_queued", kind=kind)
        self.db.commit()
        return row

    def queue_tool_test(self, connection_id, tool_id, payload):
        require_admin(self.principal)
        connection = self.owned(Integration, connection_id)
        _, version = self.exact(connection, tool_id, payload)
        config = self.config(connection, version.connection_revision)
        _, fixture = destination(config.configuration["base_url"])
        if not fixture and not get_settings().live_tests_enabled:
            raise ConnectorError(
                "POLICY_DENIED", "Set LIVE_TESTS_ENABLED=true before an explicitly authorized real-provider test"
            )
        plots = authorized_plots(self.db, self.principal, payload.plot_ids)
        supplied = dict(payload.arguments)
        image_id = supplied.pop("image_asset_id", None) if "image_asset_id" in version.specification.get("context_bindings", {}) else None
        if image_id:
            from src.services.image_asset_service import owned_image
            owned_image(self.db, self.principal, image_id)
        arguments = bind_and_check_arguments(version.specification, supplied, plots, image_asset_id=image_id)
        validate(arguments, version.specification["input_json_schema"])
        if not payload.authorize_network:
            raise ConnectorError("POLICY_DENIED", "Explicit network authorization is required for a provider test")
        cred = self.db.scalar(select(ConnectionCredential).where(ConnectionCredential.connection_id == connection.id))
        return self.create_job(
            "tool_test",
            version.id,
            payload.model_dump(mode="json"),
            snapshot={
                "connection_id": connection.id,
                "connection_revision": version.connection_revision,
                "credential_scope": credential_scope(self.db, connection),
                "credential_revision": cred.revision if cred else None,
            },
        )
