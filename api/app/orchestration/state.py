"""SessionState — super-graph shared state per docs/specs/05-backend-spec.md §5.1.

Concurrent fan-out into vision and context produces independent dict updates;
LangGraph merges them into the same state. We therefore avoid having both
sub-graphs write to the same field. Each sub-graph writes to its own slot.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import (
    ContextResponse,
    RecommendationResponse,
    SessionCreateRequest,
    VisionResponse,
)


def _merge_dict(left: dict, right: dict) -> dict:
    out = dict(left or {})
    out.update(right or {})
    return out


class SessionState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Inputs
    session_id: str
    image_bytes: bytes
    request: SessionCreateRequest
    started_at_ms: int = 0

    # Preprocess output
    preprocessed_image: Optional[bytes] = None
    preprocess_meta: Annotated[dict[str, Any], _merge_dict] = Field(default_factory=dict)

    # Agent sub-graph outputs (each agent writes its own field)
    outfit: Optional[VisionResponse] = None
    context: Optional[ContextResponse] = None
    recommendation: Optional[RecommendationResponse] = None

    # Meta — these are concurrently written by vision and context, so we use a
    # reducer that merges dict updates instead of overwriting.
    agent_latencies_ms: Annotated[dict[str, int], _merge_dict] = Field(
        default_factory=dict
    )
    cache_hits: Annotated[list[str], operator.add] = Field(default_factory=list)
    tier2_triggered: bool = False
    errors: Annotated[list[dict], operator.add] = Field(default_factory=list)
