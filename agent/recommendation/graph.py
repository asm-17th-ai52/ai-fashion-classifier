from langgraph.graph import END, StateGraph

from .checks import evaluate_checks
from .scoring import calculate_score, get_blockers_failed
from .schemas import RecommendationResponse
from .state import RecommendationState
from .suggestions import build_explanation, build_suggestions


def node_evaluate_checks(state: RecommendationState) -> dict:
    return {"checks": evaluate_checks(state.outfit, state.context)}


def node_compute_score(state: RecommendationState) -> dict:
    return {"score": calculate_score(state.checks)}


def node_generate_suggestions(state: RecommendationState) -> dict:
    return {"suggestions": build_suggestions(state.outfit, state.context, state.checks)}


def node_pack_response(state: RecommendationState) -> dict:
    if state.score is None:
        raise ValueError("score must be computed before packing RecommendationResponse")

    return {
        "response": RecommendationResponse(
            session_id=state.outfit.session_id,
            score=state.score,
            checks=state.checks,
            blockers_failed=get_blockers_failed(state.checks),
            suggestions=state.suggestions,
            explanation=build_explanation(
                state.outfit,
                state.context,
                state.checks,
                state.suggestions,
            ),
        )
    }


def build_recommendation_graph():
    graph = StateGraph(RecommendationState)

    graph.add_node("evaluate_checks", node_evaluate_checks)
    graph.add_node("compute_score", node_compute_score)
    graph.add_node("generate_suggestions", node_generate_suggestions)
    graph.add_node("pack_response", node_pack_response)

    graph.set_entry_point("evaluate_checks")
    graph.add_edge("evaluate_checks", "compute_score")
    graph.add_edge("compute_score", "generate_suggestions")
    graph.add_edge("generate_suggestions", "pack_response")
    graph.add_edge("pack_response", END)

    return graph.compile()


recommendation_subgraph = build_recommendation_graph()
