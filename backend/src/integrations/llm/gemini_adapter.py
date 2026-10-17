import base64
import json
import logging
import re
from time import sleep
from time import perf_counter

import httpx

from src.config.settings import get_settings
from src.agent.prompts import (build_chat_system_prompt, build_intent_prompt,
                              build_crop_image_prompt)


settings = get_settings()
logger = logging.getLogger("uvicorn.error")


def _post_gemini(url: str, payload: dict, operation: str) -> httpx.Response:
    max_attempts = 3
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=float(settings.gemini_timeout_seconds)) as client:
                return client.post(
                    url,
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            logger.warning(
                "Gemini:%s transport_error attempt=%s max_attempts=%s error=%s",
                operation,
                attempt,
                max_attempts,
                exc.__class__.__name__,
            )
            if attempt < max_attempts:
                sleep(0.4 * attempt)

    raise RuntimeError(f"Gemini {operation} request failed after retries: {last_error}") from last_error


def _build_contents(recent_messages: list[dict[str, str]], latest_user_message: str) -> list[dict]:
    contents: list[dict] = []
    for msg in recent_messages:
        role = "user" if msg.get("sender") == "user" else "model"
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})

    contents.append({"role": "user", "parts": [{"text": latest_user_message.strip()}]})
    return contents


def _extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise RuntimeError(f"Gemini returned non-JSON response: {text[:300]}")
        return json.loads(match.group(0))


def generate_reply(
    *,
    latest_user_message: str,
    recent_messages: list[dict[str, str]],
    profile_context: dict[str, str],
) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not settings.gemini_model:
        raise RuntimeError("GEMINI_MODEL is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": build_chat_system_prompt(profile_context)}],
        },
        "contents": _build_contents(recent_messages, latest_user_message),
        "generationConfig": {
            "temperature": 0.4,
        },
    }

    started_at = perf_counter()
    logger.info(
        "Gemini:generate_reply request model=%s message_chars=%s recent_messages=%s profile_fields=%s",
        settings.gemini_model,
        len(latest_user_message or ""),
        len(recent_messages),
        sum(1 for value in profile_context.values() if value),
    )
    response = _post_gemini(url, payload, "generate_reply")

    if response.status_code >= 400:
        logger.warning(
            "Gemini:generate_reply error status=%s elapsed_ms=%s",
            response.status_code,
            round((perf_counter() - started_at) * 1000),
        )
        raise RuntimeError(f"Gemini provider error ({response.status_code}): {response.text}")

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join([(p.get("text") or "") for p in parts]).strip()
    if not text:
        raise RuntimeError("Gemini returned empty response")

    logger.info(
        "Gemini:generate_reply response status=%s response_chars=%s elapsed_ms=%s",
        response.status_code,
        len(text),
        round((perf_counter() - started_at) * 1000),
    )
    return text


def classify_chat_intent(
    *,
    latest_user_message: str,
    has_image: bool,
    recent_messages: list[dict[str, str]],
    profile_context: dict[str, str],
    tool_catalog: list[dict[str, str]],
) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not settings.gemini_model:
        raise RuntimeError("GEMINI_MODEL is not configured")

    prompt = build_intent_prompt(
        latest_user_message, has_image, recent_messages, profile_context, tool_catalog,
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
        },
    }

    started_at = perf_counter()
    logger.info(
        "Gemini:intent_router request model=%s has_image=%s message_chars=%s "
        "recent_messages=%s tool_count=%s",
        settings.gemini_model,
        has_image,
        len(latest_user_message or ""),
        len(recent_messages),
        len(tool_catalog),
    )
    response = _post_gemini(url, payload, "intent_router")

    if response.status_code >= 400:
        logger.warning(
            "Gemini:intent_router error status=%s elapsed_ms=%s",
            response.status_code,
            round((perf_counter() - started_at) * 1000),
        )
        raise RuntimeError(f"Gemini intent router error ({response.status_code}): {response.text}")

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini intent router returned no candidates")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join([(part.get("text") or "") for part in parts]).strip()
    if not text:
        raise RuntimeError("Gemini intent router returned empty response")

    parsed = _extract_json_object(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini intent router returned JSON that is not an object")
    logger.info(
        "Gemini:intent_router response status=%s intent=%s confidence=%s elapsed_ms=%s",
        response.status_code,
        parsed.get("intent"),
        parsed.get("confidence"),
        round((perf_counter() - started_at) * 1000),
    )
    return parsed


def classify_crop_image(
    *,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    supported_crops: list[str],
) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not settings.gemini_model:
        raise RuntimeError("GEMINI_MODEL is not configured")

    prompt = build_crop_image_prompt(supported_crops)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
        },
    }

    started_at = perf_counter()
    logger.info(
        "Gemini:crop_image_triage request model=%s mime_type=%s image_bytes=%s supported_crops=%s",
        settings.gemini_model,
        mime_type,
        len(image_bytes),
        len(supported_crops),
    )
    response = _post_gemini(url, payload, "crop_image_triage")

    if response.status_code >= 400:
        logger.warning(
            "Gemini:crop_image_triage error status=%s elapsed_ms=%s",
            response.status_code,
            round((perf_counter() - started_at) * 1000),
        )
        raise RuntimeError(f"Gemini vision provider error ({response.status_code}): {response.text}")

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini vision returned no candidates")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join([(p.get("text") or "") for p in parts]).strip()
    if not text:
        raise RuntimeError("Gemini vision returned empty response")

    parsed = _extract_json_object(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini vision returned JSON that is not an object")
    logger.info(
        "Gemini:crop_image_triage response status=%s decision=%s crop_name=%s "
        "confidence=%s elapsed_ms=%s",
        response.status_code,
        parsed.get("decision"),
        parsed.get("crop_name"),
        parsed.get("confidence"),
        round((perf_counter() - started_at) * 1000),
    )
    return parsed
