from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

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
from src.auth.jwt_utils import create_access_token, decode_access_token
from src.auth.otp_utils import generate_otp_code, hash_otp, otp_expiry_time, verify_otp_hash
from src.auth.password import hash_password, verify_password
from src.common.utils.phone import normalize_phone
from src.config.settings import get_settings
from src.db.models.user import OTPVerification, PasswordResetVerification, PhoneChangeVerification, User, UserProfile
from src.integrations.sms.sms_ethiopia import send_sms
from src.repositories.user_repository import UserRepository
from src.repositories.verification_repository import (
    OTPVerificationRepository,
    PasswordResetVerificationRepository,
    PhoneChangeVerificationRepository,
)
from src.services.exceptions import ServiceError


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_user_response(user: User) -> UserResponse:
    onboarding_completed = bool(user.profile and user.profile.onboarding_completed)
    return UserResponse(
        user_id=user.user_id,
        phone_number=user.phone_number,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        onboarding_completed=onboarding_completed,
    )


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.otp = OTPVerificationRepository(db)
        self.phone_changes = PhoneChangeVerificationRepository(db)
        self.password_resets = PasswordResetVerificationRepository(db)

    def request_otp(self, payload: RequestOTPRequest) -> OTPRequestedResponse:
        phone_number = self._normalize_phone(payload.phone_number)
        if self.users.get_by_phone(phone_number):
            raise ServiceError(409, "Phone number already registered. Please login.")

        self.otp.consume_active_for_phone(phone_number)
        otp_code = generate_otp_code()
        verification = OTPVerification(
            phone_number=phone_number,
            full_name=payload.full_name.strip(),
            otp_code_hash=hash_otp(phone_number, otp_code),
            expires_at=otp_expiry_time(),
            max_attempts=self.settings.otp_max_attempts,
        )
        self.otp.add(verification)
        self.db.commit()

        debug_otp = self._send_otp_sms(
            phone_number,
            f"Farmly verification code: {otp_code}. Expires in {self.settings.otp_expire_minutes} minutes.",
            otp_code,
        )
        return OTPRequestedResponse(
            message="OTP sent successfully",
            expires_in_minutes=self.settings.otp_expire_minutes,
            debug_otp=debug_otp,
        )

    def verify_otp(self, payload: VerifyOTPRequest) -> OTPVerifyResponse:
        phone_number = self._normalize_phone(payload.phone_number)
        record = self.otp.get_latest_active(phone_number)
        if not record:
            raise ServiceError(404, "No OTP request found")

        now = datetime.now(timezone.utc)
        if _aware_utc(record.expires_at) < now:
            record.consumed = True
            self.db.commit()
            raise ServiceError(400, "OTP expired")

        if record.verified:
            raise ServiceError(400, "OTP already verified")

        if record.attempts >= record.max_attempts:
            record.consumed = True
            self.db.commit()
            raise ServiceError(429, "Maximum OTP attempts exceeded")

        if not verify_otp_hash(phone_number, payload.otp_code, record.otp_code_hash):
            record.attempts += 1
            self.db.commit()
            raise ServiceError(400, "Invalid OTP")

        record.verified = True
        record.verified_at = now
        self.db.commit()

        return OTPVerifyResponse(
            message="OTP verified successfully",
            setup_token=create_access_token(subject=phone_number, expires_minutes=15),
        )

    def set_password(self, payload: SetPasswordRequest) -> AuthResponse:
        phone_number = self._normalize_phone(payload.phone_number)
        token_payload = decode_access_token(payload.setup_token)
        if token_payload is None or token_payload.get("sub") != phone_number:
            raise ServiceError(401, "Invalid or expired setup token")

        if self.users.get_by_phone(phone_number):
            raise ServiceError(409, "Account already exists. Please login.")

        record = self.otp.get_latest_verified(phone_number)
        if not record:
            raise ServiceError(400, "No verified OTP found for this phone number")

        if _aware_utc(record.expires_at) < datetime.now(timezone.utc):
            record.consumed = True
            self.db.commit()
            raise ServiceError(400, "Verified OTP expired. Request a new OTP.")

        user = User(
            phone_number=phone_number,
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        self.users.add_user(user)
        self.db.flush()

        self.users.add_profile(
            UserProfile(
                user_id=user.user_id,
                full_name=record.full_name,
                phone_number=phone_number,
            )
        )
        record.consumed = True
        self.db.commit()
        self.db.refresh(user)

        return AuthResponse(
            access_token=create_access_token(subject=user.user_id),
            token_type="bearer",
            user=_to_user_response(user),
        )

    def login(self, payload: LoginRequest) -> AuthResponse:
        phone_number = self._normalize_phone(payload.phone_number)
        user = self.users.get_by_phone(phone_number)
        if not user or not verify_password(payload.password, user.password_hash):
            raise ServiceError(401, "Invalid phone number or password")

        if not user.is_active:
            raise ServiceError(403, "User account is inactive")

        return AuthResponse(
            access_token=create_access_token(subject=user.user_id),
            token_type="bearer",
            user=_to_user_response(user),
        )

    def get_me(self, current_user: User) -> UserResponse:
        return _to_user_response(current_user)

    def request_phone_change(self, current_user: User, payload: PhoneChangeRequest) -> PhoneChangeRequestedResponse:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise ServiceError(401, "Current password is incorrect")

        new_phone = self._normalize_phone(payload.new_phone_number)
        if new_phone == current_user.phone_number:
            raise ServiceError(400, "New phone number is the same as current phone number")

        if self.users.get_by_phone(new_phone):
            raise ServiceError(409, "Phone number already in use")

        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self.settings.phone_change_cooldown_seconds
        )
        if self.phone_changes.get_recent_active(current_user.user_id, cooldown_cutoff):
            raise ServiceError(
                429,
                f"Please wait {self.settings.phone_change_cooldown_seconds} seconds before requesting another OTP",
            )

        self.phone_changes.consume_active_for_user(current_user.user_id)
        otp_code = generate_otp_code()
        self.phone_changes.add(
            PhoneChangeVerification(
                user_id=current_user.user_id,
                new_phone_number=new_phone,
                otp_code_hash=hash_otp(new_phone, otp_code),
                expires_at=otp_expiry_time(),
                max_attempts=self.settings.otp_max_attempts,
            )
        )
        self.db.commit()

        debug_otp = self._send_otp_sms(
            new_phone,
            f"Farmly phone change code: {otp_code}. Expires in {self.settings.otp_expire_minutes} minutes.",
            otp_code,
        )
        return PhoneChangeRequestedResponse(
            message="Phone change OTP sent successfully",
            expires_in_minutes=self.settings.otp_expire_minutes,
            debug_otp=debug_otp,
        )

    def confirm_phone_change(self, current_user: User, payload: PhoneChangeConfirmRequest) -> PhoneChangeConfirmResponse:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise ServiceError(401, "Current password is incorrect")

        new_phone = self._normalize_phone(payload.new_phone_number)
        existing_user = self.users.get_by_phone(new_phone)
        if existing_user and existing_user.user_id != current_user.user_id:
            raise ServiceError(409, "Phone number already in use")

        record = self.phone_changes.get_latest_active(current_user.user_id, new_phone)
        if not record:
            raise ServiceError(404, "No phone-change OTP request found")

        now = datetime.now(timezone.utc)
        if _aware_utc(record.expires_at) < now:
            record.consumed = True
            self.db.commit()
            raise ServiceError(400, "OTP expired")

        if record.attempts >= record.max_attempts:
            record.consumed = True
            self.db.commit()
            raise ServiceError(429, "Maximum OTP attempts exceeded")

        if not verify_otp_hash(new_phone, payload.otp_code, record.otp_code_hash):
            record.attempts += 1
            self.db.commit()
            raise ServiceError(400, "Invalid OTP")

        current_user.phone_number = new_phone
        profile = self.users.get_profile(current_user.user_id)
        if profile:
            profile.phone_number = new_phone

        record.verified = True
        record.verified_at = now
        record.consumed = True
        self.db.commit()
        self.db.refresh(current_user)

        return PhoneChangeConfirmResponse(
            message="Phone number changed successfully",
            phone_number=current_user.phone_number,
        )

    def forgot_password(self, payload: ForgotPasswordRequest) -> OTPRequestedResponse:
        phone_number = self._normalize_phone(payload.phone_number)
        user = self.users.get_by_phone(phone_number)
        if not user:
            raise ServiceError(404, "No account found with this phone number")
        if not user.is_active:
            raise ServiceError(403, "User account is inactive")

        self.password_resets.consume_active_for_phone(phone_number)
        otp_code = generate_otp_code()
        self.password_resets.add(
            PasswordResetVerification(
                phone_number=phone_number,
                otp_code_hash=hash_otp(phone_number, otp_code),
                expires_at=otp_expiry_time(),
                max_attempts=self.settings.otp_max_attempts,
            )
        )
        self.db.commit()

        debug_otp = self._send_otp_sms(
            phone_number,
            f"Farmly password reset code: {otp_code}. Expires in {self.settings.otp_expire_minutes} minutes.",
            otp_code,
        )
        return OTPRequestedResponse(
            message="Password reset OTP sent successfully",
            expires_in_minutes=self.settings.otp_expire_minutes,
            debug_otp=debug_otp,
        )

    def forgot_password_verify(self, payload: ForgotPasswordVerifyRequest) -> OTPVerifyResponse:
        phone_number = self._normalize_phone(payload.phone_number)
        record = self.password_resets.get_latest_active(phone_number)
        if not record:
            raise ServiceError(404, "No password reset OTP request found")

        now = datetime.now(timezone.utc)
        if _aware_utc(record.expires_at) < now:
            record.consumed = True
            self.db.commit()
            raise ServiceError(400, "OTP expired")

        if record.attempts >= record.max_attempts:
            record.consumed = True
            self.db.commit()
            raise ServiceError(429, "Maximum OTP attempts exceeded")

        if not verify_otp_hash(phone_number, payload.otp_code, record.otp_code_hash):
            record.attempts += 1
            self.db.commit()
            raise ServiceError(400, "Invalid OTP")

        record.verified = True
        record.verified_at = now
        self.db.commit()

        return OTPVerifyResponse(
            message="OTP verified. You may now reset your password.",
            setup_token=create_access_token(subject=phone_number, expires_minutes=15),
        )

    def reset_password(self, payload: ResetPasswordRequest) -> ResetPasswordResponse:
        if payload.new_password != payload.confirm_password:
            raise ServiceError(400, "Passwords do not match")

        phone_number = self._normalize_phone(payload.phone_number)
        token_payload = decode_access_token(payload.reset_token)
        if token_payload is None or token_payload.get("sub") != phone_number:
            raise ServiceError(401, "Invalid or expired reset token")

        record = self.password_resets.get_latest_verified(phone_number)
        if not record:
            raise ServiceError(400, "No verified OTP found. Please restart the reset process.")

        if _aware_utc(record.expires_at) < datetime.now(timezone.utc):
            record.consumed = True
            self.db.commit()
            raise ServiceError(400, "Reset session expired. Please restart.")

        user = self.users.get_by_phone(phone_number)
        if not user:
            raise ServiceError(404, "User not found")

        user.password_hash = hash_password(payload.new_password)
        record.consumed = True
        self.db.commit()

        return ResetPasswordResponse(message="Password reset successfully. You can now sign in.")

    def _normalize_phone(self, value: str) -> str:
        try:
            return normalize_phone(value)
        except ValueError as exc:
            raise ServiceError(400, str(exc)) from exc

    def _send_otp_sms(self, phone_number: str, sms_text: str, otp_code: str) -> str | None:
        debug_otp: str | None = None
        try:
            send_sms(phone_number, sms_text)
        except Exception as exc:
            if self.settings.debug:
                debug_otp = otp_code
            else:
                raise ServiceError(502, f"Failed to send OTP SMS: {exc}") from exc

        if self.settings.debug and debug_otp is None:
            debug_otp = otp_code
        return debug_otp
