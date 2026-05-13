"""
Context Agent §4.1 금지어 — Recommendation 기본 리스트 + Context 특화 확장.

``agents/recommendation/narrator.py::FORBIDDEN_TERMS`` 는 미용 평가 (매력/호감/세련 등)
중심. Context Agent 의 Tier-2 extract_facts 는 외부 본문에서 인용을 가져오므로
스펙 §08 §4.1 의 추가 단어 (체형/몸매/나이/평범 등) 도 함께 걸러야 한다.

본 리스트는 ``extract_facts._quotes_contain_forbidden`` 의 단순 substring 매칭에
사용된다. 정량/enum 필드 (formality range, categories, color_guidance) 는 schema
제약상 자유 문장이 아니므로 본 리스트 검사 대상에서 제외.

False-positive 회피 트레이드오프:
- ``"키"`` 같은 짧은 단어는 의도와 무관한 토큰 (예: ‘면접 시기’) 까지 매칭 → 제외.
- ``"나이"`` / ``"연령"`` / ``"성별"`` 도 한국어 본문에 광범위 등장 (‘브랜드 연령대’,
  ‘성별 기준 추천’ 등) → 본 리스트에서 제외하고 LLM prompt 단계에서 차단.
- ``"마른 체"`` / ``"통통한"`` / ``"평범한"`` 같이 체형 의미가 명확한 N-gram 선호.
- 성별 직접 묘사는 ``"남성"`` / ``"여성"`` 두 토큰으로 차단 (Vision Agent 의
  gender-inference 금지 정책과 정렬).
"""
from __future__ import annotations

from agents.recommendation.narrator import FORBIDDEN_TERMS


# spec §08 §4.1 의 Context 특화 추가 단어 — narrator 기본 리스트에 빠진 항목.
# 단어 선정은 false-positive 와 안전망 폭의 균형 (lead 의 PR-D 회송 가이드 그대로).
_CONTEXT_ONLY: tuple[str, ...] = (
    "잘생",
    "잘생긴",
    "체형",
    "몸매",
    "마른 체",  # ‘마른’ 단독은 ‘마른 빵/화’ 등 무관 매칭 → N-gram 으로 제한.
    "통통한",
    "슬림한",  # 체형 의미일 때만 — 의류 ‘슬림 핏’ 은 일반적 별도 표기 (‘슬림핏’) 라 안전.
    "남성",
    "여성",
    "평범한",
)


CONTEXT_FORBIDDEN_TERMS: tuple[str, ...] = tuple(FORBIDDEN_TERMS) + _CONTEXT_ONLY
