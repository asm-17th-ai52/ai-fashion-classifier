from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GarmentSlot(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    OUTER = "outer"
    SHOES = "shoes"
    BAG = "bag"
    WATCH = "watch"


class FormalityLabel(str, Enum):
    CASUAL = "casual"
    SMART_CASUAL = "smart_casual"
    BUSINESS_CASUAL = "business_casual"
    BUSINESS_FORMAL = "business_formal"
    FORMAL = "formal"


class Pattern(str, Enum):
    SOLID = "solid"
    STRIPE = "stripe"
    CHECK = "check"
    DOT = "dot"
    GRAPHIC = "graphic"
    OTHER = "other"


class Material(str, Enum):
    COTTON = "cotton"
    WOOL = "wool"
    SYNTHETIC = "synthetic"
    DENIM = "denim"
    LEATHER = "leather"
    KNIT = "knit"
    UNKNOWN = "unknown"


class Fit(str, Enum):
    SLIM = "slim"
    REGULAR = "regular"
    LOOSE = "loose"
    OVERSIZED = "oversized"
    UNKNOWN = "unknown"


class SleeveLength(str, Enum):
    SLEEVELESS = "sleeveless"
    SHORT = "short"
    LONG = "long"
    NA = "n/a"


class DressCodeTier(str, Enum):
    TIER1 = "tier1"
    TIER2_LIVE = "tier2_live"
    FALLBACK_GENERAL = "fallback_general"


class CheckGroup(str, Enum):
    DRESSCODE = "dresscode"
    CONSISTENCY = "consistency"
    COLOR = "color"
    CONFIDENCE = "confidence"


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class ActionType(str, Enum):
    SWAP = "swap"
    ADD = "add"
    REMOVE = "remove"
    RECOLOR = "recolor"


class RGBColor(BaseModel):
    rgb: tuple[int, int, int]
    name: str

    @field_validator("rgb")
    @classmethod
    def validate_rgb_range(cls, value: tuple[int, int, int]) -> tuple[int, int, int]:
        if any(channel < 0 or channel > 255 for channel in value):
            raise ValueError("rgb channels must be between 0 and 255")
        return value


class ImageQuality(BaseModel):
    resolution_ok: bool
    frontal: bool
    occlusion_ratio: float = Field(ge=0, le=1)


class Garment(BaseModel):
    slot: GarmentSlot
    category: str
    primary_color: RGBColor
    pattern: Pattern
    formality_label: FormalityLabel
    confidence: float = Field(ge=0, le=1)
    subcategory: str | None = None
    secondary_colors: list[object] = Field(default_factory=list)
    estimated_material: Material | None = None
    fit: Fit | None = None
    sleeve_length: SleeveLength | None = None


class VisionResponse(BaseModel):
    session_id: str
    person_detected: bool
    image_quality: ImageQuality
    garments: list[Garment]
    warnings: list[str]


class ExpectedCategories(BaseModel):
    top: list[str] = Field(default_factory=list)
    bottom: list[str] = Field(default_factory=list)
    outer: list[str] = Field(default_factory=list)
    shoes: list[str] = Field(default_factory=list)


class ColorGuidance(BaseModel):
    preferred_tones: list[str] = Field(default_factory=list)
    avoid_tones: list[str] = Field(default_factory=list)


class EvidenceQuote(BaseModel):
    url: str
    quote: str = Field(max_length=500)
    fetched_at: str


class LiveResearchMeta(BaseModel):
    search_queries_used: list[str] = Field(default_factory=list)
    sources_count: int = Field(ge=0)
    react_steps: int = Field(ge=0, le=5)
    latency_ms: int = Field(ge=0)


class DressCode(BaseModel):
    event_type: str
    tier: DressCodeTier
    rag_match_score: float = Field(ge=0, le=1)
    expected_formality_range: tuple[int, int]
    expected_categories: ExpectedCategories
    color_guidance: ColorGuidance
    extraction_confidence: float = Field(ge=0, le=1)
    source_doc_ids: list[str] = Field(default_factory=list)
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list)
    live_research_meta: LiveResearchMeta | None = None

    @field_validator("expected_formality_range")
    @classmethod
    def validate_formality_range(cls, value: tuple[int, int]) -> tuple[int, int]:
        low, high = value
        if low < 0 or high > 100 or low > high:
            raise ValueError("expected_formality_range must be within 0..100 and low <= high")
        return value


class ContextResponse(BaseModel):
    session_id: str
    dress_code: DressCode
    warnings: list[str]


class Score(BaseModel):
    overall: int = Field(ge=0, le=100)
    method: Literal["group_weighted_with_blocker_cap"]
    group_scores: dict[CheckGroup, float]
    blocker_failed: bool
    cap_applied: Literal["blocker_cap_50"] | None = None

    @field_validator("group_scores")
    @classmethod
    def validate_group_scores(cls, value: dict[CheckGroup, float]) -> dict[CheckGroup, float]:
        for score in value.values():
            if score < 0 or score > 1:
                raise ValueError("group score must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def validate_blocker_cap(self) -> "Score":
        if self.blocker_failed and self.cap_applied != "blocker_cap_50":
            raise ValueError("cap_applied must be blocker_cap_50 when blocker_failed is true")
        if not self.blocker_failed and self.cap_applied is not None:
            raise ValueError("cap_applied must be null when blocker_failed is false")
        return self


class CheckResult(BaseModel):
    id: str = Field(pattern=r"^[A-E][0-9]+$")
    group: CheckGroup
    label: str
    result: CheckStatus
    applicable: bool
    is_blocker: bool
    evidence_facts: list[str]

    @model_validator(mode="after")
    def validate_applicable_result(self) -> "CheckResult":
        if self.result == CheckStatus.NOT_APPLICABLE and self.applicable:
            raise ValueError("not_applicable checks must have applicable=false")
        if self.result != CheckStatus.NOT_APPLICABLE and not self.applicable:
            raise ValueError("pass/fail checks must have applicable=true")
        return self


class Action(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: ActionType
    target_slot: Literal["top", "bottom", "outer", "shoes"] | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


class Suggestion(BaseModel):
    id: str
    fixes_check_ids: list[str] = Field(min_length=1)
    action: Action
    rationale_facts: list[str] = Field(min_length=1)
    expected_overall_delta: int
    removes_blocker: bool
    user_facing_text: str | None = Field(default=None, max_length=200)


class RecommendationResponse(BaseModel):
    session_id: str
    score: Score
    checks: list[CheckResult] = Field(min_length=13, max_length=13)
    blockers_failed: list[str]
    suggestions: list[Suggestion] = Field(max_length=3)
    explanation: str = Field(max_length=400)


class RecommendationRequest(BaseModel):
    session_id: str
    outfit: VisionResponse
    context: ContextResponse

    @model_validator(mode="after")
    def validate_session_ids(self) -> "RecommendationRequest":
        if self.session_id != self.outfit.session_id:
            raise ValueError("request session_id must match outfit session_id")
        if self.session_id != self.context.session_id:
            raise ValueError("request session_id must match context session_id")
        return self
