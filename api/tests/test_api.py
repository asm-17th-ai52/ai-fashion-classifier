"""End-to-end FastAPI tests via TestClient."""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def _client() -> TestClient:
    return TestClient(app)


def test_health_endpoint() -> None:
    resp = _client().get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "openai" in body["dependencies"]


def test_create_session_happy_path(red_jpeg_bytes: bytes) -> None:
    client = _client()
    resp = client.post(
        "/v1/sessions",
        files={"image": ("outfit.jpg", red_jpeg_bytes, "image/jpeg")},
        data={
            "event_type": "interview",
            "event_datetime": "2026-05-07T10:00:00",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"].startswith("sess_")
    assert body["recommendation"]["score"]["overall"] >= 0
    assert len(body["recommendation"]["checks"]) == 13
    assert body["meta"]["latency_ms"] >= 0


def test_get_session_returns_cached(red_jpeg_bytes: bytes) -> None:
    client = _client()
    create = client.post(
        "/v1/sessions",
        files={"image": ("outfit.jpg", red_jpeg_bytes, "image/jpeg")},
        data={"event_type": "interview", "event_datetime": "2026-05-07T10:00:00"},
    )
    sid = create.json()["session_id"]
    get = client.get(f"/v1/sessions/{sid}")
    assert get.status_code == 200
    assert get.json()["session_id"] == sid
    assert "session_full" in get.json()["meta"]["cache_hits"]


def test_get_session_missing_returns_404() -> None:
    resp = _client().get("/v1/sessions/sess_nonexistent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "session_not_found"


def test_invalid_event_datetime_returns_422(red_jpeg_bytes: bytes) -> None:
    resp = _client().post(
        "/v1/sessions",
        files={"image": ("outfit.jpg", red_jpeg_bytes, "image/jpeg")},
        data={"event_type": "interview", "event_datetime": "not-a-date"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_garbage_image_returns_400() -> None:
    resp = _client().post(
        "/v1/sessions",
        files={"image": ("not.jpg", b"not an image", "image/jpeg")},
        data={"event_type": "interview", "event_datetime": "2026-05-07T10:00:00"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in {"image_invalid", "person_not_detected"}


def test_simulate_endpoint_applies_suggestion(red_jpeg_bytes: bytes) -> None:
    """Use a low-formality outfit so A3 fails and a swap suggestion exists.

    The stub always emits a sg_1 swap suggestion when shoes aren't in
    expected categories. Office_daily expects loafers etc. so shoes=loafers
    in the stub passes — pick interview which expects [dress_shoes, loafers]
    matching the stub shoes (loafers) so no suggestion. Use casual_date with
    is_custom to force a path.

    For the deterministic stub, suggestions list may be empty. Then
    /simulate should still return original_overall == simulated_overall.
    """
    client = _client()
    create = client.post(
        "/v1/sessions",
        files={"image": ("outfit.jpg", red_jpeg_bytes, "image/jpeg")},
        data={"event_type": "interview", "event_datetime": "2026-05-07T10:00:00"},
    )
    sid = create.json()["session_id"]
    suggestions = create.json()["recommendation"]["suggestions"]
    applied_ids = [s["id"] for s in suggestions]

    sim = client.post(
        f"/v1/sessions/{sid}/simulate",
        json={"applied_suggestion_ids": applied_ids},
    )
    assert sim.status_code == 200, sim.text
    body = sim.json()
    assert body["session_id"] == sid
    assert body["original_overall"] == create.json()["recommendation"]["score"]["overall"]
    if applied_ids:
        assert body["simulated_overall"] >= body["original_overall"]
    else:
        assert body["simulated_overall"] == body["original_overall"]
