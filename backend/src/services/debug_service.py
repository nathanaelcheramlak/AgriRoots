from src.config.settings import get_settings
from src.db import models  # noqa: F401
from src.db.base import Base
from src.db.session import engine
from src.services.exceptions import ServiceError


def reset_all_data(x_debug_token: str | None) -> dict:
    settings = get_settings()
    if not settings.debug:
        raise ServiceError(403, "Debug reset endpoint is disabled")

    if not settings.debug_reset_token:
        raise ServiceError(500, "DEBUG_RESET_TOKEN is not configured")

    if x_debug_token != settings.debug_reset_token:
        raise ServiceError(401, "Invalid debug token")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    return {
        "status": "success",
        "message": "Database reset completed: all tables dropped and recreated",
    }
