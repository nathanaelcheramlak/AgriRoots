from sqlalchemy.orm import Session

from src.api.schemas.recommendation import (
    FertilizerRecommendationRequest,
    RecommendationResponse,
    WeatherRecommendationResponse,
)
from src.db.models.user import User
from src.repositories.user_repository import UserRepository
from src.services.advisory_service import (
    run_crop_recommendation,
    run_fertilizer_recommendation,
    run_weather_recommendation,
)
from src.services.exceptions import ServiceError


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def recommend_crops(self, current_user: User) -> RecommendationResponse:
        profile = self._require_profile(current_user)
        return RecommendationResponse(**run_crop_recommendation(profile))

    def recommend_fertilizer(
        self,
        current_user: User,
        payload: FertilizerRecommendationRequest,
    ) -> RecommendationResponse:
        profile = self._require_profile(current_user)
        return RecommendationResponse(**run_fertilizer_recommendation(profile, payload.target_crop))

    def recommend_weather(self, current_user: User) -> WeatherRecommendationResponse:
        profile = self._require_profile(current_user)
        try:
            result = run_weather_recommendation(profile)
        except ValueError as exc:
            raise ServiceError(400, str(exc)) from exc
        except Exception as exc:
            raise ServiceError(502, f"Weather provider request failed: {exc}") from exc
        return WeatherRecommendationResponse(**result)

    def _require_profile(self, current_user: User):
        profile = self.users.get_profile(current_user.user_id)
        if not profile:
            raise ServiceError(404, "Profile not found. Complete onboarding first.")
        return profile
