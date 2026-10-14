from tests.helpers import complete_onboarding, register_user


def test_chat_session_lifecycle_and_message_send(client, monkeypatch):
    user = register_user(client, phone_number="0911000002")
    complete_onboarding(client, user)

    def fake_agent(**kwargs):
        assert kwargs["message"] == "How can I improve maize yield?"
        assert kwargs["image_bytes"] is None
        return "general", "Use clean seed, proper spacing, and timely weeding."

    monkeypatch.setattr("src.services.chat_service.run_farmly_agent", fake_agent)

    create_response = client.post(
        "/api/chat/sessions",
        json={"title": "Maize support"},
        headers=user["headers"],
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    send_response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        data={"message": "How can I improve maize yield?", "language_code": "en"},
        headers=user["headers"],
    )
    assert send_response.status_code == 200
    body = send_response.json()
    assert body["chosen_route"] == "general"
    assert body["user_message"]["sequence_no"] == 1
    assert body["assistant_message"]["sequence_no"] == 2
    assert body["assistant_message"]["content"] == "Use clean seed, proper spacing, and timely weeding."

    messages_response = client.get(
        f"/api/chat/sessions/{session_id}/messages?limit=10&offset=0",
        headers=user["headers"],
    )
    assert messages_response.status_code == 200
    assert len(messages_response.json()) == 2

    empty_message_response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        data={},
        headers=user["headers"],
    )
    assert empty_message_response.status_code == 400

    rename_response = client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"title": "Updated maize support"},
        headers=user["headers"],
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["title"] == "Updated maize support"

    delete_response = client.delete(
        f"/api/chat/sessions/{session_id}",
        headers=user["headers"],
    )
    assert delete_response.status_code == 200

    messages_after_delete = client.get(
        f"/api/chat/sessions/{session_id}/messages",
        headers=user["headers"],
    )
    assert messages_after_delete.status_code == 404
