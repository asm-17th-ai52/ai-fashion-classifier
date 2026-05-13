"""LangGraph ``astream_events()`` → SSE event mapping.

Spec references:
- 05-backend-spec.md §4.2 — SSE envelope (``progress`` / ``done`` / ``error``)
- 02-agent-vision-spec.md §12 — Vision sub-graph node names + messages
- 03-agent-context-spec.md §11 — Context sub-graph node names + messages
- 04-agent-recommendation-spec.md §11 — Recommendation sub-graph node names + messages

Per spec §4.2 line 147, agent nodes do **not** know about SSE; the
backend formats ``message``/``pct`` from ``event["name"]`` and
``event["data"]["output"]``. ``EventMapper`` keeps the per-stream state
needed to (a) emit each fixed-progress message at most once and (b) walk
the ``vlm_extract_all`` garments list to produce per-slot inline messages
(``"상의: 드레스 셔츠 · 화이트"``).
"""
from __future__ import annotations

from typing import Any, Iterator, Optional

# Per-slot progress percentages for vlm_extract_all garment fan-out. The
# numbers anchor the spec §4.2 example (top → 20, shoes → 28).
_GARMENT_SLOT_PCT = {"top": 20, "outer": 24, "bottom": 26, "shoes": 28, "bag": 30, "watch": 31}

_NODE_TO_AGENT: dict[str, str] = {
    # super-graph
    "preprocess": "vision",
    "vision": "vision",
    "context": "context",
    "recommendation": "recommendation",
    "pack_response": "recommendation",
    # vision sub-graph (02-agent-vision-spec.md §11)
    "validate_image": "vision",
    "vlm_extract_all": "vision",
    "overwrite_colors": "vision",
    "run_verifiers": "vision",
    "vlm_extract_targeted": "vision",
    "critic_llm": "vision",
    # context sub-graph (03-agent-context-spec.md §10)
    "tier1_retrieve": "context",
    "decide_tier": "context",
    "tier2_plan_query": "context",
    "tier2_web_search": "context",
    "tier2_fetch_pages": "context",
    "tier2_extract_facts": "context",
    "tier2_consensus": "context",
    "tier2_promotion_enqueue": "context",
    "pack_context": "context",
    # recommendation sub-graph (04-agent-recommendation-spec.md §10)
    "evaluate_checks": "recommendation",
    "compute_score": "recommendation",
    "generate_candidates": "recommendation",
    "simulate_and_filter": "recommendation",
    "narrate": "recommendation",
    "safety_filter": "recommendation",
}
_GARMENT_SLOT_LABEL_KO = {
    "top": "상의",
    "outer": "아우터",
    "bottom": "하의",
    "shoes": "신발",
    "bag": "가방",
    "watch": "시계",
}

# Coarse progress for super-graph node-level events (used when sub-graphs
# are stubs and don't expose internal nodes). Each entry: (pct, message).
_SUPER_NODES = {
    ("on_chain_start", "preprocess"): (5, "이미지를 전처리하고 있어요"),
    ("on_chain_end", "preprocess"): (12, "사진에서 사람을 감지했어요"),
    ("on_chain_start", "vision"): (18, "착장을 분석하고 있어요"),
    ("on_chain_end", "vision"): (35, "착장 분석을 완료했어요"),
    ("on_chain_start", "context"): (45, "드레스코드 기준을 조회하고 있어요"),
    ("on_chain_end", "context"): (65, "상황 분석을 완료했어요"),
    ("on_chain_start", "recommendation"): (72, "17개 항목을 체크하고 있어요"),
    ("on_chain_end", "recommendation"): (94, "분석 결과를 정리하고 있어요"),
    ("on_chain_start", "pack_response"): (97, "분석 결과를 정리하고 있어요"),
}

# Fine-grained sub-graph node events (per agent specs §11/§12). Used when
# real sub-graphs are wired in and emit their internal node events.
_SUB_NODES_FIXED = {
    # vision sub-graph
    ("on_chain_start", "validate_image"): (8, "사진을 확인하고 있어요"),
    ("on_chain_end", "validate_image"): (12, "사진에서 사람을 감지했어요"),
    ("on_chain_start", "vlm_extract_all"): (18, "착장을 분석하고 있어요"),
    ("on_chain_end", "overwrite_colors"): (32, "색상 정보를 정밀 보정했어요"),
    ("on_chain_start", "run_verifiers"): (33, "착장 정보를 검증하고 있어요"),
    ("on_chain_start", "critic_llm"): (34, "세부 속성을 재확인하고 있어요"),
    # context sub-graph
    ("on_chain_start", "tier1_retrieve"): (45, "드레스코드 기준을 조회하고 있어요"),
    ("on_chain_start", "tier2_plan_query"): (50, "검색 쿼리를 생성하고 있어요"),
    ("on_chain_end", "tier2_fetch_pages"): (56, "자료를 읽고 있어요"),
    ("on_chain_start", "tier2_extract_facts"): (60, "드레스코드 정보를 추출하고 있어요"),
    # recommendation sub-graph
    ("on_chain_start", "evaluate_checks"): (72, "17개 항목을 체크하고 있어요"),
    ("on_chain_end", "evaluate_checks"): (85, "드레스코드 · 색상 · 환경 적합성 평가 완료"),
    ("on_chain_end", "compute_score"): (88, "종합 점수를 계산했어요"),
    ("on_chain_start", "generate_candidates"): (92, "개선 제안을 생성하고 있어요"),
    ("on_chain_start", "narrate"): (98, "분석 결과를 정리하고 있어요"),
}


