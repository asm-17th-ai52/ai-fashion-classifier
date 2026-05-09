"""ContextResponse — per docs/specs/07-data-contracts.md §3."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, conlist

from .enums import DressCodeTier


class ExpectedCategories(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top: list[str] = Field(default_factory=list)
    bottom: list[str] = Field(default_factory=list)
    outer: list[str] = Field(default_factory=list)
    shoes: list[str] = Field(default_factory=list)


class ColorGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_tones: list[str] = Field(default_factory=list)
    avoid_tones: list[str] = Field(default_factory=list)


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    quote: str = Field(..., max_length=500)
    fetched_at: datetime


class LiveResearchMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    search_queries_used: list[str] = Field(default_factory=list)
    sources_count: int = Field(default=0, ge=0)
    react_steps: int = Field(default=0, ge=0, le=5)
    latency_ms: int = Field(default=0, ge=0)


class DressCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str
    tier: DressCodeTier
    rag_match_score: float = Field(..., ge=0.0, le=1.0)
    expected_formality_range: conlist(int, min_length=2, max_length=2)
    expected_categories: ExpectedCategories = Field(default_factory=ExpectedCategories)
    color_guidance: ColorGuidance = Field(default_factory=ColorGuidance)
    source_doc_ids: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list)
    live_research_meta: Optional[LiveResearchMeta] = None


class ContextResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    dress_code: DressCode
    warnings: list[str] = Field(default_factory=list)
