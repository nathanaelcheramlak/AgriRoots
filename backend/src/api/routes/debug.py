from fastapi import APIRouter, Header

from src.api.errors import raise_http_error
from src.services.debug_service import reset_all_data as reset_all_data_service
from src.services.exceptions import ServiceError


router = APIRouter(prefix="/api/debug", tags=["Debug"])


@router.post("/reset-all-data")
def reset_all_data(x_debug_token: str | None = Header(default=None)) -> dict:
    try:
        return reset_all_data_service(x_debug_token)
    except ServiceError as exc:
        raise_http_error(exc)
