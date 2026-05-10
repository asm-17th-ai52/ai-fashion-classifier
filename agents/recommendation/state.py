from pydantic import BaseModel, Field

from .schemas import (
    CheckResult,
    ContextResponse,
    RecommendationResponse,
    Score,
    Suggestion,
    VisionResponse,
)
from .narrator import Narration


class RecommendationState(BaseModel):
    outfit: VisionResponse
    context: ContextResponse

    checks: list[CheckResult] = Field(default_factory=list)
    score: Score | None = None
    suggestions: list[Suggestion] = Field(default_factory=list)

    fallback_explanation: str | None = None
    narration: Narration | None = None
    narrator_retries: int = 0
    narrator_violations: list[str] = Field(default_factory=list)
    narrator_used_fallback: bool = False

    response: RecommendationResponse | None = None
