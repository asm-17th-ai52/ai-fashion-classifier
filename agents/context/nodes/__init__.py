"""Context Agent Tier-2 ReAct 노드 패키지.

PR-D 는 LangGraph 그래프 조립 (PR-E) 와 분리해서 **노드 함수만** 제공한다.
각 노드는 ``ContextState`` 를 입력으로 받아 partial state dict 를 반환한다 — 예외 X,
실패 시 ``warnings`` 만 추가.

LangGraph node id 와 함수의 매핑 (spec §10.2 참조):

| node id | function |
|---|---|
| ``tier2_plan_query``      | ``node_tier2_plan_query`` |
| ``tier2_extract_facts``   | ``node_tier2_extract_facts`` |
| ``tier2_consensus``       | ``node_tier2_consensus`` |

``consensus`` 순수 함수도 함께 re-export — 단위 테스트가 LangGraph 의존 없이 검증 가능.
"""
from .consensus import consensus, node_tier2_consensus
from .extract_facts import node_tier2_extract_facts
from .plan_query import node_tier2_plan_query

__all__ = [
    "node_tier2_plan_query",
    "node_tier2_extract_facts",
    "node_tier2_consensus",
    "consensus",
]
