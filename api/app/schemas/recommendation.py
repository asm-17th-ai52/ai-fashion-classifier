"""RecommendationResponse — per docs/specs/07-data-contracts.md §4."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import CheckGroup, GarmentSlot
from .enums import SuggestionAction as SuggestionActionEnum


class Score(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall: int = Field(..., ge=0, le=100)
    method: Literal["group_weighted_with_blocker_cap"] = (
        "group_weighted_with_blocker_cap"
    )
    group_scores: dict[str, float] = Field(default_factory=dict)
    blocker_failed: bool = False
    cap_applied: Optional[Literal["blocker_cap_50"]] = None


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., pattern=r"^[A-E][0-9]+$")
    group: CheckGroup
    label: str
    result: Literal["pass", "fail", "not_applicable"]
    applicable: bool
    is_blocker: bool
    evidence_facts: list[str] = Field(default_factory=list)


class SuggestionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: SuggestionActionEnum
    target_slot: Optional[GarmentSlot] = None
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str
    fixes_check_ids: list[str] = Field(..., min_length=1)
    action: SuggestionAction
    rationale_facts: list[str] = Field(..., min_length=1)
    expected_overall_delta: int
    removes_blocker: bool
    user_facing_text: Optional[str] = Field(default=None, max_length=200)


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    score: Score
    checks: list[Check]
    blockers_failed: list[str] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list, max_length=3)
    explanation: str = Field(default="", max_length=400)
