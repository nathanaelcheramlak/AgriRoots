import logging
from time import perf_counter
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from src.agent.intents import classify_intent
from src.agent.prompts import build_profile_context, fallback_response
from src.agent.state import AgentState
from src.agent.tools import AgentToolContext, collect_recent_messages, run_agent_tool
from src.db.models.user import UserProfile


logger = logging.getLogger("uvicorn.error")


def run_farmly_agent(
    *,
    db: Session,
    session_id: str,
    profile: UserProfile | None,
    message: str,
    image_bytes: bytes | None,
    image_mime_type: str | None = None,
    language_code: str | None = None,
) -> tuple[str, str]:
    agent_started_at = perf_counter()
    profile_context = build_profile_context(profile, language_code=language_code)
    recent_messages = collect_recent_messages(db, session_id, limit=5)
    profile_field_count = sum(1 for value in profile_context.values() if value)
    logger.info(
        "Farmly agent:start session_id=%s has_image=%s image_mime_type=%s "
        "language_code=%s message_chars=%s profile_present=%s",
        session_id,
        bool(image_bytes),
        image_mime_type or "",
        language_code or "",
        len(message or ""),
        bool(profile),
    )
    logger.info(
        "Farmly agent:context_loaded session_id=%s recent_messages=%s profile_fields=%s",
        session_id,
        len(recent_messages),
        profile_field_count,
    )
    tool_context = AgentToolContext(
        profile=profile,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
        recent_messages=recent_messages,
        profile_context=profile_context,
    )

    state: AgentState = {
        "message": message,
        "has_image": bool(image_bytes),
        "intent": "general",
        "result_text": "",
    }

    def classify_node(current: AgentState) -> AgentState:
        classify_started_at = perf_counter()
        logger.info(
            "Farmly agent:classify_start session_id=%s has_image=%s message_chars=%s",
            session_id,
            current["has_image"],
            len(current["message"] or ""),
        )
        if current["has_image"]:
            current["intent"] = "disease_diagnosis"
            logger.info(
                "Farmly agent:classify_bypass session_id=%s intent=%s reason=image_upload elapsed_ms=%s",
                session_id,
                current["intent"],
                round((perf_counter() - classify_started_at) * 1000),
            )
            return current

        decision = classify_intent(
            current["message"],
            current["has_image"],
            recent_messages=recent_messages,
            profile_context=profile_context,
        )
        current["intent"] = decision.intent
        logger.info(
            "Farmly agent:classify_done session_id=%s intent=%s confidence=%.2f "
            "reason=%s elapsed_ms=%s",
            session_id,
            decision.intent,
            decision.confidence,
            decision.reason,
            round((perf_counter() - classify_started_at) * 1000),
        )
        return current

    def execute_node(current: AgentState) -> AgentState:
        intent = current["intent"]
        tool_started_at = perf_counter()
        logger.info(
            "Farmly agent:tool_start session_id=%s intent=%s",
            session_id,
            intent,
        )
        try:
            current["result_text"] = run_agent_tool(intent, current["message"], tool_context)
            logger.info(
                "Farmly agent:tool_done session_id=%s intent=%s response_chars=%s elapsed_ms=%s",
                session_id,
                intent,
                len(current["result_text"] or ""),
                round((perf_counter() - tool_started_at) * 1000),
            )
        except Exception:
            logger.exception(
                "Farmly agent:tool_error session_id=%s intent=%s",
                session_id,
                intent,
            )
            current["result_text"] = fallback_response(intent, current["message"])
            logger.info(
                "Farmly agent:fallback_used session_id=%s intent=%s response_chars=%s",
                session_id,
                intent,
                len(current["result_text"] or ""),
            )
        return current

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("execute", execute_node)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "execute")
    graph.add_edge("execute", END)

    app = graph.compile()
    out: dict[str, Any] = app.invoke(state)
    logger.info(
        "Farmly agent:done session_id=%s final_intent=%s response_chars=%s elapsed_ms=%s",
        session_id,
        out["intent"],
        len(out["result_text"] or ""),
        round((perf_counter() - agent_started_at) * 1000),
    )
    return out["intent"], out["result_text"]
