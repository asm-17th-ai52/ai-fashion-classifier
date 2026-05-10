import json
from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from agents.recommendation import ContextResponse, VisionResponse, build_recommendation_response
from agents.recommendation.graph import build_recommendation_graph
from agents.recommendation.narrator import (
    Narration,
    SuggestionUserText,
    validate_narration,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(kind: str, name: str) -> dict:
    path = FIXTURE_ROOT / kind / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class FakeNarratorClient:
    def __init__(self, narrations: list[Narration]) -> None:
        self.narrations = narrations
        self.calls = 0

    def generate(self, payload: dict) -> Narration:
        narration = self.narrations[min(self.calls, len(self.narrations) - 1)]
        self.calls += 1
        return narration


def scenario_payload(name: str = "interview_casual"):
    outfit = VisionResponse.model_validate(load_fixture("vision", name))
    context = ContextResponse.model_validate(load_fixture("context", name))
    return outfit, context


def test_graph_uses_safe_narrator_output():
    outfit, context = scenario_payload()
    client = FakeNarratorClient(
        [
            Narration(
                explanation="A4 미스가 있으며 평균 63은 기대 범위 70~95보다 낮습니다.",
                suggestions_user_text=[
                    SuggestionUserText(
                        id="sg_1",
                        user_facing_text="신발을 로퍼로 교체하면 평균 78로 올라갑니다.",
                    )
                ],
            )
        ]
    )
    graph = build_recommendation_graph(narrator_client=client)

    state = graph.invoke({"outfit": outfit, "context": context})

    assert state["response"].explanation == "A4 미스가 있으며 평균 63은 기대 범위 70~95보다 낮습니다."
    assert state["response"].suggestions[0].user_facing_text == "신발을 로퍼로 교체하면 평균 78로 올라갑니다."
    assert client.calls == 1


def test_graph_retries_once_after_safety_violation():
    outfit, context = scenario_payload()
    client = FakeNarratorClient(
        [
            Narration(explanation="신뢰감이 좋아집니다.", suggestions_user_text=[]),
            Narration(
                explanation="A4 미스가 있으며 평균 63은 기대 범위 70~95보다 낮습니다.",
                suggestions_user_text=[],
            ),
        ]
    )
    graph = build_recommendation_graph(narrator_client=client)

    state = graph.invoke({"outfit": outfit, "context": context})

    assert state["response"].explanation == "A4 미스가 있으며 평균 63은 기대 범위 70~95보다 낮습니다."
    assert state["narrator_retries"] == 1
    assert client.calls == 2


def test_graph_falls_back_after_repeated_safety_violation():
    outfit, context = scenario_payload()
    expected = build_recommendation_response(outfit, context)
    client = FakeNarratorClient(
        [
            Narration(explanation="신뢰감이 좋아집니다.", suggestions_user_text=[]),
            Narration(explanation="없는 숫자 999를 말합니다.", suggestions_user_text=[]),
        ]
    )
    graph = build_recommendation_graph(narrator_client=client)

    state = graph.invoke({"outfit": outfit, "context": context})

    assert state["response"] == expected
    assert state["narrator_retries"] == 1
    assert state["narrator_used_fallback"] is True
    assert client.calls == 2


def test_validate_narration_flags_forbidden_terms_and_unsupported_numbers():
    outfit, context = scenario_payload()
    response = build_recommendation_response(outfit, context)
    narration = Narration(
        explanation="신뢰감이 좋아지고 999점이 됩니다.",
        suggestions_user_text=[],
    )

    violations = validate_narration(narration, response.checks, response.suggestions)

    assert "forbidden_term:신뢰감" in violations
    assert "unsupported_number:999" in violations
