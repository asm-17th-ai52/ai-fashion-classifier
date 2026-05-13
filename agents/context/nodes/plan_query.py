"""
Tier-2 ReAct: 검색 쿼리 생성 노드 (spec §6.4).

LLM 에 자유 작문을 맡기지 않고 4 개 템플릿 슬롯 채우기로 강제. 성공 시
``state.search_queries_used`` 에 새 쿼리를 append 하고 ``react_step`` 을 1 증가.
실패 / 중복 쿼리 / 빈 결과는 warnings 추가만 한다 (raise X).
"""
from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from agents.context.prompts import PLANNER_SYSTEM, build_planner_user
from agents.context.state import ContextState
from agents.vision.nodes.step1_nodes import GEMINI_MODEL


# spec §6.4 의 4 템플릿. 인덱스로 LLM 출력과 매칭.
TEMPLATES: tuple[str, ...] = (
    "한국 {event_type} 드레스코드",
    "{event_type} 복장 가이드 한국",
    "{event_type} {season} 옷차림",
    "{event_type} 추천 복장",
)


class _PlanQueryOutput(BaseModel):
    """Planner LLM 의 structured output schema.

    google-genai 호환:
    - ``extra="forbid"`` 미설정 — Pydantic 이 ``additionalProperties: false`` 를
      생성하면 Gemini API 가 INVALID_ARGUMENT 로 거절한다.
    - ``Optional[str]`` 대신 ``str`` 로 통일하고 LLM 이 빈 문자열을 채우게 한다
      (nullable schema 또한 일부 SDK 버전에서 비호환).
    """

    template_id: int
    event_type: str
    season: str  # 템플릿 2 미선택 시 LLM 이 빈 문자열 "" 채움.
    reasoning: str


def _build_client() -> genai.Client:
    """Vision 의 ``_build_client`` 를 사용해도 되지만, 본 함수는 import 사이드이펙트
    회피용 로컬 사본. ``GOOGLE_API_KEY`` 미설정 시 ``EnvironmentError`` raise.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


def _format_template(template_id: int, event_type: str, season: str) -> str:
    """템플릿 인덱스 + 슬롯 값으로 최종 쿼리 문자열 생성."""
    tpl = TEMPLATES[template_id]
    # 연속된 공백을 정리해 빈 ``{season}`` 슬롯의 흔적 제거.
    raw = tpl.format(event_type=event_type, season=season or "")
    return " ".join(raw.split())


def node_tier2_plan_query(state: ContextState) -> dict:
    """LangGraph 노드: 다음 검색 쿼리 1 개를 생성해 state 에 누적."""
    # ReAct step 증가는 본 노드 진입 시점에만 일어난다 (spec §6.2 의 step 카운터).
    next_step = state.react_step + 1
    warnings: list[str] = []

    try:
        client = _build_client()
    except EnvironmentError as exc:
        # API 키 미설정은 본 노드에서 fail-soft — Tier-2 전체가 abort 됐어야 하지만
        # 그래프 조립 (PR-E) 단계의 책임. 본 노드는 warning + step 만 증가.
        warnings.append(f"plan_query_no_api_key: {exc}")
        return {
            "react_step": next_step,
            "warnings": state.warnings + warnings,
        }

    # 이미 fetch 한 페이지 요약 (제목 + 도메인) 생성 — LLM 이 중복 쿼리 회피하도록.
    fetched_summaries: list[str] = []
    for page in state.fetched_pages[-5:]:
        url_str = str(page.url)
        fetched_summaries.append(url_str)

    user_msg = build_planner_user(
        event_type=state.request.event_type,
        used_queries=list(state.search_queries_used),
        fetched_summaries=fetched_summaries,
    )
    contents = [
        types.Content(parts=[types.Part(text=f"{PLANNER_SYSTEM}\n\n{user_msg}")]),
    ]
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_PlanQueryOutput,
        temperature=0,
    )

    plan: Optional[_PlanQueryOutput] = None
    for attempt in range(2):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config
            )
            plan = _PlanQueryOutput.model_validate_json(resp.text)
            break
        except Exception as exc:  # noqa: BLE001 — 네트워크/스키마 양쪽 방어
            if attempt == 1:
                warnings.append(f"plan_query_llm_failed: {type(exc).__name__}: {exc}")

    if plan is None:
        return {
            "react_step": next_step,
            "warnings": state.warnings + warnings,
        }

    # template_id clamp — LLM 이 4 미만 정수를 보장하지 못해도 안전.
    tpl_id = max(0, min(plan.template_id, len(TEMPLATES) - 1))
    query = _format_template(tpl_id, plan.event_type, plan.season).strip()

    # 빈 쿼리 / 중복 쿼리 방어.
    if not query:
        warnings.append("plan_query_empty_query")
        return {
            "react_step": next_step,
            "warnings": state.warnings + warnings,
        }
    if query in state.search_queries_used:
        warnings.append(f"plan_query_duplicate: {query}")
        return {
            "react_step": next_step,
            "warnings": state.warnings + warnings,
        }

    return {
        "search_queries_used": state.search_queries_used + [query],
        "react_step": next_step,
        "warnings": state.warnings + warnings,
    }
