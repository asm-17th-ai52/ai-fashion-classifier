from .checks import evaluate_checks
from .schemas import ContextResponse, RecommendationResponse, VisionResponse
from .scoring import calculate_score, get_blockers_failed


def build_recommendation_response(
    outfit: VisionResponse,
    context: ContextResponse,
) -> RecommendationResponse:
    checks = evaluate_checks(outfit, context)
    score = calculate_score(checks)
    return RecommendationResponse(
        session_id=outfit.session_id,
        score=score,
        checks=checks,
        blockers_failed=get_blockers_failed(checks),
        suggestions=[],
        explanation=_build_placeholder_explanation(score.overall),
    )


def _build_placeholder_explanation(overall: int) -> str:
    return f"체크리스트 기반 종합 점수는 {overall}점입니다."
