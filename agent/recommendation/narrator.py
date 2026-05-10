import json
import os
import re
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from .schemas import CheckResult, Score, Suggestion


FORBIDDEN_TERMS = [
    "매력",
    "호감",
    "인상",
    "성격",
    "어울리는 사람",
    "멋지",
    "예쁘",
    "세련",
    "촌스러",
    "신뢰감",
]

SYSTEM_PROMPT = """
You receive a deterministic outfit evaluation: scores, failed checks
(with evidence facts), and pre-computed suggestions (with actions and
expected deltas).

Your job: phrase explanations and suggestion texts in Korean using ONLY
the provided facts and numbers. Do NOT invent numbers, do NOT add
aesthetic judgments.

FORBIDDEN words: 매력, 호감, 인상, 성격, 어울리는 사람, 멋지, 예쁘,
세련, 촌스러, 신뢰감.

ALLOWED: cite numbers from facts, name actions, mention check IDs.
Return only JSON matching the requested schema.
""".strip()


class SuggestionUserText(BaseModel):
    id: str
    user_facing_text: str = Field(max_length=200)


class Narration(BaseModel):
    explanation: str = Field(max_length=200)
    suggestions_user_text: list[SuggestionUserText] = Field(default_factory=list)


class NarratorClient(Protocol):
    def generate(self, payload: dict) -> Narration:
        ...


class OpenAINarratorClient:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_RECOMMENDATION_MODEL", "gpt-4o-mini")

    def generate(self, payload: dict) -> Narration:
        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return Narration.model_validate_json(content)


def build_default_narrator_client() -> NarratorClient | None:
    if os.getenv("RECOMMENDATION_NARRATOR_ENABLED") != "true":
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None
    return OpenAINarratorClient()


def build_narrator_payload(
    score: Score,
    checks: list[CheckResult],
    suggestions: list[Suggestion],
) -> dict:
    failed_checks = [check for check in checks if check.result == "fail"]
    return {
        "score": score.model_dump(mode="json"),
        "failed_checks": [check.model_dump(mode="json") for check in failed_checks],
        "top3_suggestions": [
            suggestion.model_dump(mode="json", by_alias=True)
            for suggestion in suggestions
        ],
    }


def rule_based_narration(
    explanation: str,
    suggestions: list[Suggestion],
) -> Narration:
    return Narration(
        explanation=explanation[:200],
        suggestions_user_text=[
            SuggestionUserText(
                id=suggestion.id,
                user_facing_text=suggestion.user_facing_text or "",
            )
            for suggestion in suggestions
            if suggestion.user_facing_text
        ],
    )


def narrate_once(
    score: Score,
    checks: list[CheckResult],
    suggestions: list[Suggestion],
    fallback_explanation: str,
    client: NarratorClient | None,
) -> Narration:
    if client is None:
        return rule_based_narration(fallback_explanation, suggestions)

    try:
        return client.generate(build_narrator_payload(score, checks, suggestions))
    except (ValidationError, json.JSONDecodeError, RuntimeError, ValueError):
        return rule_based_narration(fallback_explanation, suggestions)


def validate_narration(
    narration: Narration,
    checks: list[CheckResult],
    suggestions: list[Suggestion],
) -> list[str]:
    text = _narration_text(narration)
    violations = [
        f"forbidden_term:{term}"
        for term in FORBIDDEN_TERMS
        if term in text
    ]

    allowed_numbers = _allowed_numbers(checks, suggestions)
    unsupported = [
        number
        for number in _numbers(text)
        if number not in allowed_numbers
    ]
    violations.extend(f"unsupported_number:{number}" for number in unsupported)
    return violations


def apply_narration_to_suggestions(
    suggestions: list[Suggestion],
    narration: Narration,
) -> list[Suggestion]:
    text_by_id = {
        item.id: item.user_facing_text
        for item in narration.suggestions_user_text
    }
    return [
        suggestion.model_copy(update={"user_facing_text": text_by_id.get(suggestion.id, suggestion.user_facing_text)})
        for suggestion in suggestions
    ]


def _narration_text(narration: Narration) -> str:
    suggestion_texts = " ".join(
        item.user_facing_text
        for item in narration.suggestions_user_text
    )
    return f"{narration.explanation} {suggestion_texts}"


def _allowed_numbers(
    checks: list[CheckResult],
    suggestions: list[Suggestion],
) -> set[str]:
    facts = []
    for check in checks:
        facts.append(check.id)
        facts.extend(check.evidence_facts)
    for suggestion in suggestions:
        facts.append(suggestion.id)
        facts.extend(suggestion.fixes_check_ids)
        facts.extend(suggestion.rationale_facts)
        facts.append(str(suggestion.expected_overall_delta))
        facts.append(str(suggestion.action.from_ or ""))
        facts.append(str(suggestion.action.to or ""))
    return {
        number
        for fact in facts
        for number in _numbers(fact)
    }


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)
