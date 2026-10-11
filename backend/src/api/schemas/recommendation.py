from pydantic import BaseModel, Field


class FertilizerRecommendationRequest(BaseModel):
    target_crop: str | None = Field(default=None, min_length=2, max_length=80)


class RecommendationResponse(BaseModel):
    recommendation_text: str
    location_used: str | None = None
    crops_used: list[str]
    soil_summary: dict | None = None
    weather_summary: dict | None = None
    used_fallback: bool


class WeatherRecommendationResponse(BaseModel):
    recommendation_text: str
    location_used: str
    raw_weather: dict
    used_fallback: bool
