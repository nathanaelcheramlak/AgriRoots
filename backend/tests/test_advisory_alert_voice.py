from src.api.schemas.diagnosis import CropCandidate, DiagnosisResponse, DiseaseCandidate
from src.integrations.voice.google_stt import TranscriptionResult
from tests.helpers import complete_onboarding, register_user


def test_recommendation_endpoints_use_authenticated_profile(client, monkeypatch):
    user = register_user(client, phone_number="0911000003")
    complete_onboarding(client, user)

    common_result = {
        "recommendation_text": "Plant maize after checking rainfall and use good spacing.",
        "location_used": "9.030000,38.740000",
        "crops_used": ["maize", "teff"],
        "soil_summary": {"source": "mock"},
        "weather_summary": {"source": "mock"},
        "used_fallback": False,
    }
    weather_result = {
        "recommendation_text": "Rain may come soon. Prepare drainage and avoid spraying before rain.",
        "location_used": "9.030000,38.740000",
        "raw_weather": {"forecast_days": [{"date": "2026-06-03", "rain_mm": 5}]},
        "used_fallback": False,
    }

    monkeypatch.setattr("src.services.recommendation_service.run_crop_recommendation", lambda profile: common_result)
    monkeypatch.setattr(
        "src.services.recommendation_service.run_fertilizer_recommendation",
        lambda profile, target_crop=None: {**common_result, "crops_used": [target_crop or "maize"]},
    )
    monkeypatch.setattr("src.services.recommendation_service.run_weather_recommendation", lambda profile: weather_result)

    crop_response = client.post("/api/recommendations/crops", headers=user["headers"])
    assert crop_response.status_code == 200
    assert crop_response.json()["recommendation_text"].startswith("Plant maize")

    fertilizer_response = client.post(
        "/api/recommendations/fertilizer",
        json={"target_crop": "maize"},
        headers=user["headers"],
    )
    assert fertilizer_response.status_code == 200
    assert fertilizer_response.json()["crops_used"] == ["maize"]

    weather_response = client.post("/api/recommendations/weather", headers=user["headers"])
    assert weather_response.status_code == 200
    assert weather_response.json()["raw_weather"]["forecast_days"][0]["rain_mm"] == 5


def test_diagnosis_endpoint_accepts_image_and_returns_mocked_result(client, monkeypatch):
    user = register_user(client, phone_number="0911000004")
    complete_onboarding(client, user)

    def fake_diagnosis(profile, image_bytes, image_mime_type):
        assert image_bytes == b"fake-image"
        assert image_mime_type == "image/jpeg"
        return DiagnosisResponse(
            is_plant=True,
            top_crop=CropCandidate(name="maize", scientific_name="Zea mays", probability=0.95),
            top_disease=DiseaseCandidate(name="rust", scientific_name="Puccinia", probability=0.88),
            crops=[CropCandidate(name="maize", scientific_name="Zea mays", probability=0.95)],
            diseases=[DiseaseCandidate(name="rust", scientific_name="Puccinia", probability=0.88)],
            advice_text="Remove badly infected leaves and monitor the crop closely.",
            used_fallback=False,
            provider="mock-provider",
            confidence_status="confident",
            needs_retake=False,
        )

    monkeypatch.setattr("src.services.diagnosis_service.run_diagnosis", fake_diagnosis)

    response = client.post(
        "/api/crop-health/diagnose",
        files={"image": ("leaf.jpg", b"fake-image", "image/jpeg")},
        headers=user["headers"],
    )
    assert response.status_code == 200
    assert response.json()["is_plant"] is True
    assert response.json()["top_disease"]["name"] == "rust"
    assert response.json()["provider"] == "mock-provider"


def test_alert_generation_read_and_delete(client, monkeypatch):
    user = register_user(client, phone_number="0911000005")
    complete_onboarding(client, user)

    def fake_alerts(profile, language_code=None):
        return (
            "9.030000,38.740000",
            {"forecast_days": [{"date": "2026-06-03", "rain_mm": 18}]},
            [
                {
                    "alert_type": "heavy_rain",
                    "severity": "high",
                    "title": "Heavy rain expected",
                    "message": "Heavy rain may affect your maize field.",
                    "action_text": "Clear drainage paths before the rain.",
                }
            ],
        )

    monkeypatch.setattr("src.services.alert_app_service.build_weather_alerts", fake_alerts)

    generate_response = client.post(
        "/api/alerts/weather/generate?language_code=en",
        headers=user["headers"],
    )
    assert generate_response.status_code == 201
    generated = generate_response.json()
    assert generated["generated_count"] == 1
    alert_id = generated["alerts"][0]["alert_id"]

    list_response = client.get("/api/alerts", headers=user["headers"])
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["is_read"] is False

    read_response = client.patch(f"/api/alerts/{alert_id}/read", headers=user["headers"])
    assert read_response.status_code == 200
    assert read_response.json()["alert"]["is_read"] is True

    delete_response = client.delete(f"/api/alerts/{alert_id}", headers=user["headers"])
    assert delete_response.status_code == 200

    empty_list_response = client.get("/api/alerts", headers=user["headers"])
    assert empty_list_response.status_code == 200
    assert empty_list_response.json() == []


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
    assert synthesize_response.status_code == 200
    assert synthesize_response.content == b"fake-mp3"
    assert synthesize_response.headers["content-type"] == "audio/mpeg"
