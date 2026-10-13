from fastapi import APIRouter

from src.services.health_service import get_health_status


router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return get_health_status()
