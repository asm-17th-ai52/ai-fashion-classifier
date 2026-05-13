"""
``agents.context`` → super-graph 어댑터.

Context Agent 의 LangGraph sub-graph 는 자체 ``ContextState`` 위에서 돌고 결과를
``state.dress_code`` (``DressCode``) 에 둔다. Super-graph 는 ``SessionState`` 의
``session_id`` 와 ``request`` 를 노드 입력으로 주고, 결과를 ``ContextResponse``
형태로 ``context`` 슬롯에 받는다.

selector (``api/app/agents_stub/__init__.py``) 가 ``agents.context.context_subgraph``
import 성공 시 stub 대신 본 어댑터를 super-graph 노드로 등록한다 — 이 모듈이
import 가능한 상태가 곧 **Context Agent 활성화 신호**.

하드 latency 가드:
- spec §6.8 의 Tier-2 12 s 상한은 본래 ``decide_tier2_continue`` 내부 ``latency_exceeded``
  가 책임지지만, LangGraph 1.x 의 Pydantic ``dict`` 필드 머지 의미가 reducer 없이
  reliable 하지 못해 실측에서 5 iter (~100 s) 까지 통과한 사례가 있음.
- 본 어댑터는 ``asyncio.wait_for`` 로 **orchestration-level hard timeout** 을 걸어
  sub-graph 가 멈추지 않더라도 12s + 1s margin 안에 cancel + fallback 응답 반환.
- 내부 latency 가드는 PR-E 후속 정리에서 root cause 수정.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from api.app.schemas.context import ContextResponse

from agents.context.graph import build_context_graph
from agents.context.latency import TIER2_TIMEOUT_SECONDS
from agents.context.nodes.pack_context import _general_fallback
from agents.context.state import ContextState


# 1 s margin: pack_context 노드가 깔끔하게 종료할 여유.
_HARD_TIMEOUT_SECONDS: float = TIER2_TIMEOUT_SECONDS + 1.0


def _state_get(state: Any, key: str, default: Any = None) -> Any:
    """Vision adapter 의 ``state_get`` 동등물 — Pydantic 모델 / dict 양쪽에서 조회.

    ``app.utils.state_helpers`` 가 ``api/`` 안에 있어 외부 패키지에서 직접 import 가
    불안정하므로 (테스트 환경/sys.path 의존) 본 어댑터는 자체 helper 를 사용.
    """
    if state is None:
        return default
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# 프로세스 lifecycle 동안 한 번만 컴파일 — LangGraph compile 은 약 ms 단위라 import
# 시 한 번이면 충분. FAISS 인덱스 / ko-sroberta 모델 로드는 첫 retrieve 호출 시 lazy.
_GRAPH = build_context_graph()


def _make_timeout_response(
    session_id: str, elapsed_ms: int
) -> dict[str, Any]:
    """sub-graph hard timeout 시 안전 fallback 응답.

    ``_general_fallback()`` 의 보수적 ``DressCode`` 와 명시적 warning 으로 반환.
    Backend / Frontend 가 정상 응답으로 처리할 수 있도록 ``context`` 슬롯을 채운다.
    """
    fallback = _general_fallback()
    return {
        "context": ContextResponse(
            session_id=session_id,
            dress_code=fallback,
            warnings=[
                "context_subgraph_hard_timeout: "
                f"{_HARD_TIMEOUT_SECONDS:.1f}s budget exceeded — general fallback"
            ],
        ),
        "agent_latencies_ms": {
            "context": elapsed_ms,
            "context_tier2": elapsed_ms,
        },
        "tier2_triggered": True,
    }


async def context_subgraph(state: Any) -> dict[str, Any]:
    """Super-graph 노드 어댑터 — SessionState → ContextState → 실행 → dict update."""
    t0 = time.monotonic()

    session_id = _state_get(state, "session_id", "sess_unknown")
    request = _state_get(state, "request")

    ctx_state = ContextState(request=request)

    try:
        final = await asyncio.wait_for(
            _GRAPH.ainvoke(ctx_state), timeout=_HARD_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return _make_timeout_response(session_id, elapsed_ms)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # LangGraph 가 반환하는 final 은 dict (compile state schema 가 BaseModel 이라도).
    dress_code = final.get("dress_code") if isinstance(final, dict) else final.dress_code
    warnings = final.get("warnings", []) if isinstance(final, dict) else final.warnings

    # 방어적: pack_context 가 무조건 dress_code 를 채우지만 외부 가정 깨질 가능성 대비.
    if dress_code is None:
        return _make_timeout_response(session_id, elapsed_ms)

    context_response = ContextResponse(
        session_id=session_id,
        dress_code=dress_code,
        warnings=list(warnings or []),
    )

    tier_value = getattr(dress_code.tier, "value", str(dress_code.tier))
    tier2_triggered = tier_value == "tier2_live"

    update: dict[str, Any] = {
        "context": context_response,
        "agent_latencies_ms": {"context": elapsed_ms},
    }
    if tier2_triggered:
        update["tier2_triggered"] = True
        update["agent_latencies_ms"]["context_tier2"] = elapsed_ms
    return update
