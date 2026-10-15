"""Legacy direct delivery must not bypass the reviewed advisory workflow."""
import pytest
from src.integrations.voice.google_stt import TranscriptionResult
from tests.helpers import complete_onboarding, register_user


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/recommendations/crops", {}),
    ("post", "/api/recommendations/fertilizer", {"target_crop": "maize"}),
    ("post", "/api/recommendations/weather", {}),
    ("post", "/api/alerts/weather/generate", {}),
    ("get", "/api/alerts", None),
    ("patch", "/api/alerts/example/read", {}),
    ("delete", "/api/alerts/example", None),
    ("post", "/api/voice/synthesize", {"text": "Unapproved farming advice"}),
])
def test_legacy_delivery_requires_review(client, method, path, body):
    user = register_user(client)
    complete_onboarding(client, user)
    response = getattr(client, method)(path, **({"json": body} if body is not None else {}), headers=user["headers"])
    assert response.status_code == 409
    assert "requires officer review" in response.json()["detail"]
    assert getattr(client, method)(path, **({"json": body} if body is not None else {})).status_code == 401


def test_diagnosis_requires_review(client, monkeypatch):
    user = register_user(client)
    def must_not_generate(*args, **kwargs):
        pytest.fail("Unreviewed diagnosis generation was invoked")
    monkeypatch.setattr("src.services.diagnosis_service.run_diagnosis", must_not_generate)
    response = client.post("/api/crop-health/diagnose", files={"image": ("leaf.jpg", b"fake", "image/jpeg")}, headers=user["headers"])
    assert response.status_code == 409


def test_voice_transcription_and_synthesis_are_mocked(client, monkeypatch):
    user = register_user(client, phone_number="0911000006")
    complete_onboarding(client, user)

    monkeypatch.setattr(
        "src.services.voice_service.transcribe_audio",
        lambda audio_bytes, language_code=None, filename=None, content_type=None: TranscriptionResult(
            transcript="I need help with maize",
            confidence=0.91,
            language_code=language_code or "en-US",
        ),
    )
    monkeypatch.setattr("src.services.voice_service.synthesize_speech", lambda text, language_code=None: b"fake-mp3")

    transcribe_response = client.post(
        "/api/voice/transcribe",
        data={"language_code": "en-US"},
        files={"audio": ("voice.webm", b"fake-audio", "audio/webm")},
        headers=user["headers"],
    )
    assert transcribe_response.status_code == 200
    assert transcribe_response.json()["transcript"] == "I need help with maize"

    synthesize_response = client.post(
        "/api/voice/synthesize",
        json={"text": "Hello farmer", "language_code": "en-US"},
        headers=user["headers"],
    )
    assert synthesize_response.status_code == 409
    assert "requires officer review" in synthesize_response.json()["detail"]
