"""
Tier 분기 함수 (spec §10.3 그대로).

- ``decide_dresscode_tier`` : ``tier1_retrieve`` 결과 → Tier-1 채택 / Tier-2 진입 / general fallback.
- ``decide_tier2_continue``: ``tier2_extract_facts`` 결과 → 추가 검색 / consensus / abort.

순수 함수 (state 만 인자) — LangGraph 가 string label 만 보고 conditional edge 라우팅.
"""
from __future__ import annotations

from agents.context.latency import latency_exceeded
from agents.context.state import ContextState
from agents.context.tier1 import THRESHOLD as TIER1_THRESHOLD
from agents.context.tools import check_budget


def decide_dresscode_tier(state: ContextState) -> str:
    """tier1_retrieve 다음 분기."""
    # 1) Tier-1 통과 + custom event_type 아니면 그대로 사용.
    if state.tier1_score >= TIER1_THRESHOLD and not state.request.event_type_is_custom:
        return "use_tier1"
    # 2) Tier-2 비활성 옵션 → general fallback.
    if not state.request.allow_live_research:
        return "fallback_general"
    # 3) 글로벌 budget 도달 시 fallback.
    ok, _ = check_budget()
    if not ok:
        return "fallback_general"
    return "go_tier2"


def decide_tier2_continue(state: ContextState) -> str:
    """tier2_extract_facts 다음 분기 (spec §10.3)."""
    # spec §6.5: confidence >= 0.5 만 유효 소스로 카운트.
    n_sources = sum(
        1 for f in state.extracted_facts_per_source if f.extraction_confidence >= 0.5
    )
    # spec §6.2 / §6.8: react_step 5 회 초과 또는 12s latency 초과 → abort.
    if state.react_step >= 5 or latency_exceeded(state):
        return "abort"
    # spec §6.6: 최소 2 개 소스 합의가 채집되면 consensus 로 진행.
    if n_sources >= 2:
        return "consensus"
    return "more_search"
