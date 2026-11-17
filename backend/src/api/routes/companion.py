"""Read-only Home projection of existing membership, records and runtime registry."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from src.api.routes.integrations import service
from src.config.settings import get_settings
from src.db.models.connectors import RegisteredSkill
from src.db.models.workspace import Office, WorkspaceRecord
from src.integrations.contracts import ConnectorError
from src.tools.registry import Registry

router = APIRouter(prefix="/api/v1/companion", tags=["Officer Home"])


class HomePlot(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    area: float
    area_unit: str
    synthetic: bool
    crop: str | None = None
    planting_date: str | None = None


class HomeTool(BaseModel):
    name: str
    version_id: str
    capabilities: list[str]
    input_schema: dict[str, Any]
    plot_scoped: bool
    requires_image: bool
    optional: bool


class HomeSkill(BaseModel):
    id: str
    name: str
    description: str
    version: int | None = None
    available: bool
    blocked_reason: str | None = None
    tools: list[HomeTool] = []
    missing_optional_capabilities: list[str] = []


class HomeModel(BaseModel):
    provider: Literal["gemini", "local"]
    model: str
    configured: bool
    execution_enabled: bool
    blocked_reason: str | None
    plot_data_policy: str
    reachability_verified: bool = False


class HomeContext(BaseModel):
    user_id: str
    office_id: str
    office_name: str
    role: str
    plots: list[HomePlot]
    skills: list[HomeSkill]
    model: HomeModel
    max_plots_per_run: int = 5
    server_area_query: bool = False
    shared_conversation: bool = False
    territory_workspace: dict | None = None
    registry_workspace: dict | None = None


@router.get("/context", response_model=HomeContext)
def context(s: Annotated[Any, Depends(service)], plot_ids: str | None = Query(None, max_length=200)):
    settings = get_settings()
    office = s.db.get(Office, s.principal.office_id)
    # Registry pages are bounded; only authorized records become Home points.
    from src.registry.service import FarmRegistry
    from src.db.models.farm_registry import RegisteredPlot, CropSeason
    from src.registry.access import territory_scope
    from src.db.models.farm_registry import Territory
    registry = FarmRegistry(s.db, s.principal)
    allowed = select(RegisteredPlot.id).where(RegisteredPlot.office_id == office.id,
        RegisteredPlot.territory_id.in_(select(Territory.id).where(territory_scope(s.principal))))
    query = select(WorkspaceRecord).where(WorkspaceRecord.office_id == office.id,
        WorkspaceRecord.kind == "plot",
        (~WorkspaceRecord.id.in_(select(RegisteredPlot.id))) | WorkspaceRecord.id.in_(allowed))
    if plot_ids:
        ids = plot_ids.split(",")
        from src.tools.policy import authorized_plots
        authorized_plots(s.db, s.principal, ids)
        query = query.where(WorkspaceRecord.id.in_(ids))
    records = list(s.db.scalars(query.order_by(WorkspaceRecord.created_at, WorkspaceRecord.id).limit(100)))
    plots = []
    for record in records:
        data = record.data
        registered = s.db.get(RegisteredPlot, record.id)
        if registered:
            plots.append(HomePlot(**registry.plot_view(registered)["home_plot"]))
            continue
        household = s.db.get(WorkspaceRecord, data.get("household_id")) if data.get("household_id") else None
        if not household or household.office_id != office.id:
            continue
        seasons = list(s.db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.office_id == office.id,
            WorkspaceRecord.kind == "season", WorkspaceRecord.data["plot_id"].as_string() == record.id)
            .order_by(WorkspaceRecord.created_at.desc()).limit(1)))
        season = seasons[0].data if seasons else {}
        plots.append(HomePlot(id=record.id, name=data["name"], latitude=data["latitude"], longitude=data["longitude"],
            area=data["area"], area_unit=data["area_unit"], synthetic=household.data.get("synthetic") is True,
            crop=season.get("crop"), planting_date=season.get("planting_date")))
    territories = registry.territories(limit=100)
    for item in territories["items"]:
        item["authorizedPlotIds"] = [p.id for p in plots if (registration := s.db.get(RegisteredPlot, p.id))
            and registration.territory_id == item["id"]]
    skills = []
    from src.db.models.connectors import ToolVersion

    for skill in s.db.scalars(
        select(RegisteredSkill).where(RegisteredSkill.office_id == office.id).order_by(RegisteredSkill.name)
    ):
        item = HomeSkill(id=skill.id, name=skill.name, description="", available=False)
        try:
            if s.principal.role == "viewer":
                raise ConnectorError("POLICY_DENIED", "Viewers cannot start investigations")
            snapshot = Registry(s.db, s.principal).snapshot(skill.id)
            if settings.cloud_model_data_policy == "environment_only":
                from src.agent.companion.environment_policy import scope_environment_snapshot
                try:
                    snapshot = scope_environment_snapshot(snapshot)
                except ConnectorError:
                    continue
            item.version = snapshot["skill_version"]
            item.description = snapshot["manifest"]["description"]
            item.missing_optional_capabilities = snapshot["missing_optional_capabilities"]
            for tool in snapshot["tools"]:
                spec = s.db.get(ToolVersion, tool["version_id"]).specification
                item.tools.append(
                    HomeTool(
                        name=spec["name"],
                        version_id=tool["version_id"],
                        capabilities=tool["capability_tags"],
                        input_schema=tool["input_schema"],
                        plot_scoped="plot_coordinates" in spec["required_data_classes"],
                        requires_image="image" in spec["required_data_classes"],
                        optional=not bool(
                            set(tool["capability_tags"]) & set(snapshot["manifest"]["required_capabilities"])
                        ),
                    )
                )
            # Prevent a second release/write workflow from entering the Home evidence companion.
            if snapshot["manifest"]["allowed_internal_actions"]:
                raise ConnectorError(
                    "UNSUPPORTED_CAPABILITY", "This skill uses an internal action outside Home investigations"
                )
            item.available = True
        except ConnectorError as error:
            item.blocked_reason = error.message
        skills.append(item)
    if settings.cloud_model_data_policy == "environment_only":
        # One Home choice per capability combination, preferring the existing FieldOps skills.
        unique = {}
        for item in sorted(skills, key=lambda k: (not k.name.startswith("fieldops_"), k.name)):
            key = tuple(sorted({cap for tool in item.tools for cap in tool.capabilities}))
            if key and set(key) <= {"weather.forecast", "soil.profile"}:
                unique.setdefault(key, item)
        skills = list(unique.values())
    if settings.llm_provider == "gemini":
        configured = bool(
            settings.gemini_api_key and settings.gemini_model and "gemini_model" in settings.model_fields_set
        )
        model = HomeModel(
            provider="gemini",
            model=settings.gemini_model,
            configured=configured,
            execution_enabled=settings.live_model_tests_enabled,
            blocked_reason=(
                "Backend model requests are disabled by configuration."
                if configured and not settings.live_model_tests_enabled
                else None
                if configured
                else "The backend needs a Gemini key and an explicitly configured model."
            ),
            plot_data_policy=settings.cloud_model_data_policy,
        )
    else:
        try:
            from src.integrations.llm.local_adapter import LocalModel

            LocalModel()  # Validates configuration only; no model request is sent.
            from pathlib import Path

            key_file = Path(settings.advisory_model_key_file)
            configured = key_file.is_file() and key_file.stat().st_size > 0
            reason = None if configured else "The backend local-model key file is unavailable."
        except (ValueError, OSError):
            configured, reason = False, "The backend local-model configuration is unavailable."
        model = HomeModel(
            provider="local",
            model=settings.advisory_model_id,
            configured=configured,
            execution_enabled=True,
            blocked_reason=reason,
            plot_data_policy="authorized_context",
        )
    return HomeContext(
        user_id=s.principal.user_id,
        office_id=office.id,
        office_name=office.name,
        role=s.principal.role,
        plots=plots,
        skills=skills,
        model=model,
        server_area_query=True,
        territory_workspace={"status": "available", "territories": territories["items"]},
        registry_workspace={"available": True, "version": 1, "spatial_engine": "postgis" if s.db.bind.dialect.name == "postgresql" else "sqlite-development", "plot_page_limit": 100, "territory_total": territories["total"]},
    )
