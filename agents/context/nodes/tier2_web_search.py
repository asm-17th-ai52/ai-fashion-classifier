"""
Tier-2 web search LangGraph 노드 — PR-C ``web_search`` 의 thin wrapper.

가장 최근 ``state.search_queries_used`` 의 쿼리로 Tavily 검색.
호당 ``web_search`` 3 회 상한 (spec §6.8) + 글로벌 일일/월간 budget 카운터 갱신.
검색 결과는 ``state.tier2_meta["last_search_results"]`` 에 저장 — 다음 fetch 노드가 소비.
"""
from __future__ import annotations

from typing import Any

from agents.context.latency import mark_tier2_start
from agents.context.state import ContextState
from agents.context.tools import increment, web_search


_REQUEST_SEARCH_LIMIT = 3  # spec §6.8


def node_tier2_web_search(state: ContextState) -> dict[str, Any]:
    """state 의 마지막 query 를 Tavily 검색하고 결과를 tier2_meta 에 저장."""
    if not state.search_queries_used:
        return {
            "warnings": state.warnings + ["tier2_web_search_no_query"],
            "tier2_meta": mark_tier2_start(state.tier2_meta),
        }
    if state.web_search_calls >= _REQUEST_SEARCH_LIMIT:
        return {
            "warnings": state.warnings + ["tier2_web_search_request_limit"],
            "tier2_meta": mark_tier2_start(state.tier2_meta),
        }

    query = state.search_queries_used[-1]
    results, warning = web_search(query, max_results=5)
    increment("web_search_calls")

    new_warnings = list(state.warnings)
    if warning:
        new_warnings.append(warning)

    # last_search_results 는 다음 fetch 노드가 소비. Tier-2 start 시각도 보존.
    meta = mark_tier2_start(state.tier2_meta)
    meta = {**meta, "last_search_results": list(results or [])}

    return {
        "web_search_calls": state.web_search_calls + 1,
        "tier2_active": True,
        "tier2_meta": meta,
        "warnings": new_warnings,
    }
