"""
Tier-2 fetch_pages LangGraph 노드 — ``tools.fetch.fetch_page`` 의 multi-URL wrapper.

이전 ``tier2_web_search`` 노드가 ``tier2_meta["last_search_results"]`` 에 둔 URL
리스트를 가져와 각각 fetch. 회당 fetch 5 회 상한 (spec §6.8) + 글로벌 budget 카운터.
성공한 페이지만 ``state.fetched_pages`` 에 append. 실패는 warnings 로.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.context.state import ContextState, FetchedPage
from agents.context.tools import fetch_page, increment, url_allowed


_REQUEST_FETCH_LIMIT = 5  # spec §6.8


def node_tier2_fetch_pages(state: ContextState) -> dict[str, Any]:
    """이번 라운드 검색 결과의 URL 들을 fetch 해서 fetched_pages 에 append."""
    results = (state.tier2_meta or {}).get("last_search_results") or []
    new_pages: list[FetchedPage] = []
    new_warnings: list[str] = []
    fetch_calls_used = state.fetch_calls

    for item in results:
        if fetch_calls_used >= _REQUEST_FETCH_LIMIT:
            new_warnings.append("tier2_fetch_request_limit")
            break
        url = item.get("url") if isinstance(item, dict) else None
        if not url:
            continue
        # 화이트리스트 재검증 (Tavily 결과가 우회됐을 가능성 방어).
        if not url_allowed(url):
            new_warnings.append(f"tier2_fetch_skip_not_whitelisted: {url}")
            continue
        body, warn = fetch_page(url)
        increment("fetch_calls")
        fetch_calls_used += 1
        if warn:
            new_warnings.append(warn)
        if body:
            partial = bool(warn and "fetch_partial" in warn)
            try:
                new_pages.append(
                    FetchedPage(
                        url=url,
                        body=body,
                        fetched_at=datetime.now(timezone.utc),
                        partial=partial,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - URL 타입 변환 등 방어
                new_warnings.append(
                    f"tier2_fetch_page_invalid: {type(exc).__name__}: {exc}"
                )

    return {
        "fetched_pages": state.fetched_pages + new_pages,
        "fetch_calls": fetch_calls_used,
        "warnings": state.warnings + new_warnings,
    }
