import json
from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from agents.recommendation import ContextResponse, VisionResponse, build_recommendation_response
from agents.recommendation.graph import recommendation_subgraph


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(kind: str, name: str) -> dict:
    path = FIXTURE_ROOT / kind / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", ("interview_good", "interview_casual", "missing_shoes"))
def test_recommendation_subgraph_matches_core_response(scenario: str):
    outfit = VisionResponse.model_validate(load_fixture("vision", scenario))
    context = ContextResponse.model_validate(load_fixture("context", scenario))
    expected = build_recommendation_response(outfit, context)

    state = recommendation_subgraph.invoke(
        {
            "outfit": outfit,
            "context": context,
        }
    )

    assert state["response"] == expected
