"""
Context Agent에서 사용하는 LangGraph 상태(State) 및 보조 데이터 모델 정의.

이 파일은 ``docs/specs/03-agent-context-spec.md`` §6.5 / §10.1을 그대로 옮긴 것이다.

- ``FetchedPage``: Tier-2 web fetch 결과 1개.
- ``ExtractedFacts``: LLM이 본문에서 정량 schema로 추출한 facts 1개 (소스별 1건).
- ``ContextState``: LangGraph sub-graph가 공유하는 전체 상태.

google-genai schema 제약(랜드마인)
---------------------------------
Vision Agent에서 학습한 교훈: google-genai의 structured output은 다음을 지원하지 않는다.

- ``dict[str, Any]`` (구조 없는 dict)
- ``set``
- 단일 값 ``Literal`` (e.g., ``Literal["interview"]``)
- 필드 기본값 (defaults)

본 파일의 Pydantic 모델 중 LLM structured output에 직접 노출되는 것은
``ExtractedFacts`` 와 그 하위 모델이다. 따라서 그쪽에는 위 제약을 지키고,
``@field_validator`` 로 제약(범위/길이)을 표현한다.

``ContextState`` 자체는 LangGraph 내부 state이므로 default 사용이 자유롭다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

# 외부에 노출되는 응답 schema는 backend에 이미 정의되어 있다.
# 본 Agent는 동일 schema 인스턴스를 다시 정의하지 않고 그대로 import한다.
# (07-data-contracts.md §3 단일 출처 유지.)
from app.schemas.context import DressCode, EvidenceQuote
from app.schemas.session import SessionCreateRequest


class FetchedPage(BaseModel):
    """
    Tier-2 ReAct 루프에서 ``fetch_page`` 도구가 가져온 본문 1건.

    ``partial=True`` 는 50KB 본문 cap (spec §6.2) 에 걸려 잘렸음을 의미한다.
    이 경우에도 본문 앞부분은 LLM에 전달되지만, ``evidence_quotes`` 가 본문
    뒷부분에서 인용되었을 수 있으므로 ``extract_facts`` 단계에서 주의해야 한다.
    """

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    body: str
    fetched_at: datetime
    partial: bool = False


class ExtractedFactsExpectedCategories(BaseModel):
    """``ExtractedFacts.expected_categories`` 의 내부 schema.

    LLM structured output에 그대로 노출되므로 default 사용을 피한다.
    값은 ``agents/vision/tools/color_lookup.py`` 의 한글 카테고리 vocab을 따른다.
    """

    model_config = ConfigDict(extra="forbid")

    top: list[str]
    bottom: list[str]
    outer: list[str]
    shoes: list[str]


class ExtractedFactsColorGuidance(BaseModel):
    """``ExtractedFacts.color_guidance`` 의 내부 schema."""

    model_config = ConfigDict(extra="forbid")

    preferred_tones: list[str]
    avoid_tones: list[str]


class ExtractedFacts(BaseModel):
    """
    Tier-2의 ``tier2_extract_facts`` 노드가 단일 fetched_page에서 추출한 facts.

    spec §6.5 schema 그대로:

    .. code-block:: json

       {
         "expected_formality_range": [0~100, 0~100],
         "expected_categories": {"top": [...], "bottom": [...], ...},
         "color_guidance": {"preferred_tones": [...], "avoid_tones": [...]},
         "evidence_quotes": [{"url": "...", "quote": "...", "fetched_at": "..."}],
         "extraction_confidence": 0.0~1.0
       }

    제약:
      - ``extraction_confidence < 0.5`` 면 ``tier2_consensus`` 노드가 폐기한다 (spec §6.5).
      - ``expected_formality_range`` 는 정확히 길이 2, 각 0~100, min ≤ max.

    google-genai schema 호환:
      - 모든 필드는 default 없이 필수 입력 (LLM이 반드시 채움).
      - dict[str, Any] / set / 단일 Literal 사용 금지.
    """

    model_config = ConfigDict(extra="forbid")

    expected_formality_range: list[int] = Field(
        ...,
        description="격식 점수 [min, max], 각 0-100. 정확히 길이 2.",
    )
    expected_categories: ExtractedFactsExpectedCategories
    color_guidance: ExtractedFactsColorGuidance
    evidence_quotes: list[EvidenceQuote]
    extraction_confidence: float = Field(
        ...,
        description="LLM이 본문에서 정량 schema를 얼마나 확신했는지 (0.0-1.0).",
    )

    @field_validator("expected_formality_range")
    @classmethod
    def _validate_formality_range(cls, v: list[int]) -> list[int]:
        if len(v) != 2:
            raise ValueError(
                f"expected_formality_range must have length 2, got {len(v)}"
            )
        low, high = v
        if not (0 <= low <= 100 and 0 <= high <= 100):
            raise ValueError(
                f"expected_formality_range values must be 0-100, got [{low}, {high}]"
            )
        if low > high:
            raise ValueError(
                f"expected_formality_range min({low}) must be ≤ max({high})"
            )
        return v

    @field_validator("extraction_confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"extraction_confidence must be 0.0-1.0, got {v}")
        return v


class ContextState(BaseModel):
    """
    Context Agent LangGraph sub-graph가 공유하는 전체 상태.

    spec §10.1을 그대로 옮긴 구조이며, Tier-1/Tier-2 분기와 ReAct 루프의 모든
    중간 산출물이 이 state에 누적된다. LangGraph는 각 노드 return dict의 키만
    덮어쓰므로, default 가 있는 필드는 노드가 건너뛰어도 안전하다.

    Tier-2 budget counter (``web_search_calls`` / ``fetch_calls``) 는 spec §6.8의
    회당 호출 상한 (search 3회, fetch 5회) 을 노드 안에서 결정적으로 검사할 수
    있도록 state에 보관한다.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ── 입력 ────────────────────────────────────────────────────
    request: SessionCreateRequest

    # ── Tier-1 결과 ─────────────────────────────────────────────
    tier1_result: Optional[DressCode] = None
    tier1_score: float = 0.0

    # ── Tier-2 ReAct 상태 ───────────────────────────────────────
    react_step: int = 0
    search_queries_used: list[str] = Field(default_factory=list)
    fetched_pages: list[FetchedPage] = Field(default_factory=list)
    extracted_facts_per_source: list[ExtractedFacts] = Field(default_factory=list)
    tier2_consensus: Optional[DressCode] = None
    tier2_meta: dict[str, Any] = Field(default_factory=dict)

    # Tier-2 비용/속도 카운터 (spec §6.8)
    web_search_calls: int = 0
    fetch_calls: int = 0

    # ── 최종 산출 ───────────────────────────────────────────────
    dress_code: Optional[DressCode] = None
    warnings: list[str] = Field(default_factory=list)