# Each agent's global-pct range → used to compute per-agent 0-100 pct independently.
_AGENT_STAGE_RANGE: dict[str, tuple[int, int]] = {
    "vision":         (0,  35),
    "context":        (35, 65),
    "recommendation": (65, 100),
    "system":         (0,  100),
}


def _output_get(output: Any, name: str, default: Any = None) -> Any:
    if output is None:
        return default
    if isinstance(output, dict):
        return output.get(name, default)
    return getattr(output, name, default)


class EventMapper:
    """Stateful per-stream mapper from LangGraph events to SSE dicts."""

    def __init__(self) -> None:
        self._emitted_keys: set[tuple[str, str]] = set()
        self._garments_announced: set[str] = set()
        self._last_pct = 0
        self._last_agent_raw_pct: dict[str, int] = {}  # per-agent raw pct (before global clamp)

    def map(self, event: dict) -> Iterator[dict]:
        """Yield zero or more SSE event dicts for one LangGraph event."""
        kind = event.get("event")
        name = event.get("name")
        if kind not in {"on_chain_start", "on_chain_end"} or not name:
            return

        key = (kind, name)
        # Sub-graph fine-grained events take precedence when available.
        fixed = _SUB_NODES_FIXED.get(key) or _SUPER_NODES.get(key)
        node_agent = _NODE_TO_AGENT.get(name, "system")

        # Special: emit per-slot garment messages as vlm_extract_all ends.
        if kind == "on_chain_end" and name == "vlm_extract_all":
            output = (event.get("data") or {}).get("output")
            for sse in self._iter_garment_messages(output):
                yield sse

        # Special: decide_tier end picks tier1 vs tier2 message.
        if kind == "on_chain_end" and name == "decide_tier":
            output = (event.get("data") or {}).get("output")
            tier = _output_get(output, "tier")
            msg = (
                "외부 자료를 실시간으로 검색할게요"
                if tier == "tier2_live"
                else "드레스코드 기준을 찾았어요"
            )
            sse = self._progress(48, msg, dedup_key=("decide_tier_msg", str(tier)), agent="context")
            if sse:
                yield sse

        # Special: tier2_web_search end → result count.
        if kind == "on_chain_end" and name == "tier2_web_search":
            output = (event.get("data") or {}).get("output")
            results = _output_get(output, "search_results") or []
            n = len(results) if isinstance(results, (list, tuple)) else 0
            sse = self._progress(
                53,
                f"관련 자료 {n}건을 찾았어요",
                dedup_key=("tier2_web_search", str(n)),
                agent="context",
            )
            if sse:
                yield sse

        # Special: pack_context end → emit weather temp inline if available.
        if kind == "on_chain_end" and name == "pack_context":
            output = (event.get("data") or {}).get("output")
            weather = _output_get(output, "weather")
            temp = _output_get(weather, "temperature_celsius") if weather else None
            if temp is not None:
                msg = f"오늘 날씨 정보를 가져왔어요 · {temp}°C"
            else:
                msg = "상황 컨텍스트 준비 완료"
            sse = self._progress(63, msg, dedup_key=("pack_context_msg",), agent="context")
            if sse:
                yield sse

        if fixed is not None:
            pct, message = fixed
            sse = self._progress(pct, message, dedup_key=key, agent=node_agent)
            if sse:
                yield sse

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _iter_garment_messages(self, output: Any) -> Iterator[dict]:
        garments = _output_get(output, "garments") or []
        if not isinstance(garments, (list, tuple)):
            return
        for g in garments:
            slot = _output_get(g, "slot")
            slot_value = getattr(slot, "value", slot)
            if not isinstance(slot_value, str) or slot_value in self._garments_announced:
                continue
            self._garments_announced.add(slot_value)
            label = _GARMENT_SLOT_LABEL_KO.get(slot_value, slot_value)
            category = _output_get(g, "category") or "—"
            color = _output_get(g, "primary_color")
            color_name = _output_get(color, "name") if color else None
            tail = f"{category}" if not color_name else f"{category} · {color_name}"
            pct = _GARMENT_SLOT_PCT.get(slot_value, 28)
            sse = self._progress(
                pct,
                f"{label}: {tail}",
                dedup_key=("garment", slot_value),
                agent="vision",
            )
            if sse:
                yield sse

    def _progress(
        self, pct: int, message: str, *, dedup_key: tuple, agent: str = "system"
    ) -> Optional[dict]:
        if dedup_key in self._emitted_keys:
            return None
        self._emitted_keys.add(dedup_key)

        # Per-agent 0-100%: use original pct (before global clamp) so parallel agents
        # don't pollute each other's progress.
        start, end = _AGENT_STAGE_RANGE.get(agent, (0, 100))
        prev_raw = self._last_agent_raw_pct.get(agent, start)
        agent_raw = max(pct, prev_raw)
        self._last_agent_raw_pct[agent] = agent_raw
        agent_pct = max(0, min(100, round((agent_raw - start) / (end - start) * 100))) if end > start else 0

        # Global pct: monotonically non-decreasing for the overall progress bar.
        pct = max(pct, self._last_pct)
        self._last_pct = pct

        return {"type": "progress", "pct": pct, "agent_pct": agent_pct, "message": message, "agent": agent}


def map_langgraph_event(event: dict, mapper: EventMapper) -> list[dict]:
    """Flat helper for callers that prefer a function over the iterator.

    Returns a (possibly empty) list of SSE event dicts; the caller
    serializes them to ``data: ...\\n\\n``.
    """
    return list(mapper.map(event))
