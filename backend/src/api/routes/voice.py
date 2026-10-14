from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from src.api.errors import raise_http_error
from src.api.schemas.voice import VoiceSynthesisRequest, VoiceTranscriptionResponse
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.services.exceptions import ServiceError
from src.services.voice_service import VoiceService


router = APIRouter(prefix="/api/voice", tags=["Voice"])


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(
    audio: UploadFile = File(...),
    language_code: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
) -> VoiceTranscriptionResponse:
    try:
        return await VoiceService().transcribe_voice(current_user, audio, language_code)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/synthesize", response_class=Response)
def synthesize_voice(
    payload: VoiceSynthesisRequest,
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        audio_bytes = VoiceService().synthesize_voice(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)

    return Response(content=audio_bytes, media_type="audio/mpeg")
