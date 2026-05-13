"""
Tavily Web Search 도구.

스펙 §6.2 의 ``web_search`` 도구 구현. raw ``TavilyClient`` 를 사용하고 LangChain
wrapper 는 거치지 않음 — langchain 의 Tavily integration 은 버전별 schema 차이가
있어 SDK 직접 호출이 안정적.

설계:
- API 키는 ``TAVILY_API_KEY`` env 에서 읽음. 누락 시 warning 반환 (예외 X).
- include_domains 에 ``whitelist.ALLOWED_DOMAINS`` 를 주입해 Tavily 측에서도
  필터링하고, 후처리에서 한 번 더 ``url_allowed`` 로 검증.
- 모든 도구 함수와 마찬가지로 예외를 raise 하지 않고 ``(results, warning)`` tuple.
"""
from __future__ import annotations

import os
from typing import Optional

from .whitelist import ALLOWED_DOMAINS, url_allowed

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover - 의존성 미설치 시 import-time guard
    TavilyClient = None  # type: ignore[assignment, misc]


def search(
    query: str,
    max_results: int = 5,
) -> tuple[Optional[list[dict]], Optional[str]]:
    """단일 쿼리에 대해 Tavily 검색을 수행하고 화이트리스트 필터링한 결과를 반환.

    Returns:
        ``(results, warning)``:
            - results: 각 dict 는 최소 ``{"url", "title", "content"}`` 키 보유.
              실패 시 ``None``.
            - warning: 실패 또는 빈 결과 사유. 정상 시 ``None``.
    """
    if TavilyClient is None:
        return None, "tavily_not_installed: pip install tavily-python"
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None, "tavily_missing_api_key: TAVILY_API_KEY env not set"

    client = TavilyClient(api_key=api_key)
    try:
        resp = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_domains=list(ALLOWED_DOMAINS),
        )
    except Exception as exc:  # noqa: BLE001 — Tavily SDK 다양한 예외를 일률 catch
        return None, f"tavily_error: {type(exc).__name__}: {exc}"

    raw_results = resp.get("results", []) if isinstance(resp, dict) else []
    # 후처리 검증: Tavily 가 include_domains 를 honor 못한 경우 대비.
    filtered: list[dict] = []
    for item in raw_results:
        url = item.get("url") if isinstance(item, dict) else None
        if url and url_allowed(url):
            filtered.append(item)
    if not filtered:
        return [], "tavily_no_whitelisted_results"
    return filtered, None
