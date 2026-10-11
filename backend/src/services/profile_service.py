from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.api.schemas.profile import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    OnboardingCompleteRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from src.auth.password import verify_password
from src.db.models.user import User, UserProfile
from src.repositories.user_repository import UserRepository
from src.repositories.verification_repository import (
    OTPVerificationRepository,
    PasswordResetVerificationRepository,
    PhoneChangeVerificationRepository,
)
from src.services.exceptions import ServiceError


def _split_crops(value: str | None) -> list[str]:
    if not value:
        return []
    return [crop.strip() for crop in value.split(",") if crop.strip()]


def _join_crops(crops: list[str]) -> str:
    return ",".join(crops)


def to_profile_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        user_id=profile.user_id,
        full_name=profile.full_name,
        phone_number=profile.phone_number,
        location=profile.location,
        preferred_language=profile.preferred_language,
        user_type=profile.user_type,
        years_experience=profile.years_experience,
        main_goal=profile.main_goal,
        crops_grown=_split_crops(profile.crops_grown),
        onboarding_completed=profile.onboarding_completed,
        onboarding_completed_at=profile.onboarding_completed_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


class ProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.otp = OTPVerificationRepository(db)
        self.phone_changes = PhoneChangeVerificationRepository(db)
        self.password_resets = PasswordResetVerificationRepository(db)

    def complete_onboarding(self, current_user: User, payload: OnboardingCompleteRequest) -> ProfileResponse:
        profile = self.users.get_or_create_profile(current_user.user_id)
        profile.full_name = payload.full_name
        profile.phone_number = payload.phone_number
        profile.location = payload.location
        profile.preferred_language = payload.preferred_language
        profile.user_type = payload.user_type
        profile.years_experience = payload.years_experience
        profile.main_goal = payload.main_goal
        profile.crops_grown = _join_crops(payload.crops_grown)
        profile.onboarding_completed = True
        profile.onboarding_completed_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(profile)
        return to_profile_response(profile)

    def get_profile(self, current_user: User) -> ProfileResponse:
        profile = self.users.get_profile(current_user.user_id)
        if not profile:
            raise ServiceError(404, "Profile not found")
        return to_profile_response(profile)

    def update_profile(self, current_user: User, payload: ProfileUpdateRequest) -> ProfileResponse:
        profile = self.users.get_profile(current_user.user_id)
        if not profile:
            raise ServiceError(404, "Profile not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ServiceError(400, "No fields provided for update")

        if "phone_number" in updates:
            raise ServiceError(400, "Phone number cannot be updated from this endpoint. Use phone-change flow.")

        if "crops_grown" in updates and updates["crops_grown"] is not None:
            updates["crops_grown"] = _join_crops(updates["crops_grown"])

        for field_name, field_value in updates.items():
            setattr(profile, field_name, field_value)

        self.db.commit()
        self.db.refresh(profile)
        return to_profile_response(profile)

    def delete_account(self, current_user: User, payload: AccountDeleteRequest) -> AccountDeleteResponse:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise ServiceError(401, "Current password is incorrect")

        self.phone_changes.delete_by_user(current_user.user_id)
        self.otp.delete_by_phone(current_user.phone_number)
        self.password_resets.delete_by_phone(current_user.phone_number)
        self.users.delete_user(current_user)
        self.db.commit()

        return AccountDeleteResponse(message="Account deleted successfully")
