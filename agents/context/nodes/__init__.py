"""Context Agent LangGraph 노드 패키지.

LLM 노드 (plan_query / extract_facts / consensus) + wire-up 노드 (tier1_retrieve /
tier2_web_search / tier2_fetch_pages / tier2_promotion_enqueue / pack_context) +
분기 함수 (decide_dresscode_tier / decide_tier2_continue).

각 노드는 ``ContextState`` 를 입력으로 받아 partial state dict 를 반환한다 — 예외 X,
실패 시 ``warnings`` 만 추가.

LangGraph node id 와 함수의 매핑 (spec §10.2):

| node id | function |
|---|---|
| ``tier1_retrieve``         | ``node_tier1_retrieve`` |
| ``tier2_plan_query``       | ``node_tier2_plan_query`` |
| ``tier2_web_search``       | ``node_tier2_web_search`` |
| ``tier2_fetch_pages``      | ``node_tier2_fetch_pages`` |
| ``tier2_extract_facts``    | ``node_tier2_extract_facts`` |
| ``tier2_consensus``        | ``node_tier2_consensus`` |
| ``tier2_promotion_enqueue``| ``node_tier2_promotion_enqueue`` |
| ``pack_context``           | ``node_pack_context`` |

분기:
- ``decide_dresscode_tier`` : tier1_retrieve → {use_tier1, fallback_general, go_tier2}
- ``decide_tier2_continue`` : tier2_extract_facts → {more_search, consensus, abort}
"""
from .consensus import consensus, node_tier2_consensus
from .decide_tier import decide_dresscode_tier, decide_tier2_continue
from .extract_facts import node_tier2_extract_facts
from .pack_context import node_pack_context
from .plan_query import node_tier2_plan_query
from .promotion import node_tier2_promotion_enqueue
from .tier1_retrieve_node import node_tier1_retrieve
from .tier2_fetch_pages import node_tier2_fetch_pages
from .tier2_web_search import node_tier2_web_search

__all__ = [
    "node_tier1_retrieve",
    "node_tier2_plan_query",
    "node_tier2_web_search",
    "node_tier2_fetch_pages",
    "node_tier2_extract_facts",
    "node_tier2_consensus",
    "node_tier2_promotion_enqueue",
    "node_pack_context",
    "decide_dresscode_tier",
    "decide_tier2_continue",
    "consensus",
]
