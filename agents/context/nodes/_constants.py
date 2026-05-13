"""Tier-2 노드 공용 상수.

여러 노드에서 같은 값을 사용해 drift 가 일어나지 않도록 단일 정의.
"""
from __future__ import annotations


# spec §6.8: fetch_calls 회당 5 회 상한 → ReAct 라운드별 최대 5 페이지 처리.
# plan_query 가 LLM 에 노출하는 ‘최근 페이지 요약’ 개수와 extract_facts 가 처리하는
# ‘이번 라운드 fetched_pages’ 개수가 동일해야 한다.
RECENT_PAGES: int = 5
