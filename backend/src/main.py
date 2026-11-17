from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.integrations.contracts import ConnectorError
from src.api.routes.integrations import router as integrations_router
from src.api.routes.skills import router as skills_router
from src.api.routes.companion import router as companion_router

from src.api.routes.auth import router as auth_router
from src.api.routes.alert import router as alert_router
from src.api.routes.chat import router as chat_router
from src.api.routes.debug import router as debug_router
from src.api.routes.diagnosis import router as diagnosis_router
from src.api.routes.health import router as health_router
from src.api.routes.profile import router as profile_router
from src.api.routes.recommendation import router as recommendation_router
from src.api.routes.voice import router as voice_router
from src.api.routes.workspace import router as workspace_router
from src.api.routes.advisory_run import router as advisory_run_router
from src.config.settings import get_settings
from src.db.schema_migrations import migrate
from src.db.session import engine


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate(engine)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(alert_router)
app.include_router(diagnosis_router)
app.include_router(recommendation_router)
app.include_router(voice_router)
app.include_router(debug_router)

app.include_router(workspace_router)

app.include_router(advisory_run_router)
app.include_router(integrations_router)
app.include_router(skills_router)
app.include_router(companion_router)


@app.exception_handler(ConnectorError)
async def connector_error_handler(request, exc):
    import uuid
    codes = {"NOT_FOUND": 404, "AUTH_REQUIRED": 409, "AUTH_INVALID": 401, "POLICY_DENIED": 403,
             "EGRESS_BLOCKED": 403, "TOOL_REVOKED": 409, "APPROVAL_REQUIRED": 409, "VERSION_CONFLICT": 409,
             "INPUT_VALIDATION_FAILED": 422, "OUTPUT_VALIDATION_FAILED": 422, "UNSUPPORTED_SCHEMA": 422,
             "UNSUPPORTED_CAPABILITY": 422, "BUDGET_EXCEEDED": 429, "RATE_LIMITED": 429}
    return JSONResponse(status_code=codes.get(exc.code, 502), content={"error": {
        **exc.as_dict(), "correlation_id": str(uuid.uuid4())}})


@app.exception_handler(RequestValidationError)
async def safe_request_validation(request, exc):
    if request.url.path.startswith("/api/v1/"):
        errors = exc.errors()
        code = "UNSUPPORTED_AUTH" if any(tuple(error["loc"][-2:]) == ("authentication", "type")
            and error["type"] == "literal_error" for error in errors) else "UNSUPPORTED_TRANSPORT" if any(
                error["loc"][-1] == "transport" and error["type"] == "extra_forbidden" for error in errors) else "INPUT_VALIDATION_FAILED"
        return JSONResponse(status_code=422, content={"error": {"code": code,
            "message": "Invalid request configuration", "retryable": False,
            "fields": [{"path": list(error["loc"]), "type": error["type"]} for error in errors]}})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)
