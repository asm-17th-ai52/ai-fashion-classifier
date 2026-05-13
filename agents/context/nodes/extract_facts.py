"""
Tier-2 ReAct: page body → ExtractedFacts schema 추출 노드 (spec §6.5).

LLM 에 structured output schema 를 강제하고, 추출된 facts 의 모든 free-form
문자열 필드 (``evidence_quotes`` / ``expected_categories`` / ``color_guidance``)
에 §4.1 금지어가 포함되면 해당 facts 를 폐기한다. ``extraction_confidence < 0.5``
도 폐기. 이 단계가 Tier-2 의 환각 + 인젝션 차단 핵심 게이트.
"""
from __future__ import annotations

import json
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from agents.context.forbidden_terms import (
    CONTEXT_FORBIDDEN_TERMS,
    normalize_for_filter,
)
from agents.context.nodes._constants import RECENT_PAGES
from agents.context.prompts import EXTRACTOR_SYSTEM, build_extractor_user
from agents.context.state import ContextState, ExtractedFacts, FetchedPage
from agents.vision.nodes.step1_nodes import GEMINI_MODEL, _build_client


# ---------------------------------------------------------------------------
# Gemini-호환 sibling schema for ExtractedFacts: ``state.ExtractedFacts`` 는
# ``ConfigDict(extra="forbid")`` 가 설정돼 있어 ``additionalProperties: false`` 를
# 생성 → google-genai SDK 가 INVALID_ARGUMENT 로 거절한다. 본 sibling 은 LLM 응답
# 수신용으로만 사용하고 validate 후 정식 ``ExtractedFacts`` 로 재구성한다 (validator 재실행).
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
    # 정식 ``EvidenceQuote.quote`` 는 ``max_length=500``. LLM 이 가끔 초과 출력해도
    # 사일런트 폐기되지 않도록 sibling 은 더 넉넉히 받고 ``_llm_to_facts`` 에서 트림.
    quote: str = Field(..., max_length=2000)
    fetched_at: str  # ISO datetime — 재구성 시 datetime 으로 파싱.


class _ExtractedFactsLLM(BaseModel):
    """LLM 출력용 sibling. Pydantic ``model_config`` 미설정으로 google-genai 호환."""

    expected_formality_range: list[int]
    expected_categories: _ExtractedCategoriesLLM
    color_guidance: _ColorGuidanceLLM
    # 빈 quotes → forbidden filter 가 vacuously pass 되고 audit trail 소실. 최소 1개 강제.
    evidence_quotes: list[_EvidenceQuoteLLM] = Field(..., min_length=1)
    extraction_confidence: float


# Drift guard — sibling 과 canonical 필드명 불일치를 import-time 에 감지.
_SIBLING_FIELDS = set(_ExtractedFactsLLM.model_fields.keys())
_CANONICAL_FIELDS = set(ExtractedFacts.model_fields.keys())
if _SIBLING_FIELDS != _CANONICAL_FIELDS:  # pragma: no cover - 빌드 단계 가드
    raise AssertionError(
        "_ExtractedFactsLLM ↔ ExtractedFacts field drift: "
        f"{_SIBLING_FIELDS.symmetric_difference(_CANONICAL_FIELDS)}"
    )


# LLM 입력 본문 최대 길이. fetch 단계 (``tools/fetch.py``) 의 ``MAX_BODY_BYTES`` 와
# 동일 보호 라인 — fetch 가 트림했어도 한 번 더 안전망.
_MAX_BODY_CHARS = 50_000

# 정식 ``EvidenceQuote.quote`` 길이 상한 (재구성 시 트림 기준).
_QUOTE_MAX_CHARS = 500


def _facts_contain_forbidden(facts: _ExtractedFactsLLM) -> tuple[bool, Optional[str]]:
    """모든 free-form string 필드에서 §4.1 금지어 존재 여부 검사.

    검사 대상:
    - ``evidence_quotes[].quote``
    - ``expected_categories.{top,bottom,outer,shoes}`` (LLM 이 vocab 밖 한국어 문장을
      넣어 인젝션 시도 가능)
    - ``color_guidance.{preferred_tones, avoid_tones}`` (동일)

    매칭 양쪽 (text + term) 을 NFC 정규화 + 공백 제거 + 소문자로 normalize 한 뒤
    substring 검사 — "체-형", "체 형" 같은 분해 우회 차단.
    """
    sources: list[tuple[str, str]] = []
    for q in facts.evidence_quotes:
        sources.append(("evidence_quote", q.quote))
    for slot in ("top", "bottom", "outer", "shoes"):
        for cat in getattr(facts.expected_categories, slot):
            sources.append((f"category_{slot}", cat))
    for tone in facts.color_guidance.preferred_tones:
        sources.append(("color_preferred", tone))
    for tone in facts.color_guidance.avoid_tones:
        sources.append(("color_avoid", tone))

    normalized_terms = [(t, normalize_for_filter(t)) for t in CONTEXT_FORBIDDEN_TERMS]
    for source_label, text in sources:
        norm = normalize_for_filter(text)
        if not norm:
            continue
        for term, norm_term in normalized_terms:
            if norm_term and norm_term in norm:
                return True, f"forbidden_in_{source_label}: {term}"
    return False, None


