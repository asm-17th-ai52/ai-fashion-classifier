from langgraph.graph import END, StateGraph

from .checks import evaluate_checks
from .narrator import (
    NarratorClient,
    apply_narration_to_suggestions,
    build_default_narrator_client,
    narrate_once,
    rule_based_narration,
    validate_narration,
)
from .scoring import calculate_score, get_blockers_failed
from .schemas import RecommendationResponse
from .state import RecommendationState
from .suggestions import build_explanation, build_suggestions


_DEFAULT_NARRATOR_CLIENT = object()


def node_evaluate_checks(state: RecommendationState) -> dict:
    return {"checks": evaluate_checks(state.outfit, state.context)}


def node_compute_score(state: RecommendationState) -> dict:
    return {"score": calculate_score(state.checks)}


def node_generate_suggestions(state: RecommendationState) -> dict:
    return {"suggestions": build_suggestions(state.outfit, state.context, state.checks)}


def node_prepare_fallback_explanation(state: RecommendationState) -> dict:
    if state.score is None:
        raise ValueError("score must be computed before building fallback explanation")
    return {
        "fallback_explanation": build_explanation(
            state.outfit,
            state.context,
            state.checks,
            state.suggestions,
        )
    }


def _make_node_narrate(client: NarratorClient | None):
    def node_narrate(state: RecommendationState) -> dict:
        if state.score is None or state.fallback_explanation is None:
            raise ValueError("score and fallback_explanation must be ready before narration")
        result = narrate_once(
            state.score,
            state.checks,
            state.suggestions,
            state.fallback_explanation,
            client,
        )
        return {
            "narration": result.narration,
            "narrator_used_fallback": result.used_fallback,
        }

    return node_narrate


def node_safety_filter(state: RecommendationState) -> dict:
    if state.narration is None:
        return {"narrator_violations": ["missing_narration"]}

    violations = validate_narration(state.narration, state.checks, state.suggestions)
    if not violations:
        return {
            "narrator_violations": [],
            "narrator_used_fallback": state.narrator_used_fallback,
        }

    if state.narrator_retries >= 1:
        return {
            "narration": rule_based_narration(state.fallback_explanation or "", state.suggestions),
            "narrator_violations": violations,
            "narrator_used_fallback": True,
        }

    return {
        "narrator_violations": violations,
        "narrator_retries": state.narrator_retries + 1,
    }


def decide_after_safety(state: RecommendationState) -> str:
    if not state.narrator_violations or state.narrator_used_fallback:
        return "ok"
    return "retry"


def node_pack_response(state: RecommendationState) -> dict:
    if state.score is None:
        raise ValueError("score must be computed before packing RecommendationResponse")

    explanation = state.fallback_explanation or build_explanation(
        state.outfit,
        state.context,
        state.checks,
        state.suggestions,
    )
    suggestions = state.suggestions
    if state.narration is not None:
        explanation = state.narration.explanation
        suggestions = apply_narration_to_suggestions(state.suggestions, state.narration)

    return {
        "response": RecommendationResponse(
            session_id=state.outfit.session_id,
            score=state.score,
            checks=state.checks,
            blockers_failed=get_blockers_failed(state.checks),
            suggestions=suggestions,
            explanation=explanation,
        )
    }


def build_recommendation_graph(narrator_client: NarratorClient | None | object = _DEFAULT_NARRATOR_CLIENT):
    client = (
        build_default_narrator_client()
        if narrator_client is _DEFAULT_NARRATOR_CLIENT
        else narrator_client
    )
    graph = StateGraph(RecommendationState)

    graph.add_node("evaluate_checks", node_evaluate_checks)
    graph.add_node("compute_score", node_compute_score)
    graph.add_node("generate_suggestions", node_generate_suggestions)
    graph.add_node("prepare_fallback_explanation", node_prepare_fallback_explanation)
    graph.add_node("narrate", _make_node_narrate(client))
    graph.add_node("safety_filter", node_safety_filter)
    graph.add_node("pack_response", node_pack_response)

    graph.set_entry_point("evaluate_checks")
    graph.add_edge("evaluate_checks", "compute_score")
    graph.add_edge("compute_score", "generate_suggestions")
    graph.add_edge("generate_suggestions", "prepare_fallback_explanation")
    graph.add_edge("prepare_fallback_explanation", "narrate")
    graph.add_edge("narrate", "safety_filter")
    graph.add_conditional_edges(
        "safety_filter",
        decide_after_safety,
        {
            "ok": "pack_response",
            "retry": "narrate",
        },
    )
    graph.add_edge("pack_response", END)

    return graph.compile()


recommendation_subgraph = build_recommendation_graph()
