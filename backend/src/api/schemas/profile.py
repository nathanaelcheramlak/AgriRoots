from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


UserType = Literal["aspiring", "beginner", "experienced", "explorer"]
MainGoal = Literal[
    "increase_yield",
    "reduce_costs",
    "sustainable_farming",
    "organic_farming",
    "market_access",
]


def _normalize_crops(values: list[str]) -> list[str]:
    cleaned = [v.strip().lower() for v in values if v and v.strip()]
    unique: list[str] = []
    for crop in cleaned:
        if crop not in unique:
            unique.append(crop)
    return unique


class OnboardingCompleteRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    location: str = Field(min_length=2, max_length=255)
    preferred_language: str = Field(min_length=2, max_length=20)
    user_type: UserType
    years_experience: int = Field(ge=0, le=80)
    main_goal: MainGoal
    crops_grown: list[str] = Field(min_length=1, max_length=30)

    @field_validator("crops_grown")
    @classmethod
    def validate_crops(cls, value: list[str]) -> list[str]:
        normalized = _normalize_crops(value)
        if not normalized:
            raise ValueError("At least one crop is required")
        return normalized


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, min_length=2, max_length=255)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=20)
    user_type: UserType | None = None
    years_experience: int | None = Field(default=None, ge=0, le=80)
    main_goal: MainGoal | None = None
    crops_grown: list[str] | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("crops_grown")
    @classmethod
    def validate_crops(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = _normalize_crops(value)
        if not normalized:
            raise ValueError("At least one crop is required")
        return normalized


class ProfileResponse(BaseModel):
    user_id: str
    full_name: str | None
    phone_number: str | None
    location: str | None
    preferred_language: str | None
    user_type: str | None
    years_experience: int | None
    main_goal: str | None
    crops_grown: list[str]
    onboarding_completed: bool
    onboarding_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AccountDeleteRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)


class AccountDeleteResponse(BaseModel):
    status: str = "success"
    message: str
