"""Backend-owned super-graph nodes — preprocess + pack_response.

Per docs/specs/05-backend-spec.md §5.4, only these two are deterministic
backend responsibilities. Vision/Context/Recommendation are owned by their
respective agent owners.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.errors import (
    BackendError,
    ImageInvalidError,
    PersonNotDetectedError,
)
from app.core.logging import get_logger
from app.schemas import (
    AgentLatenciesMs,
    SessionMeta,
    SessionResponse,
)
from app.services.preprocess import preprocess_image

from app.utils.state_helpers import state_get

log = get_logger("backend.orchestration")


def preprocess_node(state: Any) -> dict[str, Any]:
    """Run the image preprocessing pipeline. Raises propagate to FastAPI.

    Idempotent: spec §5.3 has the route call this once before persisting
    state to ``pending_cache``, then ``astream_events()`` re-enters the
    graph from the entry point. If preprocessing has already happened we
    short-circuit with the existing output so neither the pixel work nor
    the log line repeats.
    """
    if state_get(state, "preprocessed_image") is not None:
        return {}

    t0 = time.monotonic()
    image_bytes = state_get(state, "image_bytes")
    session_id = state_get(state, "session_id")
    try:
        result = preprocess_image(image_bytes)
    except (ImageInvalidError, PersonNotDetectedError):
        # User-facing 4xx — bubble up
        raise
    except BackendError:
        raise
    except Exception as exc:  # noqa: BLE001 — log + wrap
        log.exception("preprocess_failed", session_id=session_id)
        raise ImageInvalidError("이미지 전처리 실패") from exc

    meta = {
        "width": result.width,
        "height": result.height,
        "faces_blurred": result.faces_blurred,
        "pose_confidence": round(result.pose_confidence, 3),
        "original_format": result.original_format,
        "preprocess_ms": int((time.monotonic() - t0) * 1000),
    }
    log.info(
        "preprocess_done",
        session_id=session_id,
        latency_ms=meta["preprocess_ms"],
        width=meta["width"],
        height=meta["height"],
        faces_blurred=meta["faces_blurred"],
    )
    return {
        "preprocessed_image": result.image_bytes,
        "preprocess_meta": meta,
    }


def pack_response_node(state: Any) -> dict[str, Any]:
    """No-op state pass-through. Final SessionResponse is built in the route.

    We keep this node so the spec's graph topology
    (``preprocess → vision/context → recommendation → pack_response → END``)
    matches the code 1:1 and lets us add response-shaping logic later
    without touching the route.
    """
    session_id = state_get(state, "session_id")

    outfit = state_get(state, "outfit")
    if outfit is not None:
        agent_meta = getattr(outfit, "agent_meta", {}) or {}
        log.info(
            "vision_done",
            session_id=session_id,
            steps_taken=agent_meta.get("steps_taken"),
            vlm_calls=agent_meta.get("vlm_calls"),
            warnings_count=len(agent_meta.get("warnings", [])),
            has_error=bool(agent_meta.get("error")),
        )

    log.info(
        "graph_done",
        session_id=session_id,
        agent_latencies_ms=state_get(state, "agent_latencies_ms"),
        cache_hits=state_get(state, "cache_hits"),
        tier2_triggered=state_get(state, "tier2_triggered"),
    )
    return {}


def build_session_response(
    state: Any, started_at_ms: int
) -> SessionResponse:
    """Convert final super-graph state into the public SessionResponse contract."""
    latencies = state_get(state, "agent_latencies_ms") or {}
    meta = SessionMeta(
        latency_ms=int(time.time() * 1000) - started_at_ms,
        agent_latencies_ms=AgentLatenciesMs(**{k: int(v) for k, v in latencies.items()}),
        cache_hits=list(state_get(state, "cache_hits") or []),
        tier2_triggered=bool(state_get(state, "tier2_triggered")),
    )
    return SessionResponse(
        session_id=state_get(state, "session_id"),
        outfit=state_get(state, "outfit"),
        context=state_get(state, "context"),
        recommendation=state_get(state, "recommendation"),
        meta=meta,
    )
