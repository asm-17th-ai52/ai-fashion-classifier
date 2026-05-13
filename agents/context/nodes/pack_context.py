"""
``pack_context`` 노드 — 그래프 종착점. state 의 분기 결과를 단일 ``DressCode`` 로 통합.

세 경로 모두 본 노드를 거친다:
1. ``decide_dresscode_tier == "use_tier1"`` → ``state.tier1_result`` 를 그대로 사용.
2. ``decide_dresscode_tier == "fallback_general"`` → 고정 fallback DressCode 생성.
3. Tier-2 루프 ``"consensus"`` 종료 → ``state.tier2_consensus`` 사용.
   여기서 ``event_type`` / ``source_doc_ids`` / ``live_research_meta`` 를 최종 채운다.
4. Tier-2 루프 ``"abort"`` 종료 → consensus 가 비어있으면 fallback.

adapter 가 ``state.dress_code`` 를 꺼내 ``ContextResponse`` 로 감싼다.
"""
from __future__ import annotations

from typing import Any

from app.schemas.context import (
    ColorGuidance,
    DressCode,
    ExpectedCategories,
    EvidenceQuote,
    LiveResearchMeta,
)
from app.schemas.enums import DressCodeTier

from agents.context.state import ContextState


def _general_fallback() -> DressCode:
    """allow_live_research=False / budget 초과 시 사용하는 고정 fallback."""
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
        source_doc_ids=["fallback_general_v1"],
        extraction_confidence=0.5,
        evidence_quotes=[],
    )


def _dedup_evidence_quotes(quotes: list[EvidenceQuote]) -> list[EvidenceQuote]:
    """URL + quote text 조합으로 dedup (외부 리뷰 R4 권고)."""
    seen: set[tuple[str, str]] = set()
    out: list[EvidenceQuote] = []
    for q in quotes:
        key = (str(q.url), q.quote)
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def _finalize_tier2(state: ContextState) -> DressCode:
    """tier2_consensus 의 빈 필드 (event_type, source_doc_ids, live_research_meta) 채움."""
    dc = state.tier2_consensus
    if dc is None:  # 방어적 — 호출 측이 보장하지만 type-narrow.
        return _general_fallback()

    # search 결과의 URL 을 source_doc_ids 로 사용.
    search_urls: list[str] = []
    last_results = (state.tier2_meta or {}).get("last_search_results") or []
    for item in last_results:
        if isinstance(item, dict):
            url = item.get("url")
            if url:
                search_urls.append(str(url))
    # 중복 제거 후 최대 5 개.
    source_doc_ids = list(dict.fromkeys(search_urls))[:5]

    # live_research_meta: spec §7.1.
    # latency_ms 는 본 노드에서 측정할 신뢰할 만한 sub-graph 진입 시각이 없어 0 으로 둠.
    # 진짜 측정값은 adapter 가 ``agent_latencies_ms["context"]`` / ``["context_tier2"]``
    # 에 채워 super-graph 로 전달한다. 본 필드는 LiveResearchMeta 스키마 호환용.
    meta = LiveResearchMeta(
        search_queries_used=list(state.search_queries_used),
        sources_count=len(state.extracted_facts_per_source),
        react_steps=state.react_step,
        latency_ms=0,
    )

    return DressCode(
        event_type=state.request.event_type,
        tier=dc.tier,
        rag_match_score=max(0.0, min(1.0, float(dc.rag_match_score))),
        expected_formality_range=list(dc.expected_formality_range),
        expected_categories=dc.expected_categories,
        color_guidance=dc.color_guidance,
        source_doc_ids=source_doc_ids,
        extraction_confidence=dc.extraction_confidence,
        evidence_quotes=_dedup_evidence_quotes(list(dc.evidence_quotes)),
        live_research_meta=meta,
    )


def node_pack_context(state: ContextState) -> dict[str, Any]:
    """state 의 분기 결과 → 최종 DressCode (state.dress_code) 로 통합."""
    if state.tier2_consensus is not None:
        dress_code = _finalize_tier2(state)
    elif state.tier1_result is not None:
        # Tier-1 hit: 이미 retrieve 노드가 정식 DressCode 로 만들어 둠.
        dress_code = state.tier1_result
    else:
        # fallback_general 분기 또는 tier-2 abort with no consensus.
        dress_code = _general_fallback()

    # 최종 안전망: rag_match_score / extraction_confidence clamp.
    dress_code = dress_code.model_copy(
        update={
            "rag_match_score": max(0.0, min(1.0, float(dress_code.rag_match_score))),
            "extraction_confidence": max(
                0.0, min(1.0, float(dress_code.extraction_confidence))
            ),
        }
    )
    return {"dress_code": dress_code}
