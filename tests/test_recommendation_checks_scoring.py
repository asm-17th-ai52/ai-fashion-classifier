import json
from pathlib import Path

import pytest

from agents.recommendation import ContextResponse, VisionResponse, build_recommendation_response


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(kind: str, name: str) -> dict:
    path = FIXTURE_ROOT / kind / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_expected_recommendation(name: str) -> dict:
    path = FIXTURE_ROOT / "recommendation" / f"expected_{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", ("interview_good", "interview_casual", "missing_shoes"))
def test_recommendation_checks_and_score_match_expected_fixture(scenario: str):
    outfit = VisionResponse.model_validate(load_fixture("vision", scenario))
    context = ContextResponse.model_validate(load_fixture("context", scenario))
    expected = load_expected_recommendation(scenario)

    response = build_recommendation_response(outfit, context)

    assert response.session_id == expected["session_id"]
    assert response.score.model_dump(mode="json") == expected["score"]
    assert response.blockers_failed == expected["blockers_failed"]
    assert [check.model_dump(mode="json") for check in response.checks] == expected["checks"]
    actual_suggestions = [
        suggestion.model_dump(mode="json", by_alias=True, exclude_none=True)
        for suggestion in response.suggestions
    ]
    assert actual_suggestions == expected["suggestions"]
    assert response.explanation == expected["explanation"]


def test_blocker_cap_limits_overall_to_50():
    outfit = VisionResponse.model_validate(load_fixture("vision", "interview_casual"))
    context = ContextResponse.model_validate(load_fixture("context", "interview_casual"))

    response = build_recommendation_response(outfit, context)

    assert response.score.blocker_failed is True
    assert response.score.cap_applied == "blocker_cap_50"
    assert response.score.overall == 50


def test_not_applicable_checks_do_not_count_in_group_score():
    outfit = VisionResponse.model_validate(load_fixture("vision", "missing_shoes"))
    context = ContextResponse.model_validate(load_fixture("context", "missing_shoes"))

    response = build_recommendation_response(outfit, context)

    assert response.checks[2].id == "A3"
    assert response.checks[2].applicable is False
    assert response.score.group_scores["dresscode"] == 1.0
    assert response.score.group_scores["consistency"] == 0.5


def test_avoid_tones_match_canonical_color_aliases():
    payload = load_fixture("vision", "interview_good")
    context_payload = load_fixture("context", "interview_good")
    payload["garments"][0]["primary_color"] = {
        "rgb": [255, 0, 0],
        "name": "red",
    }
    context_payload["dress_code"]["color_guidance"]["avoid_tones"] = ["빨강"]

    response = build_recommendation_response(
        VisionResponse.model_validate(payload),
        ContextResponse.model_validate(context_payload),
    )
    check = next(check for check in response.checks if check.id == "A5")

    assert check.result == "fail"
    assert "matched_avoid_tones=[red]" in check.evidence_facts


def test_color_contrast_uses_delta_e2000_not_brightness_proxy():
    payload = load_fixture("vision", "interview_good")
    payload["garments"][0]["primary_color"] = {
        "rgb": [255, 0, 0],
        "name": "red",
    }
    payload["garments"][1]["primary_color"] = {
        "rgb": [0, 255, 0],
        "name": "green",
    }

    response = build_recommendation_response(
        VisionResponse.model_validate(payload),
        ContextResponse.model_validate(load_fixture("context", "interview_good")),
    )
    check = next(check for check in response.checks if check.id == "C1")

    assert check.result == "fail"
    assert check.evidence_facts[0] == "delta_e2000_top_bottom=87"
