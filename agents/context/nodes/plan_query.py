"""
Tier-2 ReAct: 검색 쿼리 생성 노드 (spec §6.4).

LLM 에 자유 작문을 맡기지 않고 4 개 템플릿 슬롯 채우기로 강제. ``react_step`` 은
**본 노드 진입 시점에 항상 +1** (성공/실패 path 모두 동일) — 무한 루프 방지.
실패 / 중복 쿼리 / 빈 결과는 warnings 추가만 한다 (raise X).
"""
from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlparse

from google.genai import types
from pydantic import BaseModel, ValidationError

from agents.context.nodes._constants import RECENT_PAGES
from agents.context.prompts import PLANNER_SYSTEM, build_planner_user
from agents.context.state import ContextState
from agents.vision.nodes.step1_nodes import GEMINI_MODEL, _build_client


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


def _format_template(template_id: int, event_type: str, season: str) -> str:
    """템플릿 인덱스 + 슬롯 값으로 최종 쿼리 문자열 생성."""
    tpl = TEMPLATES[template_id]
    # 연속된 공백을 정리해 빈 ``{season}`` 슬롯의 흔적 제거.
    raw = tpl.format(event_type=event_type, season=season or "")
    return " ".join(raw.split())


def _summarize_fetched_pages(state: ContextState) -> list[str]:
    """LLM 이 중복/유사 쿼리를 피하도록 최근 페이지 요약 — domain + 본문 첫줄 80자."""
    summaries: list[str] = []
    for page in state.fetched_pages[-RECENT_PAGES:]:
        url_str = str(page.url)
        # ``urlparse`` 는 str 입력 시 raise 하지 않음 — defensive try/except 제거.
        domain = urlparse(url_str).hostname or ""
        first_line = (page.body or "").strip().splitlines()[:1]
        snippet = first_line[0][:80] if first_line else ""
        summaries.append(f"{domain} | {snippet}".strip(" |"))
    return summaries


def node_tier2_plan_query(state: ContextState) -> dict:
    """LangGraph 노드: 다음 검색 쿼리 1 개를 생성해 state 에 누적."""
    next_step = state.react_step + 1
    warnings: list[str] = []

    try:
        client = _build_client()
    except EnvironmentError as exc:
        # API 키 미설정은 fail-soft — warning + step 만 증가하고 routing 은 그래프가 결정.
        warnings.append(f"plan_query_no_api_key: {exc}")
        return {
            "react_step": next_step,
            "warnings": state.warnings + warnings,
        }

    user_msg = build_planner_user(
        event_type=state.request.event_type,
        used_queries=list(state.search_queries_used),
        fetched_summaries=_summarize_fetched_pages(state),
    )
    # 시스템 룰은 system_instruction 슬롯에 분리 (인젝션 안전).
    contents = [types.Content(parts=[types.Part(text=user_msg)])]
    config = types.GenerateContentConfig(
        system_instruction=PLANNER_SYSTEM,
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
        except (ValidationError, json.JSONDecodeError) as exc:
            if attempt == 1:
                warnings.append(
                    f"plan_query_validation: {type(exc).__name__}: {str(exc)[:200]}"
                )
        except Exception as exc:  # noqa: BLE001 — Gemini SDK 네트워크/quota 에러 catch
            if attempt == 1:
                warnings.append(
                    f"plan_query_llm_failed: {type(exc).__name__}: {str(exc)[:200]}"
                )

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
