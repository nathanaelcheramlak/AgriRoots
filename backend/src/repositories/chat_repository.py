from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.chat import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: str, title: str) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        return session

    def list_sessions(self, user_id: str, limit: int, offset: int) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_owned_session(self, session_id: UUID | str, user_id: str) -> ChatSession | None:
        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.session_id == str(session_id),
                ChatSession.user_id == user_id,
            )
            .first()
        )

    def list_messages(self, session_id: str, limit: int, offset: int) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_no.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def next_sequence_no(self, session_id: str) -> int:
        last_seq = (
            self.db.query(ChatMessage.sequence_no)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_no.desc())
            .first()
        )
        return (last_seq[0] if last_seq else 0) + 1

    def add_message(self, message: ChatMessage) -> ChatMessage:
        self.db.add(message)
        return message

    def delete_session(self, session: ChatSession) -> None:
        self.db.delete(session)
