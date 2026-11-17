"""Connection-owned authenticated encryption. Secret values never leave this internal module."""

import json
import re
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from src.config.settings import get_settings
from src.integrations.contracts import ConnectorError

SENSITIVE = re.compile(r"key|token|secret|password|authorization|cookie|credential|email|phone", re.I)


def cipher():
    settings = get_settings()
    keys = [settings.secret_encryption_key, *settings.secret_previous_encryption_keys]
    try:
        if not keys[0]:
            raise ValueError()
        return MultiFernet([Fernet(key.encode()) for key in keys if key])
    except (ValueError, TypeError):
        raise ConnectorError("AUTH_REQUIRED", "Configure a valid SECRET_ENCRYPTION_KEY outside the database") from None


def encrypt(value):
    if len(json.dumps(value).encode()) > 16384:
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Credential exceeds 16 KiB")
    return cipher().encrypt(json.dumps(value).encode()).decode()


def decrypt(record, office_id, connection_id):
    if record.office_id != office_id or record.connection_id != connection_id:
        raise ConnectorError("POLICY_DENIED", "Credential ownership mismatch")
    try:
        return json.loads(cipher().decrypt(record.ciphertext.encode()))
    except (InvalidToken, ValueError):
        raise ConnectorError("AUTH_INVALID", "Credential cannot be decrypted with the configured keys") from None


def redact(value, secret_values=()):
    if isinstance(value, dict):
        usage_counts = {"input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens"}
        return {
            str(k): v
            if k in usage_counts and isinstance(v, int) and not isinstance(v, bool) and v >= 0
            else "[REDACTED]"
            if SENSITIVE.search(str(k))
            else redact(v, secret_values)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, secret_values) for v in value]
    if isinstance(value, str):
        for secret in secret_values:
            if isinstance(secret, str) and secret:
                value = value.replace(secret, "[REDACTED]")
        settings = get_settings()
        for secret in (
            settings.gemini_api_key,
            settings.jwt_secret_key,
            settings.isda_password,
            settings.kindwise_crop_health_api_key,
            settings.secret_encryption_key,
        ):
            if secret and len(secret) >= 6:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", value)
        return value
    return value


def reject_platform_credentials(value):
    if isinstance(value, dict):
        for item in value.values():
            reject_platform_credentials(item)
        return
    if not isinstance(value, str):
        return
    settings = get_settings()
    if value in {
        secret
        for secret in (settings.gemini_api_key, settings.jwt_secret_key, settings.secret_encryption_key)
        if secret
    }:
        raise ConnectorError("POLICY_DENIED", "Platform/model credentials cannot be attached to connected providers")
    if value.count(".") == 2:
        import jwt

        try:
            jwt.decode(
                value,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False, "verify_aud": False},
            )
        except jwt.PyJWTError:
            return
        raise ConnectorError("POLICY_DENIED", "AgriLo login tokens cannot be forwarded to connected providers")
