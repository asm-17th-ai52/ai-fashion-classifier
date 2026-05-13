"""
Context Agent §4.1 금지어 — Recommendation 기본 리스트 + Context 특화 확장.

``agents/recommendation/narrator.py::FORBIDDEN_TERMS`` 는 미용 평가 (매력/호감/세련 등)
중심. Context Agent 의 Tier-2 extract_facts 는 외부 본문에서 인용을 가져오므로
스펙 §08 §4.1 의 추가 단어 (체형/나이/성별/평범 등) 도 함께 걸러야 한다.

본 리스트는 ``extract_facts._quotes_contain_forbidden`` 의 단순 substring 매칭에
사용된다. 정량/enum 필드 (formality range, categories, color_guidance) 는 schema
제약상 자유 문장이 아니므로 본 리스트 검사 대상에서 제외.
"""
from __future__ import annotations

from agents.recommendation.narrator import FORBIDDEN_TERMS


# spec §08 §4.1 의 Context 특화 추가 단어 — narrator 기본 리스트에 빠진 항목.
_CONTEXT_ONLY: tuple[str, ...] = (
    "잘생",
    "체형",
    "몸매",
    "마른",
    "통통",
    "슬림한",  # ‘체형 의미일 때’ — 정합성 위해 substring 매칭으로 보수적 차단.
    "나이",
    "연령",
    "성별",
    "평범",
)


CONTEXT_FORBIDDEN_TERMS: tuple[str, ...] = tuple(FORBIDDEN_TERMS) + _CONTEXT_ONLY
