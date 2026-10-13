from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.auth import router as auth_router
from src.api.routes.alert import router as alert_router
from src.api.routes.chat import router as chat_router
from src.api.routes.debug import router as debug_router
from src.api.routes.diagnosis import router as diagnosis_router
from src.api.routes.health import router as health_router
from src.api.routes.profile import router as profile_router
from src.api.routes.recommendation import router as recommendation_router
from src.api.routes.voice import router as voice_router
from src.config.settings import get_settings
from src.db.base import Base
from src.db.schema_migrations import ensure_chat_message_storage_columns
from src.db.session import engine
from src.db import models 


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_chat_message_storage_columns(engine)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
