from src.config.settings import get_settings
from src.integrations.voice.google_credentials import get_google_credentials
from src.integrations.voice.hasab_client import synthesize_with_hasab
from src.services.language import is_amharic


def _load_texttospeech():
    from google.cloud import texttospeech

    return texttospeech


def synthesize_speech(text: str, language_code: str | None = None) -> bytes:
    settings = get_settings()
    if is_amharic(language_code or settings.google_tts_language_code):
        return synthesize_with_hasab(text, language_code=language_code)

    texttospeech = _load_texttospeech()
    client = texttospeech.TextToSpeechClient(credentials=get_google_credentials())

    voice_kwargs = {"language_code": settings.google_tts_language_code}
    if settings.google_tts_voice_name:
        voice_kwargs["name"] = settings.google_tts_voice_name

    encoding_name = settings.google_tts_audio_encoding.upper()
    try:
        audio_encoding = getattr(texttospeech.AudioEncoding, encoding_name)
    except AttributeError as exc:
        raise RuntimeError(f"Unsupported Google TTS audio encoding: {encoding_name}") from exc

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(**voice_kwargs),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=audio_encoding,
            speaking_rate=settings.google_tts_speaking_rate,
        ),
    )
    return bytes(response.audio_content)
