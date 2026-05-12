"""Session routes — POST /v1/sessions, GET /v1/sessions/{id}/stream,
GET /v1/sessions/{id}, POST /v1/sessions/{id}/simulate.

Per docs/specs/05-backend-spec.md §4 and 07-data-contracts.md §5.

Flow (spec §4.1 → §4.2 → §4.3):
- ``POST /v1/sessions`` runs only ``preprocess_node`` so user-input errors
  (file decode, person not detected) still come back as a 4xx, then it
  caches the partially-populated ``SessionState`` and returns ``202`` with
  just ``session_id``.
- ``GET /v1/sessions/{id}/stream`` consumes that pending state via
  ``SUPER_GRAPH.astream_events()``. It maps LangGraph node events to SSE
  ``progress`` events, emits a single ``done`` (with the full
  ``SessionResponse``) when the graph completes, or an ``error`` event on
  fatal failure.
- ``GET /v1/sessions/{id}`` returns ``202 {"status":"pending"}`` while
  the analysis is in flight; ``200 SessionResponse`` once cached.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import (
    AgentFailedError,
    BackendError,
    ImageInvalidError,
    ImageTooLargeError,
    SessionNotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.orchestration import SUPER_GRAPH, SessionState
from app.orchestration.nodes import build_session_response, preprocess_node
from app.orchestration.streaming import EventMapper
from app.schemas import (
    SessionCreateRequest,
    SessionResponse,
    SimulateRequest,
    SimulateResponse,
)
from app.schemas.session import ChecksFlipped, SimulateAppliedItem
from app.services.cache import pending_cache, session_cache
from app.services.rate_limit import rate_limiter
from app.utils.ids import mint_session_id

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
log = get_logger("backend.api.sessions")

# Single-flight guard so two concurrent /stream calls for the same session
# don't both drive the graph. The second caller polls ``session_cache``.
_session_locks: dict[str, asyncio.Lock] = {}


def _lock_for(session_id: str) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


# ---------------------------------------------------------------------------
# POST /v1/sessions  — spec §4.1: 202 + {session_id}, no analysis yet.
# ---------------------------------------------------------------------------
@router.post("", status_code=202)
async def create_session(
    request: Request,
    image: UploadFile = File(...),
    event_type: str = Form(...),
    event_datetime: str = Form(...),
    event_type_is_custom: bool = Form(False),
    allow_live_research: bool = Form(True),
) -> JSONResponse:
    rate_limiter.check(_client_ip(request))
    raw = await image.read()
    if not raw:
        raise ImageInvalidError("빈 이미지입니다")

    try:
        parsed_dt = datetime.fromisoformat(event_datetime)
    except ValueError as exc:
        raise ValidationError(
            "event_datetime 은 ISO 8601 형식이어야 합니다"
        ) from exc

    if event_type_is_custom is False and not _is_standard_event_type(event_type):
        event_type_is_custom = True

    try:
        req_model = SessionCreateRequest(
            event_type=event_type,
            event_type_is_custom=event_type_is_custom,
            event_datetime=parsed_dt,
            allow_live_research=allow_live_research,
        )
    except PydanticValidationError as exc:
        raise ValidationError(details={"errors": exc.errors()}) from exc

    started_at_ms = int(time.time() * 1000)
    session_id = mint_session_id()
    state = SessionState(
        session_id=session_id,
        image_bytes=raw,
        request=req_model,
        started_at_ms=started_at_ms,
    )
    log.info(
        "session_create_start",
        session_id=session_id,
        event_type=event_type,
        event_type_is_custom=event_type_is_custom,
        bytes=len(raw),
    )

    # Run only the deterministic preprocess so 4xx user-input errors
    # surface immediately (spec §4.1). The rest of the graph is driven by
    # the SSE handler.
    try:
        update = preprocess_node(state)
    except (ImageInvalidError, ImageTooLargeError):
        raise
    except BackendError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("preprocess_failed", session_id=session_id)
        raise ImageInvalidError("이미지 전처리 실패") from exc

    state = state.model_copy(update=update)
    pending_cache.put(session_id, state, ttl=300)
    return JSONResponse(status_code=202, content={"session_id": session_id})


# ---------------------------------------------------------------------------
# GET /v1/sessions/{session_id}/stream  — spec §4.2 SSE
# ---------------------------------------------------------------------------
@router.get("/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    return StreamingResponse(
        _sse_generate(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _sse_generate(session_id: str) -> AsyncIterator[str]:
    # If analysis already finished (e.g., reconnect after stream ended)
    # replay the done event so the frontend can resume.
    cached = session_cache.get(session_id)
    if cached is not None:
        yield _sse({
            "type": "done",
            "pct": 100,
            "message": "분석이 완료됐어요",
            "result": cached.model_dump(mode="json"),
        })
        return

    state = pending_cache.get(session_id)
    if state is None:
        yield _sse({
            "type": "error",
            "pct": 0,
            "message": "세션을 찾을 수 없거나 만료되었어요. 다시 업로드해 주세요",
            "code": "session_not_found",
        })
        return

    lock = _lock_for(session_id)
    if lock.locked():
        # Another consumer is already streaming this session. Don't run
        # the graph twice — the spec's onerror fallback uses GET
        # /v1/sessions/{id} for reconnect.
        yield _sse({
            "type": "error",
            "pct": 0,
            "message": "이미 분석이 진행 중입니다. 잠시 후 다시 시도해 주세요",
            "code": "agent_failed",
        })
        return

    async with lock:
        # Re-check once we hold the lock — caller may have lost the race.
        cached = session_cache.get(session_id)
        if cached is not None:
            yield _sse({
                "type": "done",
                "pct": 100,
                "message": "분석이 완료됐어요",
                "result": cached.model_dump(mode="json"),
            })
            return

        mapper = EventMapper()
        final_state: Any = None
        try:
            async for event in SUPER_GRAPH.astream_events(state, version="v2"):
                # Capture root-graph end so we can build the response.
                if event.get("event") == "on_chain_end" and event.get(
                    "name"
                ) in {"LangGraph", "__root__"}:
                    final_state = (event.get("data") or {}).get("output")
                for sse_dict in mapper.map(event):
                    yield _sse(sse_dict)

            if final_state is None:
                # Fallback: re-run via ainvoke if astream_events didn't
                # surface a root on_chain_end (shouldn't happen with v2,
                # but keeps the contract safe).
                final_state = await SUPER_GRAPH.ainvoke(state)

            response = build_session_response(final_state, state.started_at_ms)
            session_cache.put(response.session_id, response)
            pending_cache.pop(session_id)
            log.info(
                "session_stream_done",
                session_id=response.session_id,
                latency_ms=response.meta.latency_ms,
                overall=response.recommendation.score.overall,
            )
            yield _sse({
                "type": "done",
                "pct": 100,
                "message": "분석이 완료됐어요",
                "result": response.model_dump(mode="json"),
            })
        except BackendError as exc:
            log.warning(
                "session_stream_backend_error",
                session_id=session_id,
                code=exc.code,
            )
            yield _sse({
                "type": "error",
                "pct": 0,
                "message": exc.user_message,
                "code": exc.code,
            })
        except Exception:  # noqa: BLE001
            log.exception("session_stream_failed", session_id=session_id)
            err = AgentFailedError()
            yield _sse({
                "type": "error",
                "pct": 0,
                "message": err.user_message,
                "code": err.code,
            })
        finally:
            _session_locks.pop(session_id, None)


# ---------------------------------------------------------------------------
# GET /v1/sessions/{session_id}  — spec §4.3
# ---------------------------------------------------------------------------
@router.get("/{session_id}")
async def get_session(session_id: str) -> Any:
    cached = session_cache.get(session_id)
    if cached is not None:
        cached.meta.cache_hits = list({*cached.meta.cache_hits, "session_full"})
        return cached
    if pending_cache.has(session_id):
        return JSONResponse(status_code=202, content={"status": "pending"})
    raise SessionNotFoundError()


# ---------------------------------------------------------------------------
# POST /v1/sessions/{session_id}/simulate
# ---------------------------------------------------------------------------
@router.post("/{session_id}/simulate", response_model=SimulateResponse)
async def simulate(session_id: str, payload: SimulateRequest) -> SimulateResponse:
    cached = session_cache.get(session_id)
    if cached is None:
        raise SessionNotFoundError()

    suggestions_by_id = {s.id: s for s in cached.recommendation.suggestions}
    applied_items: list[SimulateAppliedItem] = []
    cumulative_delta = 0
    blocker_removed = False
    fixed_check_ids: set[str] = set()

    for sg_id in payload.applied_suggestion_ids:
        sg = suggestions_by_id.get(sg_id)
        if sg is None:
            continue
        applied_items.append(
            SimulateAppliedItem(
                id=sg.id,
                individual_delta=sg.expected_overall_delta,
                removes_blocker=sg.removes_blocker,
            )
        )
        cumulative_delta += sg.expected_overall_delta
        if sg.removes_blocker:
            blocker_removed = True
        fixed_check_ids.update(sg.fixes_check_ids)

    original = cached.recommendation.score
    simulated_overall = max(0, min(100, original.overall + cumulative_delta))

    if original.cap_applied == "blocker_cap_50" and blocker_removed:
        simulated_overall = max(simulated_overall, 60)

    return SimulateResponse(
        session_id=session_id,
        original_overall=original.overall,
        simulated_overall=simulated_overall,
        delta=simulated_overall - original.overall,
        applied=applied_items,
        simulated_score={
            "overall": simulated_overall,
            "method": "group_weighted_with_blocker_cap",
            "group_scores": original.group_scores,
            "blocker_failed": original.blocker_failed and not blocker_removed,
            "cap_applied": None if blocker_removed else original.cap_applied,
        },
        checks_flipped=ChecksFlipped(to_pass=sorted(fixed_check_ids), to_fail=[]),
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
_STANDARD_EVENT_TYPES = {
    "business_meeting",
    "interview",
    "presentation",
    "casual_date",
    "wedding_guest",
    "office_daily",
    "school_daily",
    "outdoor_activity",
    "general",
}


def _is_standard_event_type(value: str) -> bool:
    return value in _STANDARD_EVENT_TYPES


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
