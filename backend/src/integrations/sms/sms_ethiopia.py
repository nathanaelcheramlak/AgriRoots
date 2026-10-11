import httpx

from src.config.settings import get_settings


settings = get_settings()


def send_sms(msisdn: str, text: str) -> dict:
    if not settings.sms_ethiopia_api_key:
        raise RuntimeError("SMS Ethiopia API key is not configured")

    url = f"{settings.sms_ethiopia_base_url.rstrip('/')}/sms/send"
    headers = {
        "KEY": settings.sms_ethiopia_api_key,
        "Content-Type": "application/json",
    }
    payload = {"msisdn": msisdn, "text": text}

    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(
            f"SMS provider error ({response.status_code}): {response.text}"
        )

    try:
        return response.json()
    except Exception:
        return {"status": "unknown", "message": response.text}

