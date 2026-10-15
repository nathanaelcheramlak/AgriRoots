from datetime import date
from typing import Literal
from pydantic import Field
from src.api.schemas.workspace import StrictModel
from src.api.schemas.actions import ActionCode, ACTIONS



class RunRequest(StrictModel):
    cluster_id: str
    task: str = Field(min_length=5, max_length=2000)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class EmptyInput(StrictModel):
    pass


class Plan(StrictModel):
    rationale: str = Field(min_length=1, max_length=400)
    first_tool: Literal["get_weather_evidence", "get_crop_risk_context", "get_public_guidance"]

    @property
    def tools(self):
        required = ["get_weather_evidence", "get_crop_risk_context", "get_public_guidance"]
        return [self.first_tool] + [name for name in required if name != self.first_tool]


class Candidate(StrictModel):
    plot_id: str
    crop: str
    action_code: ActionCode
    proposed_date: date
    evidence_ids: list[str] = Field(min_length=5, max_length=5)
    rationale: str = Field(min_length=1, max_length=400)
    uncertainty: str = Field(min_length=1, max_length=400)


class Candidates(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    recommendations: list[Candidate] = Field(min_length=1, max_length=20)
    missing_information: str = Field(max_length=2000)


class ToolError(StrictModel):
    code: str
    message: str
    retryable: bool = False


class ToolResult(StrictModel):
    ok: bool
    data: dict = Field(default_factory=dict)
    error: ToolError | None = None


from src.api.schemas.workspace import Plot, Season


class PlotContext(Plot):
    id: str
    synthetic: bool
    season_id: str
    season: Season


class HistoryOutput(StrictModel):
    plots: list[PlotContext] = Field(min_length=1, max_length=5)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class EvidenceOutput(StrictModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=25)


class RiskOutput(EvidenceOutput):
    warnings: list[dict]


class SaveOutput(StrictModel):
    advisory_id: str
    version: Literal[1]
    status: Literal["draft"]
