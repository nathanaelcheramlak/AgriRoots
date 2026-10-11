from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.errors import raise_http_error
from src.api.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordVerifyRequest,
    LoginRequest,
    OTPRequestedResponse,
    OTPVerifyResponse,
    PhoneChangeConfirmRequest,
    PhoneChangeConfirmResponse,
    PhoneChangeRequest,
    PhoneChangeRequestedResponse,
    RequestOTPRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SetPasswordRequest,
    UserResponse,
    VerifyOTPRequest,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User
from src.db.session import get_db
from src.services.auth_service import AuthService
from src.services.exceptions import ServiceError


router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _service(db: Session) -> AuthService:
    return AuthService(db)


@router.post("/request-otp", response_model=OTPRequestedResponse)
def request_otp(payload: RequestOTPRequest, db: Session = Depends(get_db)) -> OTPRequestedResponse:
    try:
        return _service(db).request_otp(payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/verify-otp", response_model=OTPVerifyResponse)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)) -> OTPVerifyResponse:
    try:
        return _service(db).verify_otp(payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/set-password", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return _service(db).set_password(payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return _service(db).login(payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserResponse:
    try:
        return _service(db).get_me(current_user)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/users/me/phone-change/request", response_model=PhoneChangeRequestedResponse)
def request_phone_change(
    payload: PhoneChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PhoneChangeRequestedResponse:
    try:
        return _service(db).request_phone_change(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/users/me/phone-change/confirm", response_model=PhoneChangeConfirmResponse)
def confirm_phone_change(
    payload: PhoneChangeConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PhoneChangeConfirmResponse:
    try:
        return _service(db).confirm_phone_change(current_user, payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/forgot-password", response_model=OTPRequestedResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> OTPRequestedResponse:
    try:
        return _service(db).forgot_password(payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/forgot-password/verify", response_model=OTPVerifyResponse)
def forgot_password_verify(
    payload: ForgotPasswordVerifyRequest,
    db: Session = Depends(get_db),
) -> OTPVerifyResponse:
    try:
        return _service(db).forgot_password_verify(payload)
    except ServiceError as exc:
        raise_http_error(exc)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> ResetPasswordResponse:
    try:
        return _service(db).reset_password(payload)
    except ServiceError as exc:
        raise_http_error(exc)
