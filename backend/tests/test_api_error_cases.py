from tests.helpers import complete_onboarding, register_user


def test_auth_security_and_onboarding_error_cases(client):
    otp_response = client.post(
        "/api/auth/request-otp",
        json={"full_name": "Test Farmer", "phone_number": "0911000007"},
    )
    assert otp_response.status_code == 200

    invalid_otp_response = client.post(
        "/api/auth/verify-otp",
        json={"phone_number": "0911000007", "otp_code": "000000"},
    )
    assert invalid_otp_response.status_code == 400
    assert invalid_otp_response.json()["detail"] == "Invalid OTP"

    unauthorized_response = client.get("/api/auth/me")
    assert unauthorized_response.status_code == 401

    user = register_user(client, phone_number="0911000008")
    invalid_onboarding = client.post(
        "/api/onboarding/complete",
        json={
            "full_name": "Test Farmer",
            "phone_number": user["phone_number"],
            "location": "9.030000,38.740000",
            "preferred_language": "en",
            "user_type": "beginner",
            "years_experience": 2,
            "main_goal": "increase_yield",
            "crops_grown": [],
        },
        headers=user["headers"],
    )
    assert invalid_onboarding.status_code == 422


def test_recommendations_diagnosis_and_alerts_documented_error_cases(client):
    user = register_user(client, phone_number="0911000009")
    complete_onboarding(client, user)

    invalid_file_response = client.post(
        "/api/crop-health/diagnose",
        files={"image": ("note.txt", b"not-an-image", "text/plain")},
        headers=user["headers"],
    )
    assert invalid_file_response.status_code == 400
    assert invalid_file_response.json()["detail"] == "Uploaded file must be an image."

    read_missing_alert = client.patch(
        "/api/alerts/00000000-0000-0000-0000-000000000000/read",
        headers=user["headers"],
    )
    assert read_missing_alert.status_code == 404
    assert read_missing_alert.json()["detail"] == "Alert not found"

    delete_missing_alert = client.delete(
        "/api/alerts/00000000-0000-0000-0000-000000000000",
        headers=user["headers"],
    )
    assert delete_missing_alert.status_code == 404
    assert delete_missing_alert.json()["detail"] == "Alert not found"


def test_chat_documented_error_cases(client):
    user = register_user(client, phone_number="0911000010")
    complete_onboarding(client, user)

    session_response = client.post(
        "/api/chat/sessions",
        json={"title": "Validation chat"},
        headers=user["headers"],
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["session_id"]

    empty_title_response = client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"title": ""},
        headers=user["headers"],
    )
    assert empty_title_response.status_code == 422

    unauthenticated_messages = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert unauthenticated_messages.status_code == 401
