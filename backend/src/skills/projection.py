"""Read-only, credential-free skill availability for officer workspaces."""
from urllib.parse import urlsplit

from src.db.models.connectors import Integration, IntegrationVersion, ToolVersion
from src.integrations.contracts import ConnectorError
from src.integrations.service import approval
from src.tools.registry import Registry


def execution_view(service, skill, current):
    active = service.version(skill.id, skill.enabled_version)[1] if skill.enabled_version else current
    manifest = active.manifest
    registry = Registry(service.db, service.principal)
    required = manifest["required_capabilities"]
    optional = manifest["optional_capabilities"]
    candidates = registry.tools(required + optional)
    dependencies = [{"capability": cap, "required": cap in required,
                     "available": any(cap in t["capability_tags"] for t in candidates)}
                    for cap in dict.fromkeys(required + optional)]
    available, reason, code, selected = False, None, None, candidates
    try:
        if service.principal.role == "viewer":
            raise ConnectorError("POLICY_DENIED", "Viewers cannot start investigations")
        snapshot = registry.snapshot(skill.id)
        selected = snapshot["tools"]
        if manifest["allowed_internal_actions"]:
            raise ConnectorError("UNSUPPORTED_CAPABILITY", "Internal-action skills are outside the Home investigation workflow")
        available = True
    except ConnectorError as error:
        reason, code = error.message, error.code
    tools = []
    for candidate in selected:
        spec = service.db.get(ToolVersion, candidate["version_id"]).specification
        connection = service.db.get(Integration, candidate["connection_id"])
        config = service.db.query(IntegrationVersion).filter_by(
            connection_id=connection.id, revision=candidate["connection_revision"]).one()
        tools.append({"name": spec["name"], "version_id": candidate["version_id"],
                      "capabilities": candidate["capability_tags"], "input_schema": candidate["input_schema"],
                      "plot_scoped": "plot_coordinates" in spec["required_data_classes"],
                      "requires_image": "image" in spec["required_data_classes"],
                      "optional": not bool(set(required) & set(candidate["capability_tags"])),
                      "source": {"name": connection.name, "host": urlsplit(config.configuration["base_url"]).hostname}})
    return {"available": available, "blocked_reason": reason, "blocked_code": code,
            "version": active.version, "approved": bool(approval(service.db, active.id, service.principal.office_id)),
            "manifest": manifest, "dependencies": dependencies, "tools": tools,
            "missing_optional_capabilities": [d["capability"] for d in dependencies if not d["required"] and not d["available"]]}
