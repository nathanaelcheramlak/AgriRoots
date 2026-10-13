from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.api.schemas.diagnosis import DiagnosisResponse
from src.db.models.user import User
from src.repositories.user_repository import UserRepository
from src.services.advisory_service import run_diagnosis
from src.services.exceptions import ServiceError
from src.services.upload_service import read_image_upload


class DiagnosisService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def diagnose_crop_health(self, current_user: User, image: UploadFile) -> DiagnosisResponse:
        profile = self.users.get_profile(current_user.user_id)
        if not profile:
            raise ServiceError(404, "Profile not found. Complete onboarding first.")

        image_bytes, content_type = read_image_upload(image)
        try:
            return run_diagnosis(profile, image_bytes, image_mime_type=content_type)
        except Exception as exc:
            raise ServiceError(502, f"Diagnosis provider request failed: {exc}") from exc
