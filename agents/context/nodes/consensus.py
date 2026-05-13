"""
Tier-2 ReAct: 다중 소스 합의 (consensus) 노드 (spec §6.6).

순수 함수 ``consensus(facts_list)`` 와 LangGraph 노드 래퍼 ``node_tier2_consensus``
두 단계 구조. 순수 함수는 LLM/네트워크 의존이 없어 단위 테스트가 결정적이다.

합의 룰:
- ``expected_formality_range`` : 모든 소스 (low, high) 의 교집합. 빈 교집합이면
  평균±10 으로 폴백 + warning.
- ``expected_categories`` (per slot) : 2 개 이상 소스에서 공통 등장한 카테고리만.
  소스가 1 개뿐이면 그 단일 소스의 값을 그대로 사용 (downgrade 는 score 측면에서).
- ``color_guidance`` : 합집합 (관용적, spec §6.6).
- ``rag_match_score`` : 단일 소스면 0.5 강등 + warning. 2 개 이상이면 최저
  ``extraction_confidence`` 사용 (보수적).
- ``evidence_quotes`` : 모든 소스의 quote 를 합쳐 그대로 노출.

PR-E ``pack_context`` 에서 ``event_type`` / ``source_doc_ids`` 를 최종 채워 ``DressCode`` 를
완성한다.
"""
from __future__ import annotations

from typing import Optional

from api.app.schemas.context import (
    ColorGuidance,
    DressCode,
    ExpectedCategories,
)
from api.app.schemas.enums import DressCodeTier

from agents.context.state import ContextState, ExtractedFacts


def _general_fallback() -> DressCode:
    """소스 0 개일 때 노출할 보수적 폴백 — PR-E pack_context 가 event_type 을 덮어쓴다."""
    return DressCode(
        event_type="general",
        tier=DressCodeTier.fallback_general,
        rag_match_score=0.0,
        expected_formality_range=[30, 80],
        expected_categories=ExpectedCategories(
            top=["셔츠", "블라우스", "니트", "티셔츠"],
            bottom=["슬랙스", "치마", "치노", "청바지"],
            outer=["블레이저", "자켓", "가디건"],
            shoes=["구두", "로퍼", "스니커즈"],
        ),
        color_guidance=ColorGuidance(
            preferred_tones=["흰색", "회색", "검정", "네이비", "베이지"],
            avoid_tones=["빨강", "노랑"],
        ),
        source_doc_ids=[],
        extraction_confidence=0.5,
        evidence_quotes=[],
    )


def _intersect_formality(
    facts_list: list[ExtractedFacts],
) -> tuple[list[int], Optional[str]]:
    """교집합 → 빈 교집합이면 평균±10 으로 폴백."""
    lows = [f.expected_formality_range[0] for f in facts_list]
    highs = [f.expected_formality_range[1] for f in facts_list]
    lo, hi = max(lows), min(highs)
    if lo <= hi:
        return [lo, hi], None
    mid = (sum(lows) + sum(highs)) / (2 * len(facts_list))
    fallback_lo = max(0, int(mid - 10))
    fallback_hi = min(100, int(mid + 10))
    if fallback_lo > fallback_hi:
        # 극단적 케이스 — 양쪽 모두 0 또는 100 으로 수렴.
        fallback_lo = fallback_hi = max(0, min(100, int(mid)))
    return [fallback_lo, fallback_hi], "formality_range_intersection_empty"


def _merge_categories(
    facts_list: list[ExtractedFacts],
    threshold: int,
) -> ExpectedCategories:
    """슬롯별 카테고리 카운트 → ``threshold`` 회 이상 등장한 것만 채택, 알파벳 정렬."""
    merged: dict[str, list[str]] = {}
    for slot in ("top", "bottom", "outer", "shoes"):
        counter: dict[str, int] = {}
        for f in facts_list:
            for cat in getattr(f.expected_categories, slot):
                counter[cat] = counter.get(cat, 0) + 1
        merged[slot] = sorted(c for c, k in counter.items() if k >= threshold)
    return ExpectedCategories(**merged)


def _merge_colors(facts_list: list[ExtractedFacts]) -> ColorGuidance:
    pref = sorted({t for f in facts_list for t in f.color_guidance.preferred_tones})
    avoid = sorted({t for f in facts_list for t in f.color_guidance.avoid_tones})
    return ColorGuidance(preferred_tones=pref, avoid_tones=avoid)


def consensus(facts_list: list[ExtractedFacts]) -> tuple[DressCode, list[str]]:
    """다중 소스 합의 — 순수 함수.

    Args:
        facts_list: ``extraction_confidence >= 0.5`` 로 이미 필터된 facts.

    Returns:
        ``(DressCode, warnings)``. ``DressCode.event_type`` / ``source_doc_ids`` 는
        호출 측 (PR-E pack_context) 가 채운다.
    """
    n = len(facts_list)
    warnings: list[str] = []

    if n == 0:
        return _general_fallback(), ["tier2_no_sources"]

    formality, fr_warn = _intersect_formality(facts_list)
    if fr_warn:
        warnings.append(fr_warn)

    # 카테고리 threshold: 2 소스 이상이면 공통 등장만, 1 소스면 그 소스 그대로.
    threshold = 2 if n >= 2 else 1
    categories = _merge_categories(facts_list, threshold)
    colors = _merge_colors(facts_list)

    # spec §6.6: 단일 소스면 score 0.5 로 강등. 2+ 면 보수적으로 최저 confidence.
    if n < 2:
        rag_score = 0.5
        warnings.append("single_source_downgrade")
    else:
        rag_score = min(f.extraction_confidence for f in facts_list)

    extraction_conf = sum(f.extraction_confidence for f in facts_list) / n
    evidence_quotes = [q for f in facts_list for q in f.evidence_quotes]

    dress_code = DressCode(
        event_type="",  # PR-E pack_context 가 final event_type 으로 덮어씀.
        tier=DressCodeTier.tier2_live,
        # PR-B R3 권고: 이론상 [-1, 1] 점수를 스키마 [0, 1] 로 clamp.
        rag_match_score=max(0.0, min(1.0, float(rag_score))),
        expected_formality_range=formality,
        expected_categories=categories,
        color_guidance=colors,
        source_doc_ids=[],  # PR-E 에서 search result url 로 채움.
        extraction_confidence=max(0.0, min(1.0, float(extraction_conf))),
        evidence_quotes=evidence_quotes,
    )
    return dress_code, warnings


def node_tier2_consensus(state: ContextState) -> dict:
    """LangGraph 노드: state 의 extracted_facts 중 신뢰도 통과한 것만 합의."""
    valid_facts = [
        f for f in state.extracted_facts_per_source if f.extraction_confidence >= 0.5
    ]
    dress_code, new_warnings = consensus(valid_facts)
    return {
        "tier2_consensus": dress_code,
        "warnings": state.warnings + new_warnings,
    }
