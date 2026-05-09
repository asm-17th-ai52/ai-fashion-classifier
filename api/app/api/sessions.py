"""Session routes — POST /v1/sessions, GET /v1/sessions/{id},
POST /v1/sessions/{id}/simulate.

Per docs/specs/05-backend-spec.md §4 and 07-data-contracts.md §5.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import (
    AgentFailedError,
    ImageInvalidError,
    ImageTooLargeError,
    SessionNotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.orchestration import SUPER_GRAPH, SessionState
from app.orchestration.nodes import build_session_response
from app.schemas import (
    SessionCreateRequest,
    SessionResponse,
    SimulateRequest,
    SimulateResponse,
)
from app.schemas.session import ChecksFlipped, SimulateAppliedItem
from app.services.cache import session_cache
from app.services.rate_limit import rate_limiter
from app.utils.ids import mint_session_id

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
log = get_logger("backend.api.sessions")


# ---------------------------------------------------------------------------
# POST /v1/sessions
# ---------------------------------------------------------------------------
@router.post("", response_model=SessionResponse)
async def create_session(
    request: Request,
    image: UploadFile = File(...),
    event_type: str = Form(...),
    event_datetime: str = Form(...),
    event_type_is_custom: bool = Form(False),
    allow_live_research: bool = Form(True),
) -> SessionResponse:
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

    # If user supplied free-text event_type that isn't a known enum, force tier-2.
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
    state = SessionState(
        session_id=mint_session_id(),
        image_bytes=raw,
        request=req_model,
        started_at_ms=started_at_ms,
    )
    log.info(
        "session_create_start",
        session_id=state.session_id,
        event_type=event_type,
        event_type_is_custom=event_type_is_custom,
        bytes=len(raw),
    )

    try:
        final_state = await SUPER_GRAPH.ainvoke(
            state,
            config={"configurable": {"session_id": state.session_id}},
        )
    except (ImageInvalidError, ImageTooLargeError):
        raise
    except Exception as exc:  # noqa: BLE001 — agent/graph failure path
        log.exception("super_graph_failed", session_id=state.session_id)
        raise AgentFailedError() from exc

    response = build_session_response(final_state, started_at_ms)
    session_cache.put(response.session_id, response)
    log.info(
        "session_create_done",
        session_id=response.session_id,
        latency_ms=response.meta.latency_ms,
        overall=response.recommendation.score.overall,
    )
    return response


# ---------------------------------------------------------------------------
# GET /v1/sessions/{session_id}
# ---------------------------------------------------------------------------
@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    cached = session_cache.get(session_id)
    if cached is None:
        raise SessionNotFoundError()
    cached.meta.cache_hits = list({*cached.meta.cache_hits, "session_full"})
    return cached


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

    # If a blocker was failed and the applied suggestions remove it, lift the cap.
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