def _llm_to_facts(llm: _ExtractedFactsLLM) -> ExtractedFacts:
    """LLM sibling → 정식 ``ExtractedFacts`` 재구성 (validator 재실행).

    ``EvidenceQuote.quote`` 의 ``max_length=500`` 위반 회피를 위해 인용을 500자로 트림.
    """
    quotes_payload = []
    for q in llm.evidence_quotes:
        quote_text = q.quote if len(q.quote) <= _QUOTE_MAX_CHARS else q.quote[:_QUOTE_MAX_CHARS]
        quotes_payload.append({
            "url": q.url,
            "quote": quote_text,
            "fetched_at": q.fetched_at,
        })
    return ExtractedFacts.model_validate({
        "expected_formality_range": llm.expected_formality_range,
        "expected_categories": llm.expected_categories.model_dump(),
        "color_guidance": llm.color_guidance.model_dump(),
        "evidence_quotes": quotes_payload,
        "extraction_confidence": llm.extraction_confidence,
    })


def _extract_single_page(
    client: genai.Client,
    page: FetchedPage,
    event_type: str,
    config: types.GenerateContentConfig,
) -> tuple[Optional[_ExtractedFactsLLM], Optional[str]]:
    """단일 ``FetchedPage`` 에 대한 LLM 호출 + validate. ``(sibling_facts, warning)`` 반환.

    인젝션/금지어 필터는 호출 측에서 sibling 단계에 수행해 정량 필드까지 검사.
    """
    body = page.body[:_MAX_BODY_CHARS]
    user_msg = build_extractor_user(
        event_type=event_type,
        url=str(page.url),
        fetched_at_iso=page.fetched_at.isoformat(),
        body=body,
    )
    # system_instruction 분리 — 페이지 본문이 LLM 시스템 룰과 동급으로 들어가 last-
    # instruction-wins 인젝션이 일어나지 않도록.
    contents = [types.Content(parts=[types.Part(text=user_msg)])]

    for attempt in range(2):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config
            )
            return _ExtractedFactsLLM.model_validate_json(resp.text), None
        except (ValidationError, json.JSONDecodeError) as exc:
            # schema 위반 / JSON 파싱 실패 — retry 가능.
            if attempt == 1:
                return None, f"extract_facts_validation: {type(exc).__name__}: {str(exc)[:200]}"
        except Exception as exc:  # noqa: BLE001 — Gemini SDK 네트워크/quota 에러 catch
            # 코드 버그 (AttributeError 등) 는 retry 후에도 동일하게 실패 → 같은 path.
            if attempt == 1:
                return None, f"extract_facts_llm_failed: {type(exc).__name__}: {str(exc)[:200]}"
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
    # 시스템 룰은 system_instruction 슬롯에 분리 (인젝션 안전).
    config = types.GenerateContentConfig(
        system_instruction=EXTRACTOR_SYSTEM,
        response_mime_type="application/json",
        response_schema=_ExtractedFactsLLM,
        temperature=0,
    )

    new_facts: list[ExtractedFacts] = []
    for page in state.fetched_pages[-RECENT_PAGES:]:
        sibling, warn = _extract_single_page(client, page, state.request.event_type, config)
        if warn:
            warnings.append(warn)
            continue
        if sibling is None:
            continue
        # spec §6.5: 신뢰도 0.5 미만 폐기.
        if sibling.extraction_confidence < 0.5:
            warnings.append(
                f"extract_facts_low_confidence: {sibling.extraction_confidence:.2f}"
            )
            continue
        # §4.1 금지어 필터 — quotes + categories + colors 모두 검사.
        forbidden, source = _facts_contain_forbidden(sibling)
        if forbidden:
            warnings.append(f"extract_facts_forbidden_term: {source}")
            continue
        try:
            new_facts.append(_llm_to_facts(sibling))
        except ValidationError as exc:
            # 정식 schema 의 range/length validator 위반 (sibling 은 통과한 경우).
            warnings.append(f"extract_facts_canonical_validate: {str(exc)[:200]}")

    return {
        "extracted_facts_per_source": state.extracted_facts_per_source + new_facts,
        "warnings": state.warnings + warnings,
    }
