from src.agent.state import AgentIntent
from src.db.models.user import UserProfile


DIAGNOSIS_FAILURE_MESSAGE = (
    "I could not diagnose a crop disease from this image.\n"
    "Please upload a clear photo of the crop leaf, stem, or head. "
    "If the image is not a plant, Farmly cannot run disease diagnosis on it."
)

DIAGNOSIS_IMAGE_REQUEST_MESSAGE = (
    "Yes, I can help identify it. Please upload a clear photo of the affected crop part, "
    "especially the leaf, stem, head, or fruit where you see the problem. "
    "A close-up photo plus one photo of the whole plant works best."
)


def build_profile_context(profile: UserProfile | None, language_code: str | None = None) -> dict[str, str]:
    language_context = {
        "preferred_language": language_code or "",
        "response_language": "English",
    }
    if not profile:
        return language_context

    return {
        "full_name": profile.full_name or "",
        "location": profile.location or "",
        "preferred_language": language_code or profile.preferred_language or "",
        "response_language": "English",
        "user_type": profile.user_type or "",
        "years_experience": str(profile.years_experience) if profile.years_experience is not None else "",
        "main_goal": profile.main_goal or "",
        "crops_grown": profile.crops_grown or "",
    }


def fallback_response(intent: AgentIntent, message: str) -> str:
    if intent == "disease_diagnosis":
        return DIAGNOSIS_FAILURE_MESSAGE

    fallback = (message or "").strip()[:120]
    return (
        "I received your request and prepared a basic response.\n"
        f"Request: {fallback}\n"
        "Please try again if you want a more detailed advisory answer."
    )
