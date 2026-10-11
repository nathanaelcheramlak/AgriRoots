import logging
from dataclasses import dataclass
from typing import get_args

from src.agent.state import AgentIntent
from src.integrations.llm.gemini_adapter import classify_chat_intent


logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class IntentDecision:
    intent: AgentIntent
    confidence: float
    reason: str


TOOL_CATALOG: list[dict[str, str]] = [
    {
        "intent": "general",
        "description": "General farming conversation and advice that does not need a specialized data tool.",
    },
    {
        "intent": "crop_recommendation",
        "description": "Recommend suitable crops using the farmer profile, location, weather, and soil context.",
    },
    {
        "intent": "fertilizer_recommendation",
        "description": "Advise on fertilizer type, timing, and practical application considerations.",
    },
    {
        "intent": "weather_recommendation",
        "description": "Interpret current or forecast weather and explain farm actions.",
    },
    {
        "intent": "disease_diagnosis",
        "description": (
            "Handle crop disease identification or suspected disease conversations. "
            "If no image is uploaded, this tool asks the farmer for a clear crop photo."
        ),
    },
]

VALID_INTENTS = set(get_args(AgentIntent))


def _confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _fallback_intent(has_image: bool, reason: str) -> IntentDecision:
    if has_image:
        decision = IntentDecision(
            intent="disease_diagnosis",
            confidence=0.5,
            reason=reason,
        )
    else:
        decision = IntentDecision(
            intent="general",
            confidence=0.2,
            reason=reason,
        )
    logger.info(
        "Farmly intent:fallback intent=%s confidence=%.2f reason=%s has_image=%s",
        decision.intent,
        decision.confidence,
        decision.reason,
        has_image,
    )
    return decision


def classify_intent(
    message: str,
    has_image: bool,
    *,
    recent_messages: list[dict[str, str]],
    profile_context: dict[str, str],
) -> IntentDecision:
    profile_field_count = sum(1 for value in profile_context.values() if value)
    logger.info(
        "Farmly intent:llm_request has_image=%s message_chars=%s recent_messages=%s "
        "profile_fields=%s tool_count=%s",
        has_image,
        len(message or ""),
        len(recent_messages),
        profile_field_count,
        len(TOOL_CATALOG),
    )
    try:
        payload = classify_chat_intent(
            latest_user_message=message,
            has_image=has_image,
            recent_messages=recent_messages,
            profile_context=profile_context,
            tool_catalog=TOOL_CATALOG,
        )
    except Exception:
        logger.exception("Farmly intent:llm_error")
        return _fallback_intent(has_image, "intent_router_failed")

    intent = str(payload.get("intent") or "").strip()
    logger.info(
        "Farmly intent:llm_response raw_intent=%s confidence=%s reason=%s",
        intent,
        payload.get("confidence"),
        payload.get("reason") or "",
    )
    if intent not in VALID_INTENTS:
        logger.warning("Farmly intent:invalid_intent raw_intent=%s", intent)
        return _fallback_intent(has_image, "invalid_intent")

    return IntentDecision(
        intent=intent,  # type: ignore[arg-type]
        confidence=_confidence(payload.get("confidence")),
        reason=str(payload.get("reason") or "llm_tool_selection"),
    )
