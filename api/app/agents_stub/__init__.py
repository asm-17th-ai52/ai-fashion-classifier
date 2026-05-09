"""Stub sub-graphs + selector.

Each agent owner exports a compiled LangGraph sub-graph. Per
``08-roles-and-handoffs.md`` §3.3 협의 결과, agent 코드는 repo 루트
``agents/<name>/`` 에 위치한다 (FastAPI 서빙 레이어 ``api/``와 분리).

- ``agents.vision`` — Vision Agent 공개 인터페이스 (``vision_subgraph``, ``analyze_outfit``)
- ``agents.context`` — Context Agent (예정)
- ``agents.recommendation`` — Recommendation Agent (예정)

real agent 모듈이 아직 머지 전이거나 의존성 미설치 시 ``get_subgraphs()`` 셀렉터가
schema-valid stub fixture로 폴백한다.
"""
from __future__ import annotations

from typing import Any


def get_subgraphs() -> dict[str, Any]:
    """Return live sub-graphs if their owner modules are importable, else stubs."""
    out: dict[str, Any] = {}
    try:
        # Presence check — vision_adapter wraps analyze_outfit because the
        # agent's VisionState/VisionResponse don't match SessionState.
        from agents.vision import vision_subgraph  # noqa: F401
        from .vision_adapter import vision_adapter
        out["vision"] = vision_adapter
    except Exception:
        from .vision import vision_subgraph_stub
        out["vision"] = vision_subgraph_stub
    try:
        from agents.context import context_subgraph  # type: ignore
        out["context"] = context_subgraph
    except Exception:
        from .context import context_subgraph_stub
        out["context"] = context_subgraph_stub
    try:
        from agents.recommendation import recommendation_subgraph  # type: ignore
        out["recommendation"] = recommendation_subgraph
    except Exception:
        from .recommendation import recommendation_subgraph_stub
        out["recommendation"] = recommendation_subgraph_stub
    return out
