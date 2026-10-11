from datetime import datetime

from pydantic import BaseModel, Field


class RequestOTPRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone_number: str = Field(min_length=9, max_length=20)


class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=20)
    otp_code: str = Field(min_length=4, max_length=10)


class SetPasswordRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=20)
    setup_token: str = Field(min_length=20)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=20)
    password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
    user_id: str
    phone_number: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    onboarding_completed: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(TokenResponse):
    user: UserResponse


class OTPRequestedResponse(BaseModel):
    status: str = "success"
    message: str
    expires_in_minutes: int
    debug_otp: str | None = None


class OTPVerifyResponse(BaseModel):
    status: str = "success"
    message: str
    setup_token: str


class PhoneChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_phone_number: str = Field(min_length=9, max_length=20)


class PhoneChangeConfirmRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_phone_number: str = Field(min_length=9, max_length=20)
    otp_code: str = Field(min_length=4, max_length=10)


class PhoneChangeRequestedResponse(BaseModel):
    status: str = "success"
    message: str
    expires_in_minutes: int
    debug_otp: str | None = None


class PhoneChangeConfirmResponse(BaseModel):
    status: str = "success"
    message: str
    phone_number: str


class ForgotPasswordRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=20)


class ForgotPasswordVerifyRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=20)
    otp_code: str = Field(min_length=4, max_length=10)


class ResetPasswordRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=20)
    reset_token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)


class ResetPasswordResponse(BaseModel):
    status: str = "success"
    message: str
