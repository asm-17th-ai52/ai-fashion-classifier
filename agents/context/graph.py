"""
Context Agent LangGraph sub-graph 조립 (spec §10.2 그대로).

구조::

    tier1_retrieve → decide_tier ─┬─→ pack_context (use_tier1 | fallback_general)
                                  │
                                  └─→ tier2_plan_query
                                          ↓
                                      tier2_web_search
                                          ↓
                                      tier2_fetch_pages
                                          ↓
                                      tier2_extract_facts
                                          ↓
                                      decide_tier2_continue
                                          │
                              more_search ├── (back to plan_query)
                                          │
                              consensus   ├── tier2_consensus → tier2_promotion_enqueue → pack_context
                                          │
                              abort       └── pack_context
                                                ↓
                                              END

본 모듈은 ``build_context_graph()`` 만 export 한다. adapter 가 한 번 컴파일해
프로세스 lifecycle 동안 재사용.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents.context.nodes import (
    decide_dresscode_tier,
    decide_tier2_continue,
    node_pack_context,
    node_tier1_retrieve,
    node_tier2_consensus,
    node_tier2_extract_facts,
    node_tier2_fetch_pages,
    node_tier2_plan_query,
    node_tier2_promotion_enqueue,
    node_tier2_web_search,
)
from agents.context.state import ContextState


def build_context_graph():
    """Context Agent sub-graph 컴파일. spec §10.2 노드 ID 그대로."""
    g = StateGraph(ContextState)

    # 노드 등록 (spec §10.2 노드 ID 정확) ─────────────────────────────────────
    g.add_node("tier1_retrieve", node_tier1_retrieve)
    g.add_node("tier2_plan_query", node_tier2_plan_query)
    g.add_node("tier2_web_search", node_tier2_web_search)
    g.add_node("tier2_fetch_pages", node_tier2_fetch_pages)
    g.add_node("tier2_extract_facts", node_tier2_extract_facts)
    g.add_node("tier2_consensus", node_tier2_consensus)
    g.add_node("tier2_promotion_enqueue", node_tier2_promotion_enqueue)
    g.add_node("pack_context", node_pack_context)

    g.set_entry_point("tier1_retrieve")

    # Tier-1 분기 (use_tier1 / fallback_general / go_tier2) ──────────────────
    g.add_conditional_edges(
        "tier1_retrieve",
        decide_dresscode_tier,
        {
            "use_tier1": "pack_context",
            "fallback_general": "pack_context",
            "go_tier2": "tier2_plan_query",
        },
    )

    # Tier-2 ReAct 루프 ─────────────────────────────────────────────────────
    g.add_edge("tier2_plan_query", "tier2_web_search")
    g.add_edge("tier2_web_search", "tier2_fetch_pages")
    g.add_edge("tier2_fetch_pages", "tier2_extract_facts")
    g.add_conditional_edges(
        "tier2_extract_facts",
        decide_tier2_continue,
        {
            "more_search": "tier2_plan_query",
            "consensus": "tier2_consensus",
            "abort": "pack_context",
        },
    )
    g.add_edge("tier2_consensus", "tier2_promotion_enqueue")
    g.add_edge("tier2_promotion_enqueue", "pack_context")

    g.add_edge("pack_context", END)

    return g.compile()
