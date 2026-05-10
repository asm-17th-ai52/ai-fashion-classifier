"""agent.recommendation → super-graph 어댑터.

Recommendation Agent는 자체 ``RecommendationState{outfit, context}``를
입력으로 받고 (``agent.recommendation.state``), 자체 스키마
(``agent.recommendation.schemas.RecommendationResponse``)를 반환한다.
Super-graph는 ``SessionState`` 위에서 돌고 결과는 공개 계약
``app.schemas.RecommendationResponse`` 슬롯에 담아야 한다.

두 schema는 필드 이름·enum 문자열 값까지 1:1로 같으므로 (07-data-contracts
공통 명세 기반) ``model_dump`` ↔ ``model_validate`` 라운드트립으로 변환한다.

selector(``agents_stub/__init__.py``)가 ``agent.recommendation`` 임포트
성공 시 stub 대신 이 어댑터를 super-graph 노드로 등록한다.
"""
from __future__ import annotations

import time
from typing import Any

from agent.recommendation import recommendation_subgraph  # type: ignore[import-not-found]
from agent.recommendation.schemas import (  # type: ignore[import-not-found]
    ContextResponse as AgentContextResponse,
    VisionResponse as AgentVisionResponse,
)
from app.utils.state_helpers import state_get
from app.schemas import RecommendationResponse


def _to_agent_inputs(outfit, context) -> tuple[Any, Any]:
    """app.schemas → agent.recommendation.schemas 변환.

    by_alias=True로 ``Action.from_`` ↔ ``"from"`` 같은 alias 필드를
    원본 키 이름으로 직렬화한다.
    """
    outfit_data = outfit.model_dump(by_alias=True, mode="json")
    context_data = context.model_dump(by_alias=True, mode="json")
    return (
        AgentVisionResponse.model_validate(outfit_data),
        AgentContextResponse.model_validate(context_data),
    )


def _to_app_response(agent_response) -> RecommendationResponse:
    return RecommendationResponse.model_validate(
        agent_response.model_dump(by_alias=True, mode="json")
    )


async def recommendation_adapter(state: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    outfit = state_get(state, "outfit")
    context = state_get(state, "context")
    if outfit is None or context is None:
        # Should never happen given the super-graph fan-in edges, but bail
        # out gracefully so the route emits a clean agent_failed event.
        raise RuntimeError(
            "recommendation_adapter requires both outfit and context "
            "in SessionState"
        )

    agent_outfit, agent_context = _to_agent_inputs(outfit, context)
    final_state = await recommendation_subgraph.ainvoke(
        {"outfit": agent_outfit, "context": agent_context}
    )

    # The sub-graph stores the final response on ``state.response``; in
    # LangGraph 0.2 invoke returns a dict mirror of the state.
    response = final_state["response"] if isinstance(final_state, dict) else final_state.response
    elapsed = int((time.monotonic() - t0) * 1000)
    return {
        "recommendation": _to_app_response(response),
        "agent_latencies_ms": {"recommendation": elapsed},
    }
