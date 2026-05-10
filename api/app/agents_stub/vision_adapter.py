"""app.agents.vision → super-graph 어댑터.

Vision Agent는 자체 ``VisionState(session_id, image)`` 위에서 돌고
``app.agents.vision.VisionResponse`` (자체 스키마)를 반환한다.
Super-graph는 ``SessionState(image_bytes, preprocessed_image)``를 쓰고
결과를 공개 계약 ``app.schemas.VisionResponse`` 형태로 ``outfit`` 슬롯에 담는다.

이 모듈은 둘 사이의 입력 키와 응답 스키마를 변환한다. selector
(``agents_stub/__init__.py``)가 ``app.agents.vision`` 임포트 성공 시
stub 대신 이 어댑터를 super-graph 노드로 등록한다.
"""
from __future__ import annotations

import time
from typing import Any

from app.agents.vision import analyze_outfit  # type: ignore[import-not-found]
from app.utils.state_helpers import state_get
from app.schemas import (
    Garment,
    GarmentSlot,
    ImageQuality,
    Pattern,
    PrimaryColor,
    VisionResponse,
)
from app.schemas.enums import Fit, FormalityLabel, Material, SleeveLength
from app.schemas.vision import SecondaryColor, VisionAgentMeta


def _maybe_enum(enum_cls, value):
    return enum_cls(value) if value is not None else None


def _convert(av) -> VisionResponse:
    garments: list[Garment] = []
    for g in av.garments:
        garments.append(
            Garment(
                slot=GarmentSlot(g.slot),
                category=g.category,
                subcategory=g.subcategory,
                primary_color=PrimaryColor(
                    rgb=list(g.primary_color.rgb),
                    name=g.primary_color.name,
                ),
                secondary_colors=[
                    SecondaryColor(rgb=list(sc.rgb), name=sc.name)
                    for sc in (g.secondary_colors or [])
                ],
                pattern=Pattern(g.pattern),
                estimated_material=_maybe_enum(Material, g.estimated_material),
                fit=_maybe_enum(Fit, g.fit),
                sleeve_length=_maybe_enum(SleeveLength, g.sleeve_length),
                formality_label=FormalityLabel(g.formality_label),
                confidence=g.confidence,
            )
        )

    iq = av.image_quality
    meta = av.agent_meta or {}
    return VisionResponse(
        session_id=av.session_id,
        person_detected=av.person_detected,
        image_quality=ImageQuality(
            resolution_ok=iq.resolution_ok,
            frontal=iq.frontal,
            occlusion_ratio=iq.occlusion_ratio,
        ),
        garments=garments,
        warnings=list(av.warnings or []),
        agent_meta=VisionAgentMeta(
            steps_taken=meta.get("steps_taken", 1),
            vlm_calls=meta.get("vlm_calls", 0),
            tool_call_log=meta.get("tool_call_log", []),
        ),
    )


async def vision_adapter(state: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    image_bytes = (
        state_get(state, "preprocessed_image")
        or state_get(state, "image_bytes")
    )
    session_id = state_get(state, "session_id")
    av = await analyze_outfit(session_id, image_bytes)
    elapsed = int((time.monotonic() - t0) * 1000)
    return {
        "outfit": _convert(av),
        "agent_latencies_ms": {"vision": elapsed},
    }
