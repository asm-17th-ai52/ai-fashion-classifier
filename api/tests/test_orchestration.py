"""Super-graph integration tests — spec §11.1, §11.2.

The production routes drive the graph asynchronously
(``astream_events``/``ainvoke``), and the recommendation_adapter is
``async def`` because the underlying agent sub-graph is async-only. So
these tests exercise the graph through ``ainvoke`` to mirror prod.
"""
from __future__ import annotations

import time
from datetime import datetime

import pytest

from app.orchestration import SUPER_GRAPH, SessionState
from app.orchestration.nodes import build_session_response
from app.schemas import SessionCreateRequest
from app.schemas.enums import DressCodeTier


def _state(image_bytes: bytes, **overrides) -> SessionState:
    req = SessionCreateRequest(
        event_type=overrides.pop("event_type", "interview"),
        event_type_is_custom=overrides.pop("event_type_is_custom", False),
        event_datetime=overrides.pop("event_datetime", datetime(2026, 5, 7, 10)),
        allow_live_research=overrides.pop("allow_live_research", True),
    )
    return SessionState(
        session_id=overrides.pop("session_id", "sess_test"),
        image_bytes=image_bytes,
        request=req,
        started_at_ms=int(time.time() * 1000),
    )


@pytest.mark.asyncio
async def test_super_graph_runs_all_three_agents(red_jpeg_bytes: bytes) -> None:
    state = _state(red_jpeg_bytes, event_type="interview")
    final = await SUPER_GRAPH.ainvoke(state)
    assert final["outfit"] is not None
    assert final["context"] is not None
    assert final["recommendation"] is not None
    assert final["context"].dress_code.tier == DressCodeTier.tier1
    assert final["recommendation"].score.overall >= 0
    assert len(final["recommendation"].checks) == 13  # 13 binary checks


@pytest.mark.asyncio
async def test_super_graph_custom_event_uses_fallback(red_jpeg_bytes: bytes) -> None:
    state = _state(red_jpeg_bytes, event_type="송년회", event_type_is_custom=True)
    final = await SUPER_GRAPH.ainvoke(state)
    # Stub falls back to general for custom events; real Tier-2 will replace this.
    assert final["context"].dress_code.tier in {
        DressCodeTier.tier2_live,
        DressCodeTier.fallback_general,
    }
    assert final["tier2_triggered"] is True


@pytest.mark.asyncio
async def test_build_session_response_assembles_meta(red_jpeg_bytes: bytes) -> None:
    state = _state(red_jpeg_bytes)
    final = await SUPER_GRAPH.ainvoke(state)
    resp = build_session_response(final, state.started_at_ms)
    assert resp.session_id == state.session_id
    assert resp.meta.latency_ms >= 0
    assert resp.meta.agent_latencies_ms.vision is not None
    assert resp.meta.agent_latencies_ms.context is not None
    assert resp.meta.agent_latencies_ms.recommendation is not None


@pytest.mark.asyncio
async def test_super_graph_score_is_deterministic(red_jpeg_bytes: bytes) -> None:
    """Same input → same overall score across runs."""
    overall_runs = []
    for _ in range(3):
        state = _state(red_jpeg_bytes, event_type="interview", session_id="sess_det")
        final = await SUPER_GRAPH.ainvoke(state)
        overall_runs.append(final["recommendation"].score.overall)
    assert len(set(overall_runs)) == 1
