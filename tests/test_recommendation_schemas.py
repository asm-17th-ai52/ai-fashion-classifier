import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    Score,
    Suggestion,
    VisionResponse,
    ContextResponse,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
SCENARIOS = ("interview_good", "interview_casual", "missing_shoes")


def load_fixture(kind: str, name: str) -> dict:
    path = FIXTURE_ROOT / kind / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_expected_recommendation(name: str) -> dict:
    path = FIXTURE_ROOT / "recommendation" / f"expected_{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_vision_context_and_recommendation_fixtures_validate(scenario: str):
    vision = VisionResponse.model_validate(load_fixture("vision", scenario))
    context = ContextResponse.model_validate(load_fixture("context", scenario))
    recommendation = RecommendationResponse.model_validate(load_expected_recommendation(scenario))

    assert vision.session_id == context.session_id == recommendation.session_id
    assert len(recommendation.checks) == 13


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_recommendation_request_validates_matching_session_ids(scenario: str):
    vision = load_fixture("vision", scenario)
    context = load_fixture("context", scenario)

    request = RecommendationRequest.model_validate(
        {
            "session_id": vision["session_id"],
            "outfit": vision,
            "context": context,
        }
    )

    assert request.session_id == vision["session_id"]


def test_recommendation_request_rejects_mismatched_session_id():
    vision = load_fixture("vision", "interview_good")
    context = load_fixture("context", "interview_good")

    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(
            {
                "session_id": "sess_mismatch",
                "outfit": vision,
                "context": context,
            }
        )


def test_score_rejects_invalid_overall_range():
    with pytest.raises(ValidationError):
        Score.model_validate(
            {
                "overall": 101,
                "method": "group_weighted_with_blocker_cap",
                "group_scores": {"dresscode": 1.0},
                "blocker_failed": False,
                "cap_applied": None,
            }
        )


def test_score_requires_cap_when_blocker_failed():
    with pytest.raises(ValidationError):
        Score.model_validate(
            {
                "overall": 50,
                "method": "group_weighted_with_blocker_cap",
                "group_scores": {"dresscode": 0.6},
                "blocker_failed": True,
                "cap_applied": None,
            }
        )


def test_recommendation_response_rejects_more_than_three_suggestions():
    data = load_expected_recommendation("interview_casual")
    suggestion = data["suggestions"][0]
    data["suggestions"] = [suggestion, suggestion, suggestion, suggestion]

    with pytest.raises(ValidationError):
        RecommendationResponse.model_validate(data)


def test_suggestion_accepts_action_from_alias():
    suggestion = Suggestion.model_validate(
        {
            "id": "sg_test",
            "fixes_check_ids": ["A3"],
            "action": {
                "type": "swap",
                "target_slot": "shoes",
                "from": "sneakers",
                "to": "loafers",
            },
            "rationale_facts": ["current shoes category=sneakers"],
            "expected_overall_delta": 10,
            "removes_blocker": False,
        }
    )

    assert suggestion.action.from_ == "sneakers"
