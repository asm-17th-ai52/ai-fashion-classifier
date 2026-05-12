"""Stub context sub-graph. Produces schema-valid ContextResponse fixture.

Replace by ``app.agents.context.context_subgraph`` once delivered
(docs/specs/03-agent-context-spec.md §10.5).
"""
from __future__ import annotations

import time
from typing import Any

from app.utils.state_helpers import state_get
from app.schemas import ContextResponse, DressCode, DressCodeTier
from app.schemas.context import ColorGuidance, ExpectedCategories


# 카테고리: 실제 VLM(Gemini) 출력이 한글임을 run_test.py로 확인 (2026-05-10)
# 색상 톤: Vision Agent color_lookup.py의 한글 색상명과 일치시킴
_TIER1_TABLE: dict[str, dict[str, Any]] = {
    "interview": {
        "expected_formality_range": [70, 95],
        "top": ["셔츠", "블라우스"],
        "bottom": ["슬랙스", "치마"],
        "outer": ["블레이저", "자켓"],
        "shoes": ["구두", "로퍼"],
        "preferred_tones": ["흰색", "회색", "검정", "네이비", "진회색"],
        "avoid_tones": ["빨강", "노랑", "핑크", "코랄", "연두", "주황"],
    },
    "business_meeting": {
        "expected_formality_range": [65, 90],
        "top": ["셔츠", "블라우스", "니트"],
        "bottom": ["슬랙스", "치마"],
        "outer": ["블레이저", "자켓"],
        "shoes": ["구두", "로퍼"],
        "preferred_tones": ["흰색", "회색", "검정", "네이비", "진회색"],
        "avoid_tones": ["빨강", "노랑", "핑크", "코랄", "연두"],
    },
    "presentation": {
        "expected_formality_range": [65, 90],
        "top": ["셔츠", "블라우스", "니트"],
        "bottom": ["슬랙스", "치마"],
        "outer": ["블레이저", "자켓"],
        "shoes": ["구두", "로퍼"],
        "preferred_tones": ["흰색", "회색", "검정", "네이비"],
        "avoid_tones": ["빨강", "노랑", "핑크", "코랄", "연두"],
    },
    "wedding_guest": {
        "expected_formality_range": [70, 95],
        "top": ["셔츠", "블라우스", "드레스"],
        "bottom": ["슬랙스", "치마"],
        "outer": ["블레이저", "자켓"],
        "shoes": ["구두", "로퍼"],
        "preferred_tones": ["베이지", "회색", "네이비", "검정"],
        "avoid_tones": ["흰색", "오프화이트", "빨강", "노랑"],
    },
    "office_daily": {
        "expected_formality_range": [55, 80],
        "top": ["셔츠", "블라우스", "니트", "티셔츠"],
        "bottom": ["슬랙스", "치마", "치노"],
        "outer": ["블레이저", "가디건"],
        "shoes": ["구두", "로퍼", "스니커즈"],
        "preferred_tones": ["흰색", "회색", "검정", "네이비", "베이지"],
        "avoid_tones": ["빨강", "노랑", "연두", "핑크"],
    },
    "casual_date": {
        "expected_formality_range": [40, 70],
        "top": ["셔츠", "블라우스", "니트", "티셔츠"],
        "bottom": ["슬랙스", "치노", "청바지"],
        "outer": ["자켓", "가디건"],
        "shoes": ["로퍼", "스니커즈"],
        "preferred_tones": [],
        "avoid_tones": [],
    },
    "school_daily": {
        "expected_formality_range": [20, 55],
        "top": ["셔츠", "니트", "티셔츠", "후드티"],
        "bottom": ["치노", "청바지"],
        "outer": ["자켓", "가디건"],
        "shoes": ["스니커즈", "로퍼"],
        "preferred_tones": [],
        "avoid_tones": [],
    },
    "outdoor_activity": {
        "expected_formality_range": [10, 45],
        "top": ["티셔츠", "니트"],
        "bottom": ["치노", "반바지"],
        "outer": ["자켓"],
        "shoes": ["스니커즈"],
        "preferred_tones": [],
        "avoid_tones": [],
    },
    "general": {
        "expected_formality_range": [30, 80],
        "top": ["셔츠", "블라우스", "니트", "티셔츠"],
        "bottom": ["슬랙스", "치마", "치노", "청바지"],
        "outer": ["블레이저", "자켓", "가디건"],
        "shoes": ["구두", "로퍼", "스니커즈"],
        "preferred_tones": ["흰색", "회색", "검정", "네이비", "베이지"],
        "avoid_tones": ["빨강", "노랑"],
    },
}


def _resolve_table(event_type: str, custom: bool) -> tuple[str, dict[str, Any], DressCodeTier, float]:
    if custom:
        return event_type, _TIER1_TABLE["general"], DressCodeTier.fallback_general, 0.5
    if event_type in _TIER1_TABLE:
        return event_type, _TIER1_TABLE[event_type], DressCodeTier.tier1, 0.92
    return "general", _TIER1_TABLE["general"], DressCodeTier.fallback_general, 0.5


def _stub_context(state: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    session_id = state_get(state, "session_id", "sess_unknown")
    request = state_get(state, "request")
    event_type = getattr(request, "event_type", "general")
    custom = bool(getattr(request, "event_type_is_custom", False))

    resolved_type, table, tier, score = _resolve_table(event_type, custom)
    dress_code = DressCode(
        event_type=resolved_type,
        tier=tier,
        rag_match_score=score,
        expected_formality_range=table["expected_formality_range"],
        expected_categories=ExpectedCategories(
            top=table["top"],
            bottom=table["bottom"],
            outer=table["outer"],
            shoes=table["shoes"],
        ),
        color_guidance=ColorGuidance(
            preferred_tones=table["preferred_tones"],
            avoid_tones=table["avoid_tones"],
        ),
        source_doc_ids=[f"stub_{resolved_type}_v1"],
        extraction_confidence=1.0 if tier == DressCodeTier.tier1 else 0.5,
    )
    response = ContextResponse(
        session_id=session_id,
        dress_code=dress_code,
        warnings=[],
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    update: dict[str, Any] = {
        "context": response,
        "agent_latencies_ms": {"context": elapsed},
    }
    if tier != DressCodeTier.tier1:
        update["tier2_triggered"] = True
    return update


context_subgraph_stub = _stub_context
