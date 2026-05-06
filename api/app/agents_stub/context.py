"""Stub context sub-graph. Produces schema-valid ContextResponse fixture.

Replace by ``app.agents.context.context_subgraph`` once delivered
(docs/specs/03-agent-context-spec.md §10.5).
"""
from __future__ import annotations

import time
from typing import Any

from app.orchestration.state_helpers import state_get
from app.schemas import ContextResponse, DressCode, DressCodeTier
from app.schemas.context import ColorGuidance, ExpectedCategories


# Tiny static lookup so the stub responds plausibly per event_type.
_TIER1_TABLE: dict[str, dict[str, Any]] = {
    "interview": {
        "expected_formality_range": [70, 95],
        "top": ["shirt", "blouse"],
        "bottom": ["slacks", "skirt"],
        "outer": ["blazer", "jacket"],
        "shoes": ["dress_shoes", "loafers"],
        "preferred_tones": ["neutral", "dark"],
        "avoid_tones": ["neon", "fluorescent"],
    },
    "business_meeting": {
        "expected_formality_range": [65, 90],
        "top": ["shirt", "blouse", "knit"],
        "bottom": ["slacks", "skirt"],
        "outer": ["blazer", "jacket"],
        "shoes": ["dress_shoes", "loafers"],
        "preferred_tones": ["neutral", "dark"],
        "avoid_tones": ["neon"],
    },
    "presentation": {
        "expected_formality_range": [65, 90],
        "top": ["shirt", "blouse", "knit"],
        "bottom": ["slacks", "skirt"],
        "outer": ["blazer", "jacket"],
        "shoes": ["dress_shoes", "loafers"],
        "preferred_tones": ["neutral", "dark"],
        "avoid_tones": ["neon"],
    },
    "wedding_guest": {
        "expected_formality_range": [70, 95],
        "top": ["shirt", "blouse", "dress"],
        "bottom": ["slacks", "skirt"],
        "outer": ["blazer", "jacket"],
        "shoes": ["dress_shoes", "loafers"],
        "preferred_tones": ["neutral", "dark"],
        "avoid_tones": ["white_full", "neon"],
    },
    "office_daily": {
        "expected_formality_range": [55, 80],
        "top": ["shirt", "blouse", "knit", "tshirt"],
        "bottom": ["slacks", "skirt", "chinos"],
        "outer": ["blazer", "cardigan"],
        "shoes": ["dress_shoes", "loafers", "sneakers"],
        "preferred_tones": ["neutral"],
        "avoid_tones": ["neon"],
    },
    "casual_date": {
        "expected_formality_range": [40, 70],
        "top": ["shirt", "blouse", "knit", "tshirt"],
        "bottom": ["slacks", "chinos", "jeans"],
        "outer": ["jacket", "cardigan"],
        "shoes": ["loafers", "sneakers"],
        "preferred_tones": ["neutral"],
        "avoid_tones": [],
    },
    "school_daily": {
        "expected_formality_range": [20, 55],
        "top": ["shirt", "knit", "tshirt", "hoodie"],
        "bottom": ["chinos", "jeans"],
        "outer": ["jacket", "cardigan"],
        "shoes": ["sneakers", "loafers"],
        "preferred_tones": [],
        "avoid_tones": [],
    },
    "outdoor_activity": {
        "expected_formality_range": [10, 45],
        "top": ["tshirt", "knit"],
        "bottom": ["chinos", "shorts"],
        "outer": ["jacket"],
        "shoes": ["sneakers"],
        "preferred_tones": [],
        "avoid_tones": [],
    },
    "general": {
        "expected_formality_range": [30, 80],
        "top": ["shirt", "blouse", "knit", "tshirt"],
        "bottom": ["slacks", "skirt", "chinos", "jeans"],
        "outer": ["blazer", "jacket", "cardigan"],
        "shoes": ["dress_shoes", "loafers", "sneakers"],
        "preferred_tones": ["neutral"],
        "avoid_tones": ["neon"],
    },
}


def _resolve_table(event_type: str, custom: bool) -> tuple[str, dict[str, Any], DressCodeTier, float]:
    if custom:
        return event_type, _TIER1_TABLE["general"], DressCodeTier.fallback_general, 0.5
    if event_type in _TIER1_TABLE:
        return event_type, _TIER1_TABLE[event_type], DressCodeTier.tier1, 0.92
    return "general", _TIER1_TABLE["general"], DressCodeTier.fallback_general, 0.5


def _stub_context(state: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    session_id = state_get(state, "session_id", "sess_unknown")
    request = state_get(state, "request")
    event_type = getattr(request, "event_type", "general")
    custom = bool(getattr(request, "event_type_is_custom", False))

    resolved_type, table, tier, score = _resolve_table(event_type, custom)
    dress_code = DressCode(
        event_type=resolved_type,
        tier=tier,
        rag_match_score=score,
        expected_formality_range=table["expected_formality_range"],
        expected_categories=ExpectedCategories(
            top=table["top"],
            bottom=table["bottom"],
            outer=table["outer"],
            shoes=table["shoes"],
        ),
        color_guidance=ColorGuidance(
            preferred_tones=table["preferred_tones"],
            avoid_tones=table["avoid_tones"],
        ),
        source_doc_ids=[f"stub_{resolved_type}_v1"],
        extraction_confidence=1.0 if tier == DressCodeTier.tier1 else 0.5,
    )
    response = ContextResponse(
        session_id=session_id,
        dress_code=dress_code,
        warnings=["stub_context_response"],
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    update: dict[str, Any] = {
        "context": response,
        "agent_latencies_ms": {"context": elapsed},
    }
    if tier != DressCodeTier.tier1:
        update["tier2_triggered"] = True
    return update


context_subgraph_stub = _stub_context
