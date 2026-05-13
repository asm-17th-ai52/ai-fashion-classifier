"""
Tier-2 promotion queue (spec §8).

Tier-2 결과는 **자동으로 정적 RAG 에 편입되지 않는다** — 사람 검수 후 PR 로 본
디렉터리에 편입. 본 노드는 검수 큐 (JSONL append-only) 에 한 줄을 추가한다.

best-effort fire-and-forget: 파일 작성 실패해도 그래프 전체를 중단하지 않고
warning 만 추가한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.context.state import ContextState


_QUEUE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "dresscode" / "promotion_queue.jsonl"
)


def node_tier2_promotion_enqueue(state: ContextState) -> dict[str, Any]:
    """tier2_consensus 결과를 promotion_queue.jsonl 에 append (best-effort)."""
    if state.tier2_consensus is None:
        return {}

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": state.request.event_type,
        "event_type_is_custom": state.request.event_type_is_custom,
        "dress_code": state.tier2_consensus.model_dump(mode="json"),
        "search_queries_used": list(state.search_queries_used),
        "react_steps": state.react_step,
    }
    try:
        _QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _QUEUE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {}
    except OSError as exc:
        return {
            "warnings": state.warnings + [f"promotion_enqueue_failed: {exc}"],
        }
