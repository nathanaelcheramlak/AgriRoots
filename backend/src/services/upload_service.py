from fastapi import UploadFile

from src.config.settings import get_settings
from src.services.exceptions import ServiceError


def read_image_upload(image: UploadFile) -> tuple[bytes, str]:
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise ServiceError(400, "Uploaded file must be an image.")

    image_bytes = image.file.read()
    if not image_bytes:
        raise ServiceError(400, "Uploaded image is empty.")

    return image_bytes, content_type


def read_audio_upload(audio: UploadFile) -> bytes:
    content_type = (audio.content_type or "").lower()
    if not content_type.startswith("audio/"):
        raise ServiceError(400, "Uploaded file must be an audio file.")

    audio_bytes = audio.file.read()
    if not audio_bytes:
        raise ServiceError(400, "Uploaded audio is empty.")

    settings = get_settings()
    if len(audio_bytes) > settings.voice_audio_max_bytes:
        raise ServiceError(413, "Uploaded audio is too large.")

    return audio_bytes


async def read_audio_upload_async(audio: UploadFile) -> bytes:
    content_type = (audio.content_type or "").lower()
    if not content_type.startswith("audio/"):
        raise ServiceError(400, "Uploaded file must be an audio file.")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise ServiceError(400, "Uploaded audio is empty.")

    settings = get_settings()
    if len(audio_bytes) > settings.voice_audio_max_bytes:
        raise ServiceError(413, "Uploaded audio is too large.")

    return audio_bytes
