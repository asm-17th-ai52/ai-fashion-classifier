import json
from pathlib import Path

import pytest

from agents.recommendation import ContextResponse, VisionResponse, build_recommendation_response
from agents.recommendation.checks import evaluate_checks
from agents.recommendation.scoring import calculate_score
from agents.recommendation.simulator import apply_action, simulate_action


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(kind: str, name: str) -> dict:
    path = FIXTURE_ROOT / kind / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", ("interview_casual", "missing_shoes"))
def test_suggestion_delta_matches_simulated_recomputed_score(scenario: str):
    outfit = VisionResponse.model_validate(load_fixture("vision", scenario))
    context = ContextResponse.model_validate(load_fixture("context", scenario))
    response = build_recommendation_response(outfit, context)
    suggestion = response.suggestions[0]

    _, _, simulated_score = simulate_action(outfit, context, suggestion.action)

    assert suggestion.expected_overall_delta == simulated_score.overall - response.score.overall


def test_simulator_swap_recomputes_checks_from_modified_outfit():
    outfit = VisionResponse.model_validate(load_fixture("vision", "interview_casual"))
    context = ContextResponse.model_validate(load_fixture("context", "interview_casual"))
    response = build_recommendation_response(outfit, context)
    suggestion = response.suggestions[0]

    simulated_outfit = apply_action(outfit, suggestion.action)
    simulated_checks = evaluate_checks(simulated_outfit, context)
    simulated_score = calculate_score(simulated_checks)

    assert simulated_outfit.garments[2].category == "로퍼"
    assert simulated_score.overall == 100
    assert {check.id for check in simulated_checks if check.result == "fail"} == set()


def test_a3_suggestion_targets_shoes_even_when_another_slot_is_less_formal():
    payload = load_fixture("vision", "interview_casual")
    context_payload = load_fixture("context", "interview_casual")
    payload["garments"][0]["category"] = "tshirt"
    payload["garments"][0]["formality_label"] = "casual"
    payload["garments"][2]["formality_label"] = "formal"
    context_payload["dress_code"]["expected_formality_range"] = [50, 95]
    context_payload["dress_code"]["expected_categories"]["top"] = ["tshirt"]

    response = build_recommendation_response(
        VisionResponse.model_validate(payload),
        ContextResponse.model_validate(context_payload),
    )

    assert response.suggestions
    assert response.suggestions[0].action.target_slot == "shoes"
    assert "A3" in response.suggestions[0].fixes_check_ids
