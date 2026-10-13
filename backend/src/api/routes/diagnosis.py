from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from src.api.errors import raise_http_error
from src.api.schemas.diagnosis import DiagnosisResponse
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.services.diagnosis_service import DiagnosisService
from src.services.exceptions import ServiceError


router = APIRouter(prefix="/api/crop-health", tags=["Crop Health"])


@router.post("/diagnose", response_model=DiagnosisResponse, status_code=status.HTTP_200_OK)
def diagnose_crop_health(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagnosisResponse:
    try:
        return DiagnosisService(db).diagnose_crop_health(current_user, image)
    except ServiceError as exc:
        raise_http_error(exc)
