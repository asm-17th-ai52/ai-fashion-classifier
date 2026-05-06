"""Stub sub-graphs.

Per docs/specs/08-roles-and-handoffs.md §5.1, each agent owner exports a
compiled LangGraph sub-graph at:
    - app.agents.vision.vision_subgraph
    - app.agents.context.context_subgraph
    - app.agents.recommendation.recommendation_subgraph

Until those are merged, Backend uses these stubs that produce
schema-conforming fixtures so the super-graph can run end-to-end.
The selector ``get_subgraphs()`` swaps in the real ones if importable.
"""
from __future__ import annotations

from typing import Any


def get_subgraphs() -> dict[str, Any]:
    """Return live sub-graphs if their owner modules are importable, else stubs."""
    out: dict[str, Any] = {}
    try:
        from app.agents.vision import vision_subgraph  # type: ignore
        out["vision"] = vision_subgraph
    except Exception:
        from .vision import vision_subgraph_stub
        out["vision"] = vision_subgraph_stub
    try:
        from app.agents.context import context_subgraph  # type: ignore
        out["context"] = context_subgraph
    except Exception:
        from .context import context_subgraph_stub
        out["context"] = context_subgraph_stub
    try:
        from app.agents.recommendation import recommendation_subgraph  # type: ignore
        out["recommendation"] = recommendation_subgraph
    except Exception:
        from .recommendation import recommendation_subgraph_stub
        out["recommendation"] = recommendation_subgraph_stub
    return out
