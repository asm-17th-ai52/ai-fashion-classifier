"""Backend API contract — per docs/specs/07-data-contracts.md §5."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .context import ContextResponse
from .recommendation import RecommendationResponse
from .vision import VisionResponse


class SessionCreateRequest(BaseModel):
    """Form-payload model (image is multipart UploadFile, parsed separately).

    Backend extracts `image` via FastAPI File(...). The remaining fields are
    Form() params and assembled into this model for downstream usage.
    """

    model_config = ConfigDict(extra="forbid")
    event_type: str
    event_type_is_custom: bool = False
    event_datetime: datetime
    allow_live_research: bool = True


class AgentLatenciesMs(BaseModel):
    model_config = ConfigDict(extra="allow")
    vision: int = 0
    context: int = 0
    context_tier2: Optional[int] = None
    recommendation: int = 0


class SessionMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    latency_ms: int
    agent_latencies_ms: AgentLatenciesMs
    cache_hits: list[str] = Field(default_factory=list)
    tier2_triggered: bool = False


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    outfit: VisionResponse
    context: ContextResponse
    recommendation: RecommendationResponse
    meta: SessionMeta


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    applied_suggestion_ids: list[str] = Field(default_factory=list)


class SimulateAppliedItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    individual_delta: int
    removes_blocker: bool


class ChecksFlipped(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_pass: list[str] = Field(default_factory=list)
    to_fail: list[str] = Field(default_factory=list)


class SimulateResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    original_overall: int
    simulated_overall: int
    delta: int
    applied: list[SimulateAppliedItem]
    simulated_score: dict[str, Any]
    checks_flipped: ChecksFlipped


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str = "ok"
    dependencies: dict[str, str] = Field(default_factory=dict)
    version: str = "0.1.0"


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody
