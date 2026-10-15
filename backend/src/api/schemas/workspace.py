from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.api.schemas.actions import ActionCode


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Named(StrictModel):
    name: str = Field(min_length=1, max_length=200)


class MemberInput(StrictModel):
    user_id: str
    role: Literal["administrator", "officer", "farmer"]


class Cluster(Named):
    assigned_officer_id: str
    synthetic: bool = False


class Household(Named):
    farmer_user_id: str
    cluster_id: str
    assigned_officer_id: str
    synthetic: bool = False


class Plot(Named):
    household_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    area: float = Field(gt=0)
    area_unit: Literal["ha", "m2"]
    agroclimatic_zone: str = Field(min_length=1, max_length=200)


class Season(StrictModel):
    plot_id: str
    crop: str = Field(min_length=1, max_length=100)
    stage: Literal["planned", "growing"] = "growing"
    planting_date: date
    harvest_date: date | None = None
    previous_yield: float | None = Field(default=None, ge=0)
    yield_unit: Literal["kg", "kg/ha", "t/ha"] | None = None

    @model_validator(mode="after")
    def dates_and_units(self):
        if self.harvest_date and self.harvest_date < self.planting_date:
            raise ValueError("Harvest must follow planting")
        if (self.previous_yield is None) != (self.yield_unit is None):
            raise ValueError("Yield and yield unit must be provided together")
        return self


class PlantingRule(StrictModel):
    # These are office-reviewed parameters, never universal agronomic defaults.
    rain_days: int = Field(ge=1, le=3)
    minimum_rain_mm: float = Field(ge=0, le=1000)
    maximum_rain_mm: float = Field(ge=0, le=1000)
    maximum_temperature_c: float = Field(ge=-10, le=60)
    maximum_wind_kph: float = Field(ge=0, le=300)

    @model_validator(mode="after")
    def rainfall_range(self):
        if self.minimum_rain_mm > self.maximum_rain_mm:
            raise ValueError("Minimum rainfall cannot exceed maximum rainfall")
        return self


class Guidance(StrictModel):
    crop: str = Field(min_length=1, max_length=100)
    agroclimatic_zone: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)
    source: str = Field(min_length=1, max_length=500)
    reviewed_on: date
    supported_actions: list[ActionCode] = Field(default_factory=list)
    planting_rule: PlantingRule | None = None

    @model_validator(mode="after")
    def supported_planting(self):
        if {"plant_crop", "hold_planting"} & set(self.supported_actions) and not self.planting_rule:
            raise ValueError("Planting actions require explicit locally reviewed planting rules")
        return self


class Calendar(Guidance):
    planting_start: date
    planting_end: date
    harvest_start: date
    harvest_end: date

    @model_validator(mode="after")
    def ordered(self):
        if not self.planting_start <= self.planting_end <= self.harvest_start <= self.harvest_end:
            raise ValueError("Calendar dates must be ordered")
        return self


class Evidence(StrictModel):
    source_name: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=1000)
    observed_at: datetime
    retrieved_at: datetime
    valid_from: datetime
    valid_until: datetime
    location: str = Field(min_length=1, max_length=200)
    crop: str = Field(min_length=1, max_length=100)
    units: str = Field(min_length=1, max_length=100)
    values: dict
    snapshot: str = Field(min_length=1, max_length=20000)
    classification: Literal["live", "historical", "synthetic", "officer-entered"]
    plot_id: str | None = None

    @model_validator(mode="after")
    def times(self):
        for value in (self.observed_at, self.retrieved_at, self.valid_from, self.valid_until):
            if value.tzinfo is None:
                raise ValueError("Evidence timestamps require a timezone")
        if self.valid_until < self.valid_from or self.retrieved_at < self.observed_at:
            raise ValueError("Evidence timestamps are out of order")
        return self


RECORD_SCHEMAS = {"cluster": Cluster, "household": Household, "plot": Plot,
                  "season": Season, "guidance": Guidance, "calendar": Calendar, "evidence": Evidence}


class RecordInput(StrictModel):
    kind: Literal["cluster", "household", "plot", "season", "guidance", "calendar", "evidence"]
    data: dict
    expected_revision: int | None = Field(default=None, ge=1)


class Recommendation(StrictModel):
    action: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    uncertainty: str = Field(min_length=1, max_length=2000)
    proposed_date: date | None = None
    basis: str = Field(default="", max_length=3000)


class AdvisoryInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    household_ids: list[str] = Field(min_length=1, max_length=100)
    plot_ids: list[str] = Field(default_factory=list, max_length=300)
    assigned_officer_id: str
    language: Literal["en", "am"]
    recommendations: list[Recommendation] = Field(min_length=1, max_length=50)
    missing_information: str = Field(max_length=5000)
    # Every translation is part of the immutable reviewed content.
    translations: dict[Literal["en", "am"], list[str]] = Field(default_factory=dict)
    replaces_advisory_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def translation_lengths(self):
        if self.language in self.translations:
            raise ValueError("Primary language must not also be a translation")
        if any(len(v) != len(self.recommendations) or any(not s.strip() for s in v)
               for v in self.translations.values()):
            raise ValueError("Translations must contain one nonempty action per recommendation")
        return self


class Transition(StrictModel):
    action: Literal["submit", "approve", "reject", "cancel", "release"]
    expected_version: int = Field(ge=1)
    reason: str = Field(default="", max_length=2000)
