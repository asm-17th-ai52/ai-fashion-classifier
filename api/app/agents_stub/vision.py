"""Stub vision sub-graph. Produces schema-valid VisionResponse fixture.

Replace by importing the real ``app.agents.vision.vision_subgraph`` once
the Vision agent owner ships it (per docs/specs/02-agent-vision-spec.md §11.5).
"""
from __future__ import annotations

import time
from typing import Any

from app.utils.state_helpers import state_get
from app.schemas import (
    Garment,
    GarmentSlot,
    ImageQuality,
    Pattern,
    PrimaryColor,
    VisionResponse,
)
from app.schemas.enums import FormalityLabel
from app.schemas.vision import VisionAgentMeta


def _stub_vision(state: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    session_id = state_get(state, "session_id", "sess_unknown")
    response = VisionResponse(
        session_id=session_id,
        person_detected=True,
        image_quality=ImageQuality(
            resolution_ok=True, frontal=True, occlusion_ratio=0.05
        ),
        garments=[
            Garment(
                slot=GarmentSlot.top,
                category="shirt",
                primary_color=PrimaryColor(rgb=[240, 240, 240], name="white"),
                pattern=Pattern.solid,
                formality_label=FormalityLabel.business_casual,
                confidence=0.82,
            ),
            Garment(
                slot=GarmentSlot.bottom,
                category="slacks",
                primary_color=PrimaryColor(rgb=[40, 40, 50], name="navy"),
                pattern=Pattern.solid,
                formality_label=FormalityLabel.business_formal,
                confidence=0.86,
            ),
            Garment(
                slot=GarmentSlot.shoes,
                category="loafers",
                primary_color=PrimaryColor(rgb=[60, 40, 30], name="brown"),
                pattern=Pattern.solid,
                formality_label=FormalityLabel.business_casual,
                confidence=0.78,
            ),
        ],
        warnings=["stub_vision_response"],
        agent_meta=VisionAgentMeta(steps_taken=1, vlm_calls=0),
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    return {
        "outfit": response,
        "agent_latencies_ms": {"vision": elapsed},
    }


# A LangGraph "sub-graph" can be any Runnable. For stubs we expose the bare
# function — the super-graph wraps it via ``add_node``.
vision_subgraph_stub = _stub_vision
