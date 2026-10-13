from src.config.settings import get_settings


def get_health_status() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
    }
