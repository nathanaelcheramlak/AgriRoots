from functools import lru_cache

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

    app_name: str = "Farmly Backend"
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

    sorghum_model_path: str = "backend/model/farmly_sorghum_efficientnet_b0_best.pt"
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

    debug_reset_token: str | None = None

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
