"""Offline eSpeak NG synthesis in a separate bounded process; plain reviewed text only."""
import json
import subprocess
import sys
from pathlib import Path
from src.config.settings import get_settings


def synthesize_speech(text, language_code=None):
    if get_settings().advisory_audio_provider == "cloud":
        from src.integrations.voice.google_tts import synthesize_speech as cloud_speech
        return cloud_speech(text, language_code=language_code)
    if not text.strip() or len(text) > 20000 or language_code not in ("en", "am"):
        raise ValueError("Unsupported speech language or text length")
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("speech_process.py"))],
        input=json.dumps({"text": text, "language": language_code}).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=True)
    if not result.stdout.startswith(b"RIFF") or len(result.stdout) > 32_000_000:
        raise RuntimeError("Local speech returned an invalid WAV")
    return result.stdout
