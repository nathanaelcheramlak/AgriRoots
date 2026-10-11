import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from src.config.settings import get_settings


settings = get_settings()


def generate_otp_code(length: int = 6) -> str:
    if length < 4:
        length = 4
    digits = "".join(str(secrets.randbelow(10)) for _ in range(length))
    return digits


def hash_otp(phone_number: str, otp_code: str) -> str:
    message = f"{phone_number}:{otp_code}".encode("utf-8")
    key = settings.jwt_secret_key.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_otp_hash(phone_number: str, otp_code: str, otp_code_hash: str) -> bool:
    calculated = hash_otp(phone_number, otp_code)
    return hmac.compare_digest(calculated, otp_code_hash)


def otp_expiry_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)

