"""VisionResponse — per docs/specs/07-data-contracts.md §2."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, conlist

from .enums import (
    Fit,
    FormalityLabel,
    GarmentSlot,
    Material,
    Pattern,
    SleeveLength,
)


class PrimaryColor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rgb: conlist(int, min_length=3, max_length=3) = Field(
        ..., description="0-255 RGB triple"
    )
    name: str


class SecondaryColor(BaseModel):
    model_config = ConfigDict(extra="allow")
    rgb: Optional[conlist(int, min_length=3, max_length=3)] = None
    name: Optional[str] = None


class Garment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: GarmentSlot
    category: str
    subcategory: Optional[str] = None
    primary_color: PrimaryColor
    secondary_colors: list[SecondaryColor] = Field(default_factory=list)
    pattern: Pattern
    estimated_material: Optional[Material] = None
    fit: Optional[Fit] = None
    sleeve_length: Optional[SleeveLength] = None
    formality_label: FormalityLabel
    confidence: float = Field(..., ge=0.0, le=1.0)


class ImageQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution_ok: bool
    frontal: bool
    occlusion_ratio: float = Field(..., ge=0.0, le=1.0)


class VisionAgentMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    steps_taken: int = 1
    vlm_calls: int = 0
    verifiers_failed: list[str] = Field(default_factory=list)
    reextracted_slots: list[str] = Field(default_factory=list)
    tool_call_log: list[dict] = Field(default_factory=list)


class VisionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    person_detected: bool
    image_quality: ImageQuality
    garments: list[Garment]
    warnings: list[str] = Field(default_factory=list)
    agent_meta: Optional[VisionAgentMeta] = None
