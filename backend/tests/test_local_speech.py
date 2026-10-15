import io
import wave
import pytest
from src.integrations.voice.local_speech import synthesize_speech


@pytest.mark.parametrize("language,text", [("en", "Inspect the crop. Officer confirmation is required."), ("am", "ለማሳያ ብቻ።")])
def test_real_local_speech_produces_decodable_pcm(language, text):
    audio = synthesize_speech(text, language_code=language)
    with wave.open(io.BytesIO(audio)) as stream:
        assert stream.getnchannels() == 1
        assert stream.getsampwidth() == 2
        assert stream.getframerate() >= 16000
        samples = stream.readframes(stream.getnframes())
        assert len(samples) > 1000 and len(set(samples)) > 10


def test_local_speech_rejects_unreviewed_languages_and_oversized_text():
    for text, language in [("anything", "xx"), ("x" * 20001, "en"), (" ", "en")]:
        with pytest.raises(ValueError): synthesize_speech(text, language_code=language)
