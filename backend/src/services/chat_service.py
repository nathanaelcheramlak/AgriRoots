from datetime import datetime, timezone
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.agent.orchestrator import run_farmly_agent
from src.api.schemas.chat import (
    ChatDeleteResponse,
    ChatMessageResponse,
    ChatSendResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from src.db.models.chat import ChatMessage, ChatSession
from src.db.models.user import User
from src.integrations.voice.google_stt import transcribe_audio
from src.integrations.voice.hasab_client import translate_text_with_hasab
from src.repositories.chat_repository import ChatRepository
from src.repositories.user_repository import UserRepository
from src.services.exceptions import ServiceError
from src.services.language import language_name, language_to_bcp47, normalize_app_language
from src.services.upload_service import read_audio_upload, read_image_upload


def to_session_response(session: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def to_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        message_id=message.message_id,
        session_id=message.session_id,
        sender=message.sender,
        content=message.content,
        content_type=message.content_type or "text",
        message_content_english=message.message_content_english,
        media_url=message.media_url,
        language_used=message.language_used,
        sequence_no=message.sequence_no,
        created_at=message.created_at,
    )


def _translate_amharic_to_english(text: str) -> str:
    return translate_text_with_hasab(
        text,
        source_language="am-ET",
        target_language="en-US",
    )


def _translate_english_to_amharic(text: str) -> str:
    return translate_text_with_hasab(
        text,
        source_language="en-US",
        target_language="am-ET",
    )


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.chats = ChatRepository(db)
        self.users = UserRepository(db)

    def create_session(self, current_user: User, payload: ChatSessionCreateRequest) -> ChatSessionResponse:
        title = payload.title.strip() if payload.title else "New chat"
        session = self.chats.create_session(current_user.user_id, title)
        self.db.commit()
        self.db.refresh(session)
        return to_session_response(session)

    def list_sessions(self, current_user: User, limit: int, offset: int) -> list[ChatSessionResponse]:
        sessions = self.chats.list_sessions(current_user.user_id, limit, offset)
        return [to_session_response(session) for session in sessions]

    def get_session_messages(
        self,
        current_user: User,
        session_id: UUID,
        limit: int,
        offset: int,
    ) -> list[ChatMessageResponse]:
        session = self._require_owned_session(current_user, session_id)
        messages = self.chats.list_messages(session.session_id, limit, offset)
        return [to_message_response(message) for message in messages]

    def send_message(
        self,
        current_user: User,
        session_id: UUID,
        message: str | None,
        language_code: str | None,
        image: UploadFile | None,
        audio: UploadFile | None,
    ) -> ChatSendResponse:
        session = self._require_owned_session(current_user, session_id)
        text = (message or "").strip()
        if image is None and audio is None and not text:
            raise ServiceError(400, "Provide message, image, or audio")

        image_bytes: bytes | None = None
        image_mime_type: str | None = None
        if image is not None:
            image_bytes, image_mime_type = read_image_upload(image)

        profile = self.users.get_profile(current_user.user_id)
        effective_language = language_code or (profile.preferred_language if profile else None)
        normalized_language = normalize_app_language(effective_language, default="en")
        bcp47_language = language_to_bcp47(effective_language)
        language_used = language_name(normalized_language)

        transcript: str | None = None
        user_content_english: str | None = None
        media_url: str | None = None
        if audio is not None:
            audio_bytes = read_audio_upload(audio)
            try:
                transcription = transcribe_audio(
                    audio_bytes,
                    language_code=bcp47_language,
                    filename=audio.filename or "voice-message.webm",
                    content_type=audio.content_type or "audio/webm",
                    translate_to_english=normalized_language == "am",
                )
            except Exception as exc:
                raise ServiceError(502, f"Voice transcription failed: {exc}") from exc

            transcript = transcription.transcript.strip()
            user_content_english = transcription.translation
            media_url = transcription.media_url
            if not transcript:
                raise ServiceError(400, "Could not transcribe uploaded audio.")
            text = transcript

        content_type = "audio" if audio is not None else "image" if image is not None else "text"
        user_content = text if text else "[image uploaded for diagnosis]"
        if not user_content_english and normalized_language == "en":
            user_content_english = user_content
        elif not user_content_english and normalized_language == "am" and text:
            try:
                user_content_english = _translate_amharic_to_english(user_content)
            except Exception as exc:
                raise ServiceError(502, f"Amharic-to-English translation failed: {exc}") from exc

        chosen_route, assistant_text_english = run_farmly_agent(
            db=self.db,
            session_id=session.session_id,
            profile=profile,
            message=user_content_english or user_content,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
            language_code=bcp47_language,
        )
        assistant_text = assistant_text_english
        if normalized_language == "am":
            try:
                assistant_text = _translate_english_to_amharic(assistant_text_english)
            except Exception as exc:
                raise ServiceError(502, f"English-to-Amharic translation failed: {exc}") from exc

        next_seq = self.chats.next_sequence_no(session.session_id)
        user_message = ChatMessage(
            session_id=session.session_id,
            sender="user",
            content=user_content,
            content_type=content_type,
            message_content_english=user_content_english,
            media_url=media_url,
            language_used=language_used,
            sequence_no=next_seq,
        )
        assistant_message = ChatMessage(
            session_id=session.session_id,
            sender="assistant",
            content=assistant_text,
            content_type="text",
            message_content_english=assistant_text_english,
            media_url=None,
            language_used=language_used,
            sequence_no=next_seq + 1,
        )
        self.chats.add_message(user_message)
        self.chats.add_message(assistant_message)
        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)

        return ChatSendResponse(
            session_id=session.session_id,
            user_message=to_message_response(user_message),
            assistant_message=to_message_response(assistant_message),
            chosen_route=chosen_route,
            transcript=transcript,
        )

    def rename_session(
        self,
        current_user: User,
        session_id: UUID,
        payload: ChatSessionUpdateRequest,
    ) -> ChatSessionResponse:
        session = self._require_owned_session(current_user, session_id)
        title = payload.title.strip()
        if not title:
            raise ServiceError(400, "Session title cannot be empty")

        session.title = title
        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return to_session_response(session)

    def delete_session(self, current_user: User, session_id: UUID) -> ChatDeleteResponse:
        session = self._require_owned_session(current_user, session_id)
        deleted_id = UUID(session.session_id)
        self.chats.delete_session(session)
        self.db.commit()
        return ChatDeleteResponse(
            message="Chat session deleted successfully",
            session_id=deleted_id,
        )

    def _require_owned_session(self, current_user: User, session_id: UUID) -> ChatSession:
        session = self.chats.get_owned_session(session_id, current_user.user_id)
        if not session:
            raise ServiceError(404, "Chat session not found")
        return session
