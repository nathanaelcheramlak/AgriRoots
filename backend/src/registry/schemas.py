from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from src.integrations.contracts import Strict


class TerritoryInput(Strict):
    name: str = Field(min_length=1, max_length=120)
    region: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=600)
    boundary: dict


class Review(Strict):
    expected_revision: int = Field(ge=1)
    decision: Literal["approve", "reject", "deactivate"]


class TerritoryEdit(TerritoryInput):
    expected_revision: int = Field(ge=1)


class AssignmentInput(Strict):
    user_id: str
    role: Literal["manager", "reader"] = "manager"
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def dates(self):
        if any(v is not None and v.tzinfo is None for v in (self.starts_at, self.ends_at)):
            raise ValueError("Assignment times require a timezone")
        if self.ends_at and self.ends_at <= (self.starts_at or datetime.now(UTC)):
            raise ValueError("Assignment end must follow its start")
        return self


class FarmerInput(Strict):
    territory_id: str
    reference: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    village: str = Field(default="", max_length=100)
    language: str = Field(default="", max_length=40)
    channel: Literal["sms", "voice", "smartphone", "email", "none", "in-person"] = "none"
    consent: Literal["unknown", "granted", "declined"] = "unknown"
    consent_purpose: str = Field(default="registry management", max_length=200)
    household: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=160)
    preferences: str = Field(default="", max_length=600)
    notes: str = Field(default="", max_length=1000)
    synthetic: bool = False


class FarmerEdit(FarmerInput):
    expected_revision: int = Field(ge=1)


class SeasonInput(Strict):
    crop: str | None = Field(default=None, max_length=80)
    planting_date: date | None = None
    harvest_date: date | None = None
    stage: str | None = Field(default=None, max_length=80)
    irrigation: Literal["unknown", "none", "available"] = "unknown"
    irrigation_method: str | None = Field(default=None, max_length=80)
    previous_crop: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def dates(self):
        if self.planting_date and self.harvest_date and self.harvest_date < self.planting_date:
            raise ValueError("Harvest precedes planting")
        return self


class PlotInput(Strict):
    name: str = Field(min_length=1, max_length=120)
    geometry: dict
    farmer_ids: list[str] = Field(min_length=1, max_length=10)
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    observation: str | None = Field(default=None, max_length=1000)
    association_role: Literal["owner", "operator", "manager"] = "operator"
    season: SeasonInput | None = None
    acknowledge_overlaps: bool = False
    synthetic: bool = False
    request_key: str = Field(min_length=8, max_length=100)

    @field_validator("farmer_ids")
    @classmethod
    def distinct(cls, ids):
        if len(set(ids)) != len(ids):
            raise ValueError("Farmer IDs must be distinct")
        return ids


class PlotEdit(PlotInput):
    expected_revision: int = Field(ge=1)


class FarmRegistration(Strict):
    """The map-first form: geographic scope plus only three farmer fields."""

    selection_boundary: dict
    geometry: dict
    farmer_name: str = Field(min_length=1, max_length=120)
    farmer_reference: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=7, max_length=40, pattern=r"^\+?[0-9 ()-]{7,40}$")
    request_key: str = Field(min_length=8, max_length=100)

    @field_validator("phone")
    @classmethod
    def phone_digits(cls, value):
        if not 7 <= sum(c.isdigit() for c in value) <= 15:
            raise ValueError("Use a telephone number containing 7 to 15 digits")
        return value


class ObservationInput(Strict):
    provenance: Literal["measured", "self-reported", "model-derived", "synthetic"]
    observed_at: datetime | None = None
    metric: str = Field(min_length=1, max_length=80)
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=200)
    uncertainty: str | None = Field(default=None, max_length=200)
