"""Super-graph builder — per docs/specs/05-backend-spec.md §5.2.

Topology:
    preprocess
        ├── vision
        ├── context
        └── recommendation (joins vision + context)
                └── pack_response → END

Vision and context fan out in parallel from preprocess; recommendation
joins them. LangGraph's superstep model triggers a node only when all of
its incoming edges are satisfied, so adding edges from both ``vision`` and
``context`` to ``recommendation`` produces the desired join.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents_stub import get_subgraphs

from .nodes import pack_response_node, preprocess_node
from .state import SessionState


def build_super_graph():
    g = StateGraph(SessionState)

    subs = get_subgraphs()

    g.add_node("preprocess", preprocess_node)
    g.add_node("vision", subs["vision"])
    g.add_node("context", subs["context"])
    g.add_node("recommendation", subs["recommendation"])
    g.add_node("pack_response", pack_response_node)

    g.set_entry_point("preprocess")

    # Parallel fan-out
    g.add_edge("preprocess", "vision")
    g.add_edge("preprocess", "context")

    # Fan-in: both must finish before recommendation runs
    g.add_edge("vision", "recommendation")
    g.add_edge("context", "recommendation")

    g.add_edge("recommendation", "pack_response")
    g.add_edge("pack_response", END)

    return g.compile()


SUPER_GRAPH = build_super_graph()
