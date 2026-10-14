import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "farmly_pytest.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "farmly_test_secret_key_for_pytest_only"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "10080"
os.environ["DEBUG"] = "true"
os.environ["DEBUG_RESET_TOKEN"] = "test-debug-token"
os.environ["PHONE_CHANGE_COOLDOWN_SECONDS"] = "0"
os.environ["GEMINI_MODEL"] = "test-model"
os.environ["GEMINI_TIMEOUT_SECONDS"] = "20"
os.environ["SORGHUM_MODEL_SERVER_URL"] = "http://127.0.0.1:8001"

from src.db import models  # noqa: E402,F401
from src.db.base import Base  # noqa: E402
from src.db.schema_migrations import ensure_chat_message_storage_columns  # noqa: E402
from src.db.session import engine  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_chat_message_storage_columns(engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def mock_sms_provider(monkeypatch):
    import src.services.auth_service as auth_service

    monkeypatch.setattr(
        auth_service,
        "send_sms",
        lambda phone_number, text: {"status": "success", "phone_number": phone_number},
    )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
