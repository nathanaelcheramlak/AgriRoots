from fastapi import UploadFile

from src.api.schemas.voice import VoiceSynthesisRequest, VoiceTranscriptionResponse
from src.db.models.user import User
from src.integrations.voice.google_stt import transcribe_audio
from src.integrations.voice.google_tts import synthesize_speech
from src.services.exceptions import ServiceError
from src.services.upload_service import read_audio_upload_async


def _preferred_language(current_user: User, override: str | None = None) -> str | None:
    if override and override.strip():
        return override.strip()
    profile = getattr(current_user, "profile", None)
    return getattr(profile, "preferred_language", None)


class VoiceService:
    async def transcribe_voice(
        self,
        current_user: User,
        audio: UploadFile,
        language_code: str | None = None,
    ) -> VoiceTranscriptionResponse:
        audio_bytes = await read_audio_upload_async(audio)
        try:
            result = transcribe_audio(
                audio_bytes,
                language_code=_preferred_language(current_user, language_code),
                filename=audio.filename or "voice-message.webm",
                content_type=audio.content_type or "audio/webm",
            )
        except Exception as exc:
            raise ServiceError(502, f"Voice transcription failed: {exc}") from exc

        return VoiceTranscriptionResponse(
            transcript=result.transcript,
            confidence=result.confidence,
            language_code=result.language_code,
        )

    def synthesize_voice(self, current_user: User, payload: VoiceSynthesisRequest) -> bytes:
        text = payload.text.strip()
        if not text:
            raise ServiceError(400, "Text cannot be empty.")

        try:
            return synthesize_speech(
                text,
                language_code=_preferred_language(current_user, payload.language_code),
            )
        except Exception as exc:
            raise ServiceError(502, f"Voice synthesis failed: {exc}") from exc
