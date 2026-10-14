from tests.helpers import DEFAULT_PASSWORD, complete_onboarding, register_user


def test_registration_login_onboarding_and_profile_update(client):
    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    user = register_user(client)

    me_response = client.get("/api/auth/me", headers=user["headers"])
    assert me_response.status_code == 200
    assert me_response.json()["onboarding_completed"] is False

    duplicate_response = client.post(
        "/api/auth/request-otp",
        json={"full_name": "Duplicate User", "phone_number": user["raw_phone_number"]},
    )
    assert duplicate_response.status_code == 409

    profile = complete_onboarding(client, user)
    assert profile["onboarding_completed"] is True
    assert profile["crops_grown"] == ["maize", "teff"]

    me_after_onboarding = client.get("/api/auth/me", headers=user["headers"])
    assert me_after_onboarding.status_code == 200
    assert me_after_onboarding.json()["onboarding_completed"] is True

    update_response = client.patch(
        "/api/users/me/profile",
        json={"location": "8.980000,38.760000", "crops_grown": ["wheat", "teff", "wheat"]},
        headers=user["headers"],
    )
    assert update_response.status_code == 200
    assert update_response.json()["location"] == "8.980000,38.760000"
    assert update_response.json()["crops_grown"] == ["wheat", "teff"]

    direct_phone_update = client.patch(
        "/api/users/me/profile",
        json={"phone_number": "0911223344"},
        headers=user["headers"],
    )
    assert direct_phone_update.status_code == 400

    login_response = client.post(
        "/api/auth/login",
        json={"phone_number": user["raw_phone_number"], "password": DEFAULT_PASSWORD},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_password_reset_phone_change_and_account_delete(client):
    user = register_user(client, phone_number="0911000001")
    complete_onboarding(client, user)

    forgot_response = client.post(
        "/api/auth/forgot-password",
        json={"phone_number": user["raw_phone_number"]},
    )
    assert forgot_response.status_code == 200
    reset_otp = forgot_response.json()["debug_otp"]
    assert reset_otp

    verify_reset = client.post(
        "/api/auth/forgot-password/verify",
        json={"phone_number": user["raw_phone_number"], "otp_code": reset_otp},
    )
    assert verify_reset.status_code == 200
    reset_token = verify_reset.json()["setup_token"]

    new_password = "NewPass123!"
    reset_response = client.post(
        "/api/auth/reset-password",
        json={
            "phone_number": user["raw_phone_number"],
            "reset_token": reset_token,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert reset_response.status_code == 200

    old_login = client.post(
        "/api/auth/login",
        json={"phone_number": user["raw_phone_number"], "password": DEFAULT_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"phone_number": user["raw_phone_number"], "password": new_password},
    )
    assert new_login.status_code == 200
    headers = {"Authorization": f"Bearer {new_login.json()['access_token']}"}

    phone_change_response = client.post(
        "/api/auth/users/me/phone-change/request",
        json={"current_password": new_password, "new_phone_number": "0911777888"},
        headers=headers,
    )
    assert phone_change_response.status_code == 200
    phone_change_otp = phone_change_response.json()["debug_otp"]
    assert phone_change_otp

    confirm_phone = client.post(
        "/api/auth/users/me/phone-change/confirm",
        json={
            "current_password": new_password,
            "new_phone_number": "0911777888",
            "otp_code": phone_change_otp,
        },
        headers=headers,
    )
    assert confirm_phone.status_code == 200
    assert confirm_phone.json()["phone_number"] == "251911777888"

    create_chat = client.post(
        "/api/chat/sessions",
        json={"title": "Before delete"},
        headers=headers,
    )
    assert create_chat.status_code == 201

    delete_response = client.request(
        "DELETE",
        "/api/users/me",
        json={"current_password": new_password},
        headers=headers,
    )
    assert delete_response.status_code == 200

    me_after_delete = client.get("/api/auth/me", headers=headers)
    assert me_after_delete.status_code == 401

    login_after_delete = client.post(
        "/api/auth/login",
        json={"phone_number": "0911777888", "password": new_password},
    )
    assert login_after_delete.status_code == 401
