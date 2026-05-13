"""
Tier-2 latency cap (spec §6.8).

Tier-2 ReAct 루프가 12 초를 초과하면 ``decide_tier2_continue`` 가 abort 시그널을
보낸다. 시작 시각은 첫 ``tier2_plan_query`` 진입 시 ``tier2_meta`` 에 기록.
"""
from __future__ import annotations

import time
from typing import Any


# spec §6.8: Tier-2 전체 latency 상한 (12s).
TIER2_TIMEOUT_SECONDS: float = 12.0

_TIER2_START_KEY = "tier2_started_at"


def mark_tier2_start(tier2_meta: dict[str, Any]) -> dict[str, Any]:
    """``tier2_meta`` 에 시작 시각 기록 — 이미 기록돼 있으면 변경하지 않는다.

    LangGraph 노드가 immutable dict-merge 패턴을 따르므로, 새 dict 를 반환해
    호출 측이 ``return {"tier2_meta": mark_tier2_start(state.tier2_meta)}`` 로 사용.
    """
    if _TIER2_START_KEY in tier2_meta:
        return tier2_meta
    return {**tier2_meta, _TIER2_START_KEY: time.monotonic()}


def latency_exceeded(state: Any) -> bool:
    """``state.tier2_meta`` 의 시작 시각으로부터 ``TIER2_TIMEOUT_SECONDS`` 경과 여부."""
    started = (state.tier2_meta or {}).get(_TIER2_START_KEY)
    if started is None:
        return False
    return (time.monotonic() - float(started)) >= TIER2_TIMEOUT_SECONDS
