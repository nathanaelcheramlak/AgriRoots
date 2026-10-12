from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, Query, status
from sqlalchemy.orm import Session

from src.api.errors import raise_http_error
from src.api.schemas.chat import (
    ChatDeleteResponse,
    ChatMessageResponse,
    ChatSendResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.services.chat_service import ChatService
from src.services.exceptions import ServiceError


router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _service(db: Session) -> ChatService:
    return ChatService(db)


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    try:
        return _service(db).create_session(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_my_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionResponse]:
    try:
        return _service(db).list_sessions(current_user, limit, offset)
    except ServiceError as exc:
        raise_http_error(exc)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessageResponse]:
    try:
        return _service(db).get_session_messages(current_user, session_id, limit, offset)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/sessions/{session_id}/messages", response_model=ChatSendResponse)
def send_message(
    session_id: UUID,
    message: str | None = Form(default=None),
    language_code: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSendResponse:
    try:
        return _service(db).send_message(
            current_user=current_user,
            session_id=session_id,
            message=message,
            language_code=language_code,
            image=image,
            audio=audio,
        )
    except ServiceError as exc:
        raise_http_error(exc)


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def rename_session(
    session_id: UUID,
    payload: ChatSessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    try:
        return _service(db).rename_session(current_user, session_id, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.delete("/sessions/{session_id}", response_model=ChatDeleteResponse)
def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatDeleteResponse:
    try:
        return _service(db).delete_session(current_user, session_id)
    except ServiceError as exc:
        raise_http_error(exc)
