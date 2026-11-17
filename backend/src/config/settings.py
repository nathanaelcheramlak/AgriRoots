from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GOOGLE_TTS_VOICE_NAME = "en-US-Chirp3-HD-Aoede"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AgriRoots Backend"
    debug: bool = True

    database_url: str = Field(..., min_length=1)

    jwt_secret_key: str = Field(..., min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    otp_expire_minutes: int = 5
    otp_max_attempts: int = 5
    phone_change_cooldown_seconds: int = 60

    sms_ethiopia_api_key: str | None = None
    sms_ethiopia_base_url: str = "https://smsethiopia.et/api"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    gemini_timeout_seconds: int = 20

    isda_username: str | None = None
    isda_password: str | None = None

    kindwise_plant_id_api_key: str | None = None
    kindwise_crop_health_api_key: str | None = None

    sorghum_model_path: str = "backend/model/agriroots_sorghum_efficientnet_b0_best.pt"
    sorghum_model_server_url: str = "http://127.0.0.1:8001"
    sorghum_model_server_timeout_seconds: int = 30
    plant_id_sorghum_threshold: float = 0.35
    plant_id_supported_crop_threshold: float = 0.40
    sorghum_confident_threshold: float = 0.60
    sorghum_uncertain_threshold: float = 0.40


    enset_model_path: str = "backend/model/enset_efficientnet_b0_final_best.pt"
    enset_model_server_url: str = "http://127.0.0.1:8002"
    enset_model_server_timeout_seconds: int = 30
    plant_id_enset_threshold: float = 0.35
    enset_confident_threshold: float = 0.60
    enset_uncertain_threshold: float = 0.40

    google_cloud_project: str | None = None
    google_application_credentials: str | None = None
    google_cloud_location: str = "global"
    google_stt_language_code: str = "en-US"
    google_stt_model: str = "latest_short"
    google_tts_language_code: str = "en-US"
    google_tts_voice_name: str = DEFAULT_GOOGLE_TTS_VOICE_NAME
    google_tts_audio_encoding: str = "MP3"
    google_tts_speaking_rate: float = Field(default=0.96, ge=0.25, le=4.0)
    voice_audio_max_bytes: int = 10 * 1024 * 1024

    hasab_api_key: str | None = None
    hasab_api_base_url: str = "https://api.hasab.ai/api"
    hasab_timeout_seconds: int = 60
    hasab_amharic_language_code: str = "amh"
    hasab_tts_amharic_speaker_name: str = "Selam"

    advisory_model_url: str = "http://127.0.0.1:8081"
    advisory_model_id: str = "qwen3-0.6b-q8"
    advisory_model_key_file: str = str(Path(__file__).resolve().parents[2] / "runtime" / "model-api-key")
    advisory_model_revision: str = "23749fefcc72300e3a2ad315e1317431b06b590a"
    advisory_model_timeout: int = Field(default=180, ge=5, le=300)
    advisory_run_timeout: int = Field(default=600, ge=30, le=900)
    advisory_tool_timeout: int = Field(default=45, ge=5, le=90)
    advisory_max_tool_calls: int = Field(default=32, ge=4, le=64)
    advisory_compute_cost_per_hour: float = Field(default=0, ge=0)
    advisory_audio_provider: Literal["local", "cloud"] = "local"

    debug_reset_token: str | None = None

    app_env: Literal["development", "test", "production"] = "development"
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    secret_encryption_key: str | None = None
    secret_previous_encryption_keys: list[str] = []
    redis_url: str | None = None
    llm_provider: Literal["gemini", "local"] = "gemini"
    cloud_model_data_policy: Literal["synthetic_only", "approved_context", "environment_only"] = "synthetic_only"
    live_tests_enabled: bool = False
    live_model_tests_enabled: bool = False
    live_diagnosis_tests_enabled: bool = False
    external_actions_enabled: bool = False
    outbound_allowed_hosts: list[str] = ["api.open-meteo.com", "power.larc.nasa.gov", "api.isda-africa.com",
        "climateserv.servirglobal.net", "fpma.fao.org", "www.arcgis.com", "services5.arcgis.com",
        "api.eppo.int", "hapi.humdata.org", "api.heigit.org", "crop.kindwise.com", "storage.googleapis.com",
        "data.apps.fao.org", "asis-esri.fao.org", "earthengine.googleapis.com", "oauth2.googleapis.com"]
    outbound_hosts_policy_file: str | None = None
    connector_fixture_origins: list[str] = []
    connector_http_timeout: float = Field(default=15, ge=1, le=60)
    connector_max_response_bytes: int = Field(default=4194304, ge=1024, le=4194304)
    connector_run_seconds: int = Field(default=240, ge=5, le=600)
    connector_max_tool_calls: int = Field(default=24, ge=1, le=100)
    connector_max_provider_requests: int = Field(default=80, ge=1, le=200)
    connector_max_concurrency: int = Field(default=4, ge=1, le=16)
    connector_max_model_tools: int = Field(default=12, ge=1, le=32)
    connector_max_followups: int = Field(default=2, ge=0, le=4)
    connector_artifact_root: str = "private-data/connectors"
    provider_test_results_path: str | None = None
    internal_mcp_url: str | None = None
    connector_checkpoint_prepared: bool = False

    @field_validator("connector_fixture_origins")
    @classmethod
    def fixture_origins_are_explicit(cls, value, info):
        if value and info.data.get("app_env") == "production":
            raise ValueError("Fixture network exceptions are forbidden in production")
        return value

    @field_validator("google_tts_voice_name", mode="before")
    @classmethod
    def default_tts_voice(cls, value):
        if value is None:
            return DEFAULT_GOOGLE_TTS_VOICE_NAME
        if isinstance(value, str) and not value.strip():
            return DEFAULT_GOOGLE_TTS_VOICE_NAME
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"debug", "development", "dev"}:
                return True
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
