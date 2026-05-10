"""Unit tests for ``app.orchestration.streaming.EventMapper``.

The mapper is fed LangGraph ``astream_events()`` payloads and must emit
SSE-shaped progress dicts with monotonically non-decreasing pct, dedup'ed
keys, and dynamic messages for nodes whose pct/message depends on output
(per agent specs §11/§12).
"""
from __future__ import annotations

from app.orchestration.streaming import EventMapper


def _flatten(mapper: EventMapper, events: list[dict]) -> list[dict]:
    out: list[dict] = []
    for ev in events:
        out.extend(mapper.map(ev))
    return out


# ---------------------------------------------------------------------------
# Super-graph node-level coverage (stub mode — no sub-graph internals)
# ---------------------------------------------------------------------------
def test_super_graph_nodes_emit_in_pct_order() -> None:
    mapper = EventMapper()
    events = [
        {"event": "on_chain_start", "name": "preprocess", "data": {}},
        {"event": "on_chain_end", "name": "preprocess", "data": {}},
        {"event": "on_chain_start", "name": "vision", "data": {}},
        {"event": "on_chain_end", "name": "vision", "data": {}},
        {"event": "on_chain_start", "name": "context", "data": {}},
        {"event": "on_chain_end", "name": "context", "data": {}},
        {"event": "on_chain_start", "name": "recommendation", "data": {}},
        {"event": "on_chain_end", "name": "recommendation", "data": {}},
        {"event": "on_chain_start", "name": "pack_response", "data": {}},
    ]
    sse = _flatten(mapper, events)
    pcts = [s["pct"] for s in sse]
    assert pcts == sorted(pcts)
    # Every emission has the SSE progress envelope
    for s in sse:
        assert s["type"] == "progress"
        assert isinstance(s["message"], str) and s["message"]


def test_unknown_event_kind_is_ignored() -> None:
    mapper = EventMapper()
    out = list(mapper.map({"event": "on_chat_model_stream", "name": "foo", "data": {}}))
    assert out == []


def test_unknown_node_name_is_ignored() -> None:
    mapper = EventMapper()
    out = list(mapper.map({"event": "on_chain_start", "name": "_nothing_", "data": {}}))
    assert out == []


def test_dedup_prevents_duplicate_emissions() -> None:
    mapper = EventMapper()
    e = {"event": "on_chain_start", "name": "preprocess", "data": {}}
    first = list(mapper.map(e))
    second = list(mapper.map(e))
    assert len(first) == 1
    assert second == []


# ---------------------------------------------------------------------------
# Vision sub-graph: per-garment fan-out from vlm_extract_all
# ---------------------------------------------------------------------------
def test_vlm_extract_all_emits_per_slot_messages() -> None:
    mapper = EventMapper()
    payload = {
        "event": "on_chain_end",
        "name": "vlm_extract_all",
        "data": {
            "output": {
                "garments": [
                    {"slot": "top", "category": "shirt", "primary_color": {"name": "white"}},
                    {"slot": "bottom", "category": "slacks", "primary_color": {"name": "navy"}},
                    {"slot": "shoes", "category": "loafers", "primary_color": {"name": "brown"}},
                ]
            }
        },
    }
    out = list(mapper.map(payload))
    messages = [s["message"] for s in out]
    assert "상의: shirt · white" in messages
    assert "하의: slacks · navy" in messages
    assert "신발: loafers · brown" in messages
    # pct stays non-decreasing across the fan-out
    pcts = [s["pct"] for s in out]
    assert pcts == sorted(pcts)


def test_vlm_extract_all_handles_missing_color() -> None:
    mapper = EventMapper()
    payload = {
        "event": "on_chain_end",
        "name": "vlm_extract_all",
        "data": {
            "output": {
                "garments": [
                    {"slot": "top", "category": "shirt", "primary_color": None},
                ]
            }
        },
    }
    out = list(mapper.map(payload))
    assert any(s["message"] == "상의: shirt" for s in out)


# ---------------------------------------------------------------------------
# Context sub-graph: tier branch + dynamic search-result count
# ---------------------------------------------------------------------------
def test_decide_tier_picks_tier1_message() -> None:
    mapper = EventMapper()
    out = list(
        mapper.map({
            "event": "on_chain_end",
            "name": "decide_tier",
            "data": {"output": {"tier": "tier1"}},
        })
    )
    assert any(s["message"] == "드레스코드 기준을 찾았어요" for s in out)


def test_decide_tier_picks_tier2_message() -> None:
    mapper = EventMapper()
    out = list(
        mapper.map({
            "event": "on_chain_end",
            "name": "decide_tier",
            "data": {"output": {"tier": "tier2_live"}},
        })
    )
    assert any(s["message"] == "외부 자료를 실시간으로 검색할게요" for s in out)


def test_tier2_web_search_inlines_result_count() -> None:
    mapper = EventMapper()
    out = list(
        mapper.map({
            "event": "on_chain_end",
            "name": "tier2_web_search",
            "data": {"output": {"search_results": [1, 2, 3, 4]}},
        })
    )
    assert any(s["message"] == "관련 자료 4건을 찾았어요" for s in out)


def test_pack_context_inlines_temperature_when_present() -> None:
    mapper = EventMapper()
    out = list(
        mapper.map({
            "event": "on_chain_end",
            "name": "pack_context",
            "data": {"output": {"weather": {"temperature_celsius": 8.5}}},
        })
    )
    assert any("8.5°C" in s["message"] for s in out)


def test_pack_context_falls_back_when_weather_missing() -> None:
    mapper = EventMapper()
    out = list(
        mapper.map({
            "event": "on_chain_end",
            "name": "pack_context",
            "data": {"output": {"weather": None}},
        })
    )
    assert any(s["message"] == "상황 컨텍스트 준비 완료" for s in out)


# ---------------------------------------------------------------------------
# Monotonic pct guard
# ---------------------------------------------------------------------------
def test_pct_never_decreases_across_mixed_events() -> None:
    mapper = EventMapper()
    # Intentionally emit a "later" node before an "earlier" one — the second
    # emission should be clamped up to the previously reached pct, not rewind.
    out = []
    out += list(mapper.map({"event": "on_chain_start", "name": "narrate", "data": {}}))
    out += list(mapper.map({"event": "on_chain_start", "name": "preprocess", "data": {}}))
    pcts = [s["pct"] for s in out]
    assert pcts == sorted(pcts)
