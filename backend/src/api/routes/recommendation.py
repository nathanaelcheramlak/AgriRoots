from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.errors import raise_http_error
from src.api.schemas.recommendation import (
    FertilizerRecommendationRequest,
    RecommendationResponse,
    WeatherRecommendationResponse,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.services.exceptions import ServiceError
from src.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


def _service(db: Session) -> RecommendationService:
    return RecommendationService(db)


@router.post("/crops", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_crops(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    try:
        return _service(db).recommend_crops(current_user)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/fertilizer", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_fertilizer(
    payload: FertilizerRecommendationRequest = FertilizerRecommendationRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    try:
        return _service(db).recommend_fertilizer(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/weather", response_model=WeatherRecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_weather(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherRecommendationResponse:
    try:
        return _service(db).recommend_weather(current_user)
    except ServiceError as exc:
        raise_http_error(exc)
