"""End-to-end FastAPI tests via TestClient.

Spec references:
- 05-backend-spec.md §4.1 — POST /v1/sessions returns 202 + session_id
- 05-backend-spec.md §4.2 — GET /v1/sessions/{id}/stream is SSE
- 05-backend-spec.md §4.3 — GET /v1/sessions/{id} returns pending/cached/404
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from main import app


def _client() -> TestClient:
    return TestClient(app)


def _post_session(client: TestClient, image: bytes, **form: Any):
    data = {
        "event_type": "interview",
        "event_datetime": "2026-05-07T10:00:00",
    }
    data.update(form)
    return client.post(
        "/v1/sessions",
        files={"image": ("outfit.jpg", image, "image/jpeg")},
        data=data,
    )


def _parse_sse(body: str) -> list[dict]:
    """Parse SSE body string into the JSON payloads of every ``data:`` line."""
    out: list[dict] = []
    for raw in body.splitlines():
        if raw.startswith("data: "):
            out.append(json.loads(raw[len("data: "):]))
    return out


# ---------------------------------------------------------------------------
# §4.1 POST is async — 202 + {session_id}
# ---------------------------------------------------------------------------
def test_health_endpoint() -> None:
    resp = _client().get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "openai" in body["dependencies"]


def test_post_returns_202_with_only_session_id(red_jpeg_bytes: bytes) -> None:
    resp = _post_session(_client(), red_jpeg_bytes)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert set(body.keys()) == {"session_id"}, body
    assert body["session_id"].startswith("sess_")


def test_post_invalid_event_datetime_returns_422(red_jpeg_bytes: bytes) -> None:
    resp = _post_session(_client(), red_jpeg_bytes, event_datetime="not-a-date")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_post_garbage_image_returns_400() -> None:
    # Garbage payload — must surface a 4xx during preprocess (synchronous step
    # in the route per spec §4.1).
    resp = _post_session(_client(), b"not an image")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in {"image_invalid", "person_not_detected"}


def test_post_custom_event_type_auto_promotes_to_tier2(red_jpeg_bytes: bytes) -> None:
    """Free-text event_type without explicit flag → server flips it to custom.

    The flip is only visible end-to-end (via ``meta.tier2_triggered``) so we
    drive the SSE flow once and inspect the final result.
    """
    client = _client()
    sid = _post_session(client, red_jpeg_bytes, event_type="송년회").json()["session_id"]
    with client.stream("GET", f"/v1/sessions/{sid}/stream") as r:
        body = r.read().decode("utf-8")
    events = _parse_sse(body)
    done = next(e for e in events if e["type"] == "done")
    assert done["result"]["meta"]["tier2_triggered"] is True


# ---------------------------------------------------------------------------
# §4.2 SSE stream — progress events + a single done with full SessionResponse
# ---------------------------------------------------------------------------
def test_stream_emits_progress_then_done(red_jpeg_bytes: bytes) -> None:
    client = _client()
    sid = _post_session(client, red_jpeg_bytes).json()["session_id"]

    with client.stream("GET", f"/v1/sessions/{sid}/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers.get("cache-control") == "no-cache"
        body = r.read().decode("utf-8")

    events = _parse_sse(body)
    progress = [e for e in events if e["type"] == "progress"]
    done = [e for e in events if e["type"] == "done"]
    error = [e for e in events if e["type"] == "error"]

    assert error == []
    assert len(progress) >= 1
    assert len(done) == 1

    # Each progress event shape (spec §4.2)
    for ev in progress:
        assert set(ev.keys()) >= {"type", "pct", "message"}
        assert isinstance(ev["pct"], int)
        assert 0 <= ev["pct"] <= 100
        assert isinstance(ev["message"], str) and ev["message"]

    # pct must be monotonically non-decreasing across the stream
    pcts = [e["pct"] for e in progress]
    assert pcts == sorted(pcts), pcts

    # done event carries the full SessionResponse (spec §4.2)
    final = done[0]
    assert final["pct"] == 100
    result = final["result"]
    assert result["session_id"] == sid
    for slot in ("outfit", "context", "recommendation", "meta"):
        assert slot in result, slot
    assert len(result["recommendation"]["checks"]) == 13


def test_stream_for_unknown_session_emits_error_event() -> None:
    client = _client()
    with client.stream("GET", "/v1/sessions/sess_nonexistent/stream") as r:
        assert r.status_code == 200  # SSE always 200; error is in payload
        body = r.read().decode("utf-8")
    events = _parse_sse(body)
    assert any(e["type"] == "error" and e["code"] == "session_not_found" for e in events)


# ---------------------------------------------------------------------------
# §4.3 GET /v1/sessions/{id} — pending / done / 404
# ---------------------------------------------------------------------------
def test_get_pending_returns_202_status_pending(red_jpeg_bytes: bytes) -> None:
    """Right after POST, before the SSE consumer has driven the graph."""
    client = _client()
    sid = _post_session(client, red_jpeg_bytes).json()["session_id"]
    resp = client.get(f"/v1/sessions/{sid}")
    assert resp.status_code == 202
    assert resp.json() == {"status": "pending"}


def test_get_after_stream_completes_returns_cached_result(
    red_jpeg_bytes: bytes,
) -> None:
    client = _client()
    sid = _post_session(client, red_jpeg_bytes).json()["session_id"]
    # Drive the analysis to completion
    with client.stream("GET", f"/v1/sessions/{sid}/stream") as r:
        r.read()

    resp = client.get(f"/v1/sessions/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == sid
    assert "session_full" in body["meta"]["cache_hits"]


def test_get_unknown_session_returns_404() -> None:
    resp = _client().get("/v1/sessions/sess_nonexistent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "session_not_found"


# ---------------------------------------------------------------------------
# Reconnect / single-flight (spec §4.2 reconnect fallback note)
# ---------------------------------------------------------------------------
def test_stream_reconnect_after_completion_replays_done(
    red_jpeg_bytes: bytes,
) -> None:
    client = _client()
    sid = _post_session(client, red_jpeg_bytes).json()["session_id"]
    with client.stream("GET", f"/v1/sessions/{sid}/stream") as r:
        r.read()
    # Re-subscribe: backend should serve cached done immediately.
    with client.stream("GET", f"/v1/sessions/{sid}/stream") as r:
        body = r.read().decode("utf-8")
    events = _parse_sse(body)
    assert len(events) == 1
    assert events[0]["type"] == "done"
    assert events[0]["result"]["session_id"] == sid


# ---------------------------------------------------------------------------
# Simulate (unchanged — runs against cached SessionResponse)
# ---------------------------------------------------------------------------
def test_simulate_endpoint_applies_suggestion(red_jpeg_bytes: bytes) -> None:
    client = _client()
    sid = _post_session(client, red_jpeg_bytes).json()["session_id"]
    with client.stream("GET", f"/v1/sessions/{sid}/stream") as r:
        body = r.read().decode("utf-8")
    done = next(e for e in _parse_sse(body) if e["type"] == "done")
    suggestions = done["result"]["recommendation"]["suggestions"]
    applied_ids = [s["id"] for s in suggestions]

    sim = client.post(
        f"/v1/sessions/{sid}/simulate",
        json={"applied_suggestion_ids": applied_ids},
    )
    assert sim.status_code == 200, sim.text
    body_sim = sim.json()
    assert body_sim["session_id"] == sid
    assert body_sim["original_overall"] == done["result"]["recommendation"]["score"]["overall"]
    if applied_ids:
        assert body_sim["simulated_overall"] >= body_sim["original_overall"]
    else:
        assert body_sim["simulated_overall"] == body_sim["original_overall"]
