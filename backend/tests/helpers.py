DEFAULT_PASSWORD = "TestPass123!"


def register_user(
    client,
    phone_number: str = "0911000000",
    full_name: str = "Dagemawi Bekele",
    password: str = DEFAULT_PASSWORD,
) -> dict:
    otp_response = client.post(
        "/api/auth/request-otp",
        json={"full_name": full_name, "phone_number": phone_number},
    )
    assert otp_response.status_code == 200
    debug_otp = otp_response.json()["debug_otp"]
    assert debug_otp

    verify_response = client.post(
        "/api/auth/verify-otp",
        json={"phone_number": phone_number, "otp_code": debug_otp},
    )
    assert verify_response.status_code == 200
    setup_token = verify_response.json()["setup_token"]

    password_response = client.post(
        "/api/auth/set-password",
        json={
            "phone_number": phone_number,
            "setup_token": setup_token,
            "password": password,
        },
    )
    assert password_response.status_code == 201
    body = password_response.json()
    token = body["access_token"]

    return {
        "raw_phone_number": phone_number,
        "phone_number": body["user"]["phone_number"],
        "password": password,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user": body["user"],
    }


def complete_onboarding(
    client,
    user: dict,
    crops: list[str] | None = None,
    language: str = "en",
) -> dict:
    response = client.post(
        "/api/onboarding/complete",
        json={
            "full_name": "Dagemawi Bekele",
            "phone_number": user["phone_number"],
            "location": "9.030000,38.740000",
            "preferred_language": language,
            "user_type": "beginner",
            "years_experience": 2,
            "main_goal": "increase_yield",
            "crops_grown": crops or ["maize", "teff", "maize"],
        },
        headers=user["headers"],
    )
    assert response.status_code == 200
    return response.json()
