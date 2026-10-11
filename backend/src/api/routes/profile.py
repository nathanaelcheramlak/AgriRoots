from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.errors import raise_http_error
from src.api.schemas.profile import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    OnboardingCompleteRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.services.exceptions import ServiceError
from src.services.profile_service import ProfileService


router = APIRouter(tags=["Onboarding"])


def _service(db: Session) -> ProfileService:
    return ProfileService(db)


@router.post(
    "/api/onboarding/complete",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def complete_onboarding(
    payload: OnboardingCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        return _service(db).complete_onboarding(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.get("/api/users/me/profile", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        return _service(db).get_profile(current_user)
    except ServiceError as exc:
        raise_http_error(exc)


@router.patch("/api/users/me/profile", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        return _service(db).update_profile(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.delete("/api/users/me", response_model=AccountDeleteResponse, tags=["Users"])
def delete_my_account(
    payload: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountDeleteResponse:
    try:
        return _service(db).delete_account(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)
