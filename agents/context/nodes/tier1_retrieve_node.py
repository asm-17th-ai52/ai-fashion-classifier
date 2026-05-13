"""
Tier-1 retrieve LangGraph 노드 — PR-B ``tier1_retrieve`` 의 thin wrapper.

retrieve 결과의 top-1 frontmatter metadata 를 정식 ``DressCode`` 로 변환해
``tier1_result`` 에 저장 (state schema 는 ``Optional[DressCode]``). 분기는 ``tier1_score``
만 본다.
"""
from __future__ import annotations

from typing import Any

from api.app.schemas.context import (
    ColorGuidance,
    DressCode,
    ExpectedCategories,
)
from api.app.schemas.enums import DressCodeTier

from agents.context.state import ContextState
from agents.context.tier1 import tier1_retrieve


def _meta_to_dress_code(metadata: dict[str, Any], score: float) -> DressCode:
    """frontmatter metadata → DressCode (Tier-1 hit 용)."""
    cats = metadata.get("expected_categories") or {}
    colors = metadata.get("color_guidance") or {}
    source_path = metadata.get("source_path") or ""
    doc_id = f"dc_{metadata.get('event_type', 'unknown')}_v1"
    if source_path:
        doc_id = f"static/{source_path}"
    return DressCode(
        event_type=metadata.get("event_type", "general"),
        tier=DressCodeTier.tier1,
        # PR-B R3: 이론상 [-1, 1] cosine 을 [0, 1] 로 clamp.
        rag_match_score=max(0.0, min(1.0, float(score))),
        expected_formality_range=metadata.get("expected_formality_range", [30, 80]),
        expected_categories=ExpectedCategories(
            top=cats.get("top", []),
            bottom=cats.get("bottom", []),
            outer=cats.get("outer", []),
            shoes=cats.get("shoes", []),
        ),
        color_guidance=ColorGuidance(
            preferred_tones=colors.get("preferred_tones", []),
            avoid_tones=colors.get("avoid_tones", []),
        ),
        source_doc_ids=[doc_id],
        extraction_confidence=1.0,  # hand_curated 코퍼스이므로 신뢰도 만점.
        evidence_quotes=[],
    )


def node_tier1_retrieve(state: ContextState) -> dict[str, Any]:
    """state.request.event_type 으로 FAISS 검색 → top-1 score + DressCode 저장."""
    query = state.request.event_type or "general"
    try:
        hits = tier1_retrieve(query, k=3)
    except Exception as exc:  # noqa: BLE001 — index 파일 누락 / SDK 변경 fail-soft
        return {
            "tier1_score": 0.0,
            "warnings": state.warnings
            + [f"tier1_retrieve_failed: {type(exc).__name__}: {exc}"],
        }

    if not hits:
        return {"tier1_score": 0.0}

    top = hits[0]
    return {
        "tier1_score": float(top["score"]),
        "tier1_result": _meta_to_dress_code(top["metadata"], top["score"]),
    }
