"""
Tier-2 ReAct: page body → ExtractedFacts schema 추출 노드 (spec §6.5).

LLM 에 structured output schema 를 강제하고, 추출 결과의 ``evidence_quotes`` 에
§4.1 금지어가 들어가면 해당 facts 를 폐기한다. ``extraction_confidence < 0.5``
도 폐기. 이 단계가 Tier-2 의 환각 차단 핵심 게이트.
"""
from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from agents.context.prompts import EXTRACTOR_SYSTEM, build_extractor_user
from agents.context.state import ContextState, ExtractedFacts, FetchedPage
from agents.recommendation.narrator import FORBIDDEN_TERMS
from agents.vision.nodes.step1_nodes import GEMINI_MODEL


# ---------------------------------------------------------------------------
# Gemini-호환 sibling schema for ExtractedFacts (PR-A 의 정식 schema 는 ``extra="forbid"``
# 가 설정돼 있어 ``additionalProperties: false`` 를 생성 → google-genai SDK 가
# INVALID_ARGUMENT 로 거절. 본 sibling 은 LLM 입력용으로만 사용하고, validate 후
# PR-A 의 정식 ``ExtractedFacts`` 로 재구성한다 (validator 가 그대로 실행됨).
# ---------------------------------------------------------------------------


class _ExtractedCategoriesLLM(BaseModel):
    top: list[str]
    bottom: list[str]
    outer: list[str]
    shoes: list[str]


class _ColorGuidanceLLM(BaseModel):
    preferred_tones: list[str]
    avoid_tones: list[str]


class _EvidenceQuoteLLM(BaseModel):
    url: str
    quote: str
    fetched_at: str  # ISO datetime — ExtractedFacts 재구성 시 datetime 으로 파싱.


class _ExtractedFactsLLM(BaseModel):
    """LLM 출력용 sibling. Pydantic ``model_config`` 미설정으로 google-genai 호환."""

    expected_formality_range: list[int]
    expected_categories: _ExtractedCategoriesLLM
    color_guidance: _ColorGuidanceLLM
    evidence_quotes: list[_EvidenceQuoteLLM]
    extraction_confidence: float


# extract_facts 가 LLM 에 전달하는 본문 최대 길이. PR-C `fetch.py` 의 ``MAX_BODY_BYTES``
# 와 동일 보호 라인 — fetch 단계에서 50KB 트림됐어도 한 번 더 안전망.
_MAX_BODY_CHARS = 50_000

# 이번 ReAct 라운드에서 처리할 fetched_pages 수. spec §6.8 의 search 3 회 × fetch 5 회
# 중 최근 라운드 = 마지막 fetch 5 건. plan_query 가 매 라운드 1 검색 → fetch 가 평균
# 3~5 페이지이므로 5 가 합리적 상한.
_RECENT_PAGES = 5


def _build_client() -> genai.Client:
    """``GOOGLE_API_KEY`` 미설정 시 ``EnvironmentError`` raise."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


def _quotes_contain_forbidden(facts: ExtractedFacts) -> bool:
    """``evidence_quotes`` 의 어떤 인용에 §4.1 금지어가 포함됐는지 검사.

    enum / numeric 필드 (categories, color_guidance, formality_range) 는 schema 제약상
    한국어 자유 문장이 아니므로 검사 대상에서 제외.
    """
    joined = " ".join(q.quote for q in facts.evidence_quotes)
    return any(term in joined for term in FORBIDDEN_TERMS)


def _llm_to_facts(llm: _ExtractedFactsLLM) -> ExtractedFacts:
    """LLM sibling → PR-A 의 정식 ``ExtractedFacts`` 재구성 (validator 재실행).

    ``EvidenceQuote.url`` 은 ``HttpUrl`` 이고 ``fetched_at`` 은 datetime 이라
    Pydantic 이 ISO 문자열을 자동 coerce. raw dict 로 넘기면 정상 검증된다.
    """
    return ExtractedFacts.model_validate({
        "expected_formality_range": llm.expected_formality_range,
        "expected_categories": llm.expected_categories.model_dump(),
        "color_guidance": llm.color_guidance.model_dump(),
        "evidence_quotes": [q.model_dump() for q in llm.evidence_quotes],
        "extraction_confidence": llm.extraction_confidence,
    })


def _extract_single_page(
    client: genai.Client,
    page: FetchedPage,
    event_type: str,
    config: types.GenerateContentConfig,
) -> tuple[Optional[ExtractedFacts], Optional[str]]:
    """단일 ``FetchedPage`` 에 대한 LLM 호출 + 검증. ``(facts, warning)`` 반환."""
    body = page.body[:_MAX_BODY_CHARS]
    user_msg = build_extractor_user(
        event_type=event_type,
        url=str(page.url),
        fetched_at_iso=page.fetched_at.isoformat(),
        body=body,
    )
    contents = [
        types.Content(parts=[types.Part(text=f"{EXTRACTOR_SYSTEM}\n\n{user_msg}")]),
    ]

    for attempt in range(2):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config
            )
            llm_out = _ExtractedFactsLLM.model_validate_json(resp.text)
            return _llm_to_facts(llm_out), None
        except Exception as exc:  # noqa: BLE001 — 네트워크/스키마/validator 모두 방어
            if attempt == 1:
                return None, f"extract_facts_llm_failed: {type(exc).__name__}: {exc}"
    return None, "extract_facts_llm_failed: exhausted retries"


def node_tier2_extract_facts(state: ContextState) -> dict:
    """LangGraph 노드: 이번 라운드 fetched_pages 에서 facts 추출 → state 누적."""
    warnings: list[str] = []
    try:
        client = _build_client()
    except EnvironmentError as exc:
        warnings.append(f"extract_facts_no_api_key: {exc}")
        return {"warnings": state.warnings + warnings}

    # google-genai 호환 sibling 사용 — 출력 후 정식 ExtractedFacts 로 재구성.
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_ExtractedFactsLLM,
        temperature=0,
    )

    new_facts: list[ExtractedFacts] = []
    for page in state.fetched_pages[-_RECENT_PAGES:]:
        facts, warn = _extract_single_page(client, page, state.request.event_type, config)
        if warn:
            warnings.append(warn)
            continue
        if facts is None:
            continue
        # spec §6.5: 신뢰도 0.5 미만 폐기.
        if facts.extraction_confidence < 0.5:
            warnings.append(
                f"extract_facts_low_confidence: {facts.extraction_confidence:.2f}"
            )
            continue
        # §4.1 금지어 포함 인용 폐기 — 정량 필드는 schema 제약상 안전.
        if _quotes_contain_forbidden(facts):
            warnings.append("extract_facts_forbidden_term_in_quotes")
            continue
        new_facts.append(facts)

    return {
        "extracted_facts_per_source": state.extracted_facts_per_source + new_facts,
        "warnings": state.warnings + warnings,
    }
