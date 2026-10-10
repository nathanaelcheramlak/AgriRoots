import base64
import json
import logging
import re
from time import sleep
from time import perf_counter

import httpx

from src.config.settings import get_settings


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


def _build_system_instruction(profile_context: dict[str, str]) -> str:
    profile_lines = []
    for key, value in profile_context.items():
        if value:
            profile_lines.append(f"- {key}: {value}")

    profile_block = "\n".join(profile_lines) if profile_lines else "- profile: not provided"
    return (
        "You are Farmly, an agricultural assistant for Ethiopian smallholder farmers.\n"
        "Give practical, clear, and simple advice suitable for the farmer's context.\n"
        "Prefer agriculture-focused answers. If off-topic, gently redirect to farming help.\n"
        "Keep the answer short and easy to understand for non-technical farmers.\n"
        "Use 3 to 6 short lines and avoid complex words.\n\n"
        "If the farmer asks to identify or diagnose a crop disease without a photo, "
        "ask for a clear photo of the affected leaf, stem, head, or fruit instead of guessing.\n\n"
        "Farmer profile context:\n"
        f"{profile_block}"
    )


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
            "parts": [{"text": _build_system_instruction(profile_context)}],
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

    prompt = (
        "You are Farmly's tool-selection agent.\n"
        "Choose exactly one tool for the latest farmer request.\n"
        "Do not answer the farmer. Only select the best tool.\n\n"
        "Available tools:\n"
        f"{json.dumps(tool_catalog, ensure_ascii=False)}\n\n"
        "Farmer profile context:\n"
        f"{json.dumps(profile_context, ensure_ascii=False)}\n\n"
        "Recent conversation:\n"
        f"{json.dumps(recent_messages[-5:], ensure_ascii=False)}\n\n"
        "Latest request metadata:\n"
        f"{json.dumps({'has_image_upload': has_image}, ensure_ascii=False)}\n\n"
        "Latest farmer message:\n"
        f"{json.dumps(latest_user_message or '', ensure_ascii=False)}\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{"intent":"general","confidence":0.75,"reason":"short reason"}\n'
        "Rules:\n"
        "- intent must exactly match one available tool intent.\n"
        "- If an image is uploaded for crop diagnosis, choose disease_diagnosis.\n"
        "- If the farmer wants to identify, confirm, or investigate a crop disease, choose disease_diagnosis even when no image is uploaded.\n"
        "- Use recent conversation to understand follow-up questions like asking how identification works.\n"
        "- Use general only when no specialized tool is appropriate.\n"
        "- confidence must be a number from 0 to 1."
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

    supported_crop_text = ", ".join(sorted(set(supported_crops)))
    prompt = (
        "You are Farmly's crop image triage system.\n"
        "Look at the uploaded image and decide if it is a plant/crop image.\n"
        "If it is a plant, identify the most likely crop.\n"
        "Use English crop names and scientific names when possible, even if the crop is known in another language.\n"
        "Sorghum (Sorghum bicolor) must be routed to Farmly's local sorghum disease model.\n"
        "Enset (Ensete ventricosum), also called false banana or Ethiopian banana, must be routed to Farmly's local enset disease model. "
        "Enset looks similar to a banana plant but is NOT a banana — it is a staple crop in Ethiopia. "
        "If the image shows enset, set is_enset=true and decision=enset_model.\n"
        "Non-sorghum, non-enset crops can be routed to Kindwise Crop.health only if they match this supported crop list:\n"
        f"{supported_crop_text}\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "is_plant": true,\n'
        '  "crop_name": "enset",\n'
        '  "scientific_name": "Ensete ventricosum",\n'
        '  "common_names": ["enset", "false banana"],\n'
        '  "confidence": 0.85,\n'
        '  "is_sorghum": false,\n'
        '  "is_enset": true,\n'
        '  "is_kindwise_supported": false,\n'
        '  "supported_crop_match": "",\n'
        '  "decision": "enset_model",\n'
        '  "reason": "short reason"\n'
        "}\n\n"
        "Rules:\n"
        '- decision must be one of: "not_plant", "uncertain", "sorghum_model", "enset_model", '
        '"kindwise_crop_health", "unsupported_crop".\n'
        "- confidence must be a number from 0 to 1.\n"
        "- If this is not clearly a plant/crop image, set is_plant=false and decision=not_plant.\n"
        "- If the image is too unclear to identify the crop, set decision=uncertain.\n"
        "- Do not diagnose disease here. Only classify/reroute the image."
    )

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
