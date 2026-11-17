"""Catalog snapshots are evidence for review, never authority to execute a new tool."""

from sqlalchemy import select
from src.db.models.connectors import DiscoverySnapshot, RegisteredTool, ToolVersion
from src.integrations.contracts import ToolSpec, ConnectorError, digest
from src.integrations.service import IntegrationService, audit, bump
from src.integrations.schema_translation import checked_schema


def input_schema(raw):
    schema = dict(raw)
    # Explicitly tighten the remote contract: unknown fields are never forwarded.
    schema["additionalProperties"] = False
    return checked_schema(schema, inputs=True)


def stage_catalog(db, principal, connection, config, catalog, complete, diagnostics):
    service = IntegrationService(db, principal)
    previous = db.scalar(
        select(DiscoverySnapshot)
        .where(
            DiscoverySnapshot.connection_id == connection.id,
            DiscoverySnapshot.connection_revision == config.revision,
            DiscoverySnapshot.complete.is_(True),
        )
        .order_by(DiscoverySnapshot.created_at.desc())
    )
    old = {t["name"]: digest(t) for t in previous.catalog} if previous else {}
    current = {t["name"]: digest(t) for t in catalog}
    diff = {
        "added": sorted(current.keys() - old.keys()),
        "changed": sorted(name for name in current.keys() & old.keys() if current[name] != old[name]),
        "unchanged": sorted(name for name in current.keys() & old.keys() if current[name] == old[name]),
        "removed": sorted(old.keys() - current.keys()) if complete else [],
        "unsupported": [],
    }
    snapshot = DiscoverySnapshot(
        connection_id=connection.id,
        office_id=principal.office_id,
        connection_revision=config.revision,
        complete=complete,
        catalog=catalog,
        diff=diff,
        diagnostics=diagnostics,
    )
    db.add(snapshot)
    db.flush()
    for upstream in catalog:
        upstream_digest = current[upstream["name"]]
        existing_versions = list(
            db.scalars(select(ToolVersion).join(RegisteredTool).where(RegisteredTool.connection_id == connection.id))
        )
        existing = next(
            (
                v
                for v in existing_versions
                if v.specification.get("upstream_tool_name") == upstream["name"]
                and v.specification.get("discovery_digest") == upstream_digest
                and v.connection_revision == config.revision
            ),
            None,
        )
        if existing:
            continue
        tool = next(
            (
                db.get(RegisteredTool, v.tool_id)
                for v in existing_versions
                if v.specification.get("upstream_tool_name") == upstream["name"]
            ),
            None,
        )
        if tool:
            tool.enabled = False
            tool.revoked_reason = "upstream_definition_changed"
            tool.revision += 1
        alias = "mcp_" + digest({"connection": connection.id, "name": upstream["name"]})[:24]
        try:
            normalized = input_schema(upstream["inputSchema"])
            output = upstream.get("outputSchema")
            if output:
                checked_schema(output)
            spec = ToolSpec(
                name=alias,
                description="Unreviewed discovered MCP operation: " + upstream["name"][:200],
                capability_tags=["unreviewed.mcp"],
                input_json_schema=normalized,
                upstream_tool_name=upstream["name"],
                discovery_digest=upstream_digest,
                response={
                    "format": "json" if output else "text",
                    "provider_output_json_schema": output,
                    "normalized_output_json_schema": output or {"type": "string", "maxLength": 20000},
                },
            )
            # Registration validates this against the persisted snapshot in the same transaction.
            service.register_tool(
                connection.id,
                spec.model_dump(mode="json"),
                connection_revision=config.revision,
                expected_revision=tool.revision if tool else None,
                commit=False,
            )
        except ConnectorError as exc:
            diff["unsupported"].append({"name": upstream["name"], "reason": exc.as_dict()})
    for name in diff["removed"]:
        for tool in db.scalars(select(RegisteredTool).where(RegisteredTool.connection_id == connection.id)):
            latest = db.scalar(
                select(ToolVersion).where(ToolVersion.tool_id == tool.id, ToolVersion.version == tool.current_version)
            )
            if latest.specification.get("upstream_tool_name") == name:
                tool.enabled = False
                tool.revoked_reason = "upstream_tool_removed"
                tool.revision += 1
    snapshot.diff = diff
    audit(
        db,
        principal,
        connection.id,
        "mcp_discovery_staged",
        snapshot_id=snapshot.id,
        complete=complete,
        added=len(diff["added"]),
        changed=len(diff["changed"]),
        removed=len(diff["removed"]),
    )
    bump(db, principal.office_id)
    return snapshot
