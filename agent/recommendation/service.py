from .checks import evaluate_checks
from .schemas import ContextResponse, RecommendationResponse, VisionResponse
from .scoring import calculate_score, get_blockers_failed
from .suggestions import build_explanation, build_suggestions


def build_recommendation_response(
    outfit: VisionResponse,
    context: ContextResponse,
) -> RecommendationResponse:
    checks = evaluate_checks(outfit, context)
    score = calculate_score(checks)
    suggestions = build_suggestions(outfit, context, checks)
    return RecommendationResponse(
        session_id=outfit.session_id,
        score=score,
        checks=checks,
        blockers_failed=get_blockers_failed(checks),
        suggestions=suggestions,
        explanation=build_explanation(outfit, context, checks, suggestions),
    )
