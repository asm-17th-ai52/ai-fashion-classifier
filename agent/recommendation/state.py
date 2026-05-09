from pydantic import BaseModel, Field

from .schemas import (
    CheckResult,
    ContextResponse,
    RecommendationResponse,
    Score,
    Suggestion,
    VisionResponse,
)


class RecommendationState(BaseModel):
    outfit: VisionResponse
    context: ContextResponse

    checks: list[CheckResult] = Field(default_factory=list)
    score: Score | None = None
    suggestions: list[Suggestion] = Field(default_factory=list)

    response: RecommendationResponse | None = None
