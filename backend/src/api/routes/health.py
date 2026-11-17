from fastapi import APIRouter

from src.services.health_service import get_health_status


router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return get_health_status()


@router.get("/health/live")
def live():
    return {"status": "ok", "provider_requests": 0}


@router.get("/health/ready")
def ready():
    from fastapi.responses import JSONResponse
    from sqlalchemy import text
    from src.db.session import engine
    from src.config.settings import get_settings
    dependencies = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        dependencies["database"] = "ready"
    except Exception:
        dependencies["database"] = "unavailable"
    settings = get_settings()
    if settings.redis_url:
        try:
            from src.tools.cache import client
            client(settings.redis_url).ping()
            dependencies["redis"] = "ready"
        except Exception:
            dependencies["redis"] = "unavailable"
    healthy = all(status == "ready" for status in dependencies.values())
    return JSONResponse(status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "unavailable", "dependencies": dependencies, "provider_requests": 0})
