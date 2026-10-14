from pydantic import BaseModel, Field


class VoiceTranscriptionResponse(BaseModel):
    transcript: str
    confidence: float | None = None
    language_code: str


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language_code: str | None = Field(default=None, min_length=2, max_length=20)

