"""Stub sub-graphs + selector.

Each agent owner exports a compiled LangGraph sub-graph. The canonical
import paths reflect where each owner actually shipped their code (see
``08-roles-and-handoffs.md`` §3.3):

- ``app.agents.vision`` — Vision Agent (``vision_subgraph``, ``analyze_outfit``)
- ``agent.recommendation`` — Recommendation Agent (``recommendation_subgraph``)
- Context Agent — not yet implemented; always falls through to the stub.

If the real module isn't importable (deps not installed, code not yet
merged, etc.) ``get_subgraphs()`` falls back to a schema-valid stub so
the super-graph still runs end-to-end. Each call re-evaluates so test
suites can monkey-patch imports between runs.
"""
from __future__ import annotations

from typing import Any


def get_subgraphs() -> dict[str, Any]:
    """Return live sub-graphs if their owner modules are importable, else stubs."""
    out: dict[str, Any] = {}

    # Vision — real code at ``api/app/agents/vision/``. The agent uses its
    # own VisionState/VisionResponse, so we wrap it with vision_adapter to
    # bridge schemas with SessionState.
    try:
        from app.agents.vision import vision_subgraph  # noqa: F401
        from .vision_adapter import vision_adapter
        out["vision"] = vision_adapter
    except Exception:
        from .vision import vision_subgraph_stub
        out["vision"] = vision_subgraph_stub

    # Context — no real implementation yet.
    try:
        from agent.context import context_subgraph  # type: ignore
        out["context"] = context_subgraph
    except Exception:
        from .context import context_subgraph_stub
        out["context"] = context_subgraph_stub

    # Recommendation — real code at ``agent/recommendation/`` (singular).
    # The sub-graph operates on its own RecommendationState + schemas,
    # so we wrap it with recommendation_adapter to bridge SessionState.
    try:
        from agent.recommendation import recommendation_subgraph  # type: ignore  # noqa: F401
        from .recommendation_adapter import recommendation_adapter
        out["recommendation"] = recommendation_adapter
    except Exception:
        from .recommendation import recommendation_subgraph_stub
        out["recommendation"] = recommendation_subgraph_stub

    return out
