"""
``agents.context`` → super-graph 어댑터.

Context Agent 의 LangGraph sub-graph 는 자체 ``ContextState`` 위에서 돌고 결과를
``state.dress_code`` (``DressCode``) 에 둔다. Super-graph 는 ``SessionState`` 의
``session_id`` 와 ``request`` 를 노드 입력으로 주고, 결과를 ``ContextResponse``
형태로 ``context`` 슬롯에 받는다.

selector (``api/app/agents_stub/__init__.py``) 가 ``agents.context.context_subgraph``
import 성공 시 stub 대신 본 어댑터를 super-graph 노드로 등록한다 — 이 모듈이
import 가능한 상태가 곧 **Context Agent 활성화 신호**.
"""
from __future__ import annotations

import time
from typing import Any

from api.app.schemas.context import ContextResponse

from agents.context.graph import build_context_graph
from agents.context.state import ContextState


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


async def context_subgraph(state: Any) -> dict[str, Any]:
    """Super-graph 노드 어댑터 — SessionState → ContextState → 실행 → dict update."""
    t0 = time.monotonic()

    session_id = _state_get(state, "session_id", "sess_unknown")
    request = _state_get(state, "request")

    ctx_state = ContextState(request=request)
    final = await _GRAPH.ainvoke(ctx_state)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # LangGraph 가 반환하는 final 은 dict (compile state schema 가 BaseModel 이라도).
    dress_code = final.get("dress_code") if isinstance(final, dict) else final.dress_code
    warnings = final.get("warnings", []) if isinstance(final, dict) else final.warnings

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
