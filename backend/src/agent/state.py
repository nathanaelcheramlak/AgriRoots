from typing import Literal, TypedDict


AgentIntent = Literal[
    "general",
    "crop_recommendation",
    "fertilizer_recommendation",
    "weather_recommendation",
    "disease_diagnosis",
]


class AgentState(TypedDict):
    message: str
    has_image: bool
    intent: AgentIntent
    result_text: str

