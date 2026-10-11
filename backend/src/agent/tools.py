import logging
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.orm import Session

from src.agent.prompts import DIAGNOSIS_IMAGE_REQUEST_MESSAGE
from src.agent.state import AgentIntent
from src.db.models.chat import ChatMessage
from src.db.models.user import UserProfile
from src.integrations.llm.gemini_adapter import generate_reply
from src.services.advisory_service import (
    run_crop_recommendation,
    run_diagnosis,
    run_fertilizer_recommendation,
    run_weather_recommendation,
)


logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class AgentToolContext:
    profile: UserProfile | None
    image_bytes: bytes | None
    image_mime_type: str | None
    recent_messages: list[dict[str, str]]
    profile_context: dict[str, str]


def collect_recent_messages(db: Session, session_id: str, limit: int = 5) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.sequence_no.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [
        {
            "sender": message.sender,
            "content": message.message_content_english or message.content,
        }
        for message in rows
    ]


def run_agent_tool(intent: AgentIntent, message: str, context: AgentToolContext) -> str:
    tool_started_at = perf_counter()
    logger.info(
        "Farmly tool:dispatch intent=%s profile_present=%s has_image=%s "
        "image_mime_type=%s recent_messages=%s",
        intent,
        bool(context.profile),
        bool(context.image_bytes),
        context.image_mime_type or "",
        len(context.recent_messages),
    )

    if intent == "crop_recommendation":
        if not context.profile:
            logger.info("Farmly tool:missing_profile intent=%s", intent)
            return "Please complete onboarding profile first."
        result = run_crop_recommendation(context.profile, recent_messages=context.recent_messages)
        text = result["recommendation_text"]
        logger.info(
            "Farmly tool:completed intent=%s response_chars=%s elapsed_ms=%s",
            intent,
            len(text or ""),
            round((perf_counter() - tool_started_at) * 1000),
        )
        return text

    if intent == "fertilizer_recommendation":
        if not context.profile:
            logger.info("Farmly tool:missing_profile intent=%s", intent)
            return "Please complete onboarding profile first."
        result = run_fertilizer_recommendation(context.profile, recent_messages=context.recent_messages)
        text = result["recommendation_text"]
        logger.info(
            "Farmly tool:completed intent=%s response_chars=%s elapsed_ms=%s",
            intent,
            len(text or ""),
            round((perf_counter() - tool_started_at) * 1000),
        )
        return text

    if intent == "weather_recommendation":
        if not context.profile:
            logger.info("Farmly tool:missing_profile intent=%s", intent)
            return "Please complete onboarding profile first."
        result = run_weather_recommendation(context.profile, recent_messages=context.recent_messages)
        text = result["recommendation_text"]
        logger.info(
            "Farmly tool:completed intent=%s response_chars=%s elapsed_ms=%s",
            intent,
            len(text or ""),
            round((perf_counter() - tool_started_at) * 1000),
        )
        return text

    if intent == "disease_diagnosis":
        if not context.image_bytes:
            logger.info("Farmly tool:missing_image intent=%s", intent)
            return DIAGNOSIS_IMAGE_REQUEST_MESSAGE
        if not context.profile:
            logger.info("Farmly tool:missing_profile intent=%s", intent)
            return "Please complete onboarding profile first."
        diagnosis = run_diagnosis(
            context.profile,
            context.image_bytes,
            image_mime_type=context.image_mime_type or "image/jpeg",
            recent_messages=context.recent_messages,
        )
        logger.info(
            "Farmly tool:completed intent=%s provider=%s confidence_status=%s "
            "needs_retake=%s response_chars=%s elapsed_ms=%s",
            intent,
            diagnosis.provider,
            diagnosis.confidence_status,
            diagnosis.needs_retake,
            len(diagnosis.advice_text or ""),
            round((perf_counter() - tool_started_at) * 1000),
        )
        return diagnosis.advice_text

    text = generate_reply(
        latest_user_message=message,
        recent_messages=context.recent_messages,
        profile_context=context.profile_context,
    )
    logger.info(
        "Farmly tool:completed intent=%s response_chars=%s elapsed_ms=%s",
        intent,
        len(text or ""),
        round((perf_counter() - tool_started_at) * 1000),
    )
    return text
