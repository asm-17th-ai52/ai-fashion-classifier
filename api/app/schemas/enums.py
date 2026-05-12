"""Shared enums per docs/specs/07-data-contracts.md §1."""
from enum import Enum


class StandardEventType(str, Enum):
    business_meeting = "business_meeting"
    interview = "interview"
    presentation = "presentation"
    casual_date = "casual_date"
    wedding_guest = "wedding_guest"
    office_daily = "office_daily"
    school_daily = "school_daily"
    outdoor_activity = "outdoor_activity"
    general = "general"


class GarmentSlot(str, Enum):
    top = "top"
    bottom = "bottom"
    outer = "outer"
    shoes = "shoes"
    bag = "bag"
    watch = "watch"


class FormalityLabel(str, Enum):
    casual = "casual"
    smart_casual = "smart_casual"
    business_casual = "business_casual"
    business_formal = "business_formal"
    formal = "formal"


FORMALITY_SCORE: dict[str, int] = {
    FormalityLabel.casual.value: 20,
    FormalityLabel.smart_casual.value: 45,
    FormalityLabel.business_casual.value: 65,
    FormalityLabel.business_formal.value: 85,
    FormalityLabel.formal.value: 95,
}


class CheckGroup(str, Enum):
    dresscode = "dresscode"
    consistency = "consistency"
    color = "color"
    confidence = "confidence"


class SuggestionAction(str, Enum):
    swap = "swap"
    add = "add"
    remove = "remove"
    recolor = "recolor"


class DressCodeTier(str, Enum):
    tier1 = "tier1"
    tier2_live = "tier2_live"
    fallback_general = "fallback_general"


class Pattern(str, Enum):
    solid = "solid"
    stripe = "stripe"
    check = "check"
    dot = "dot"
    graphic = "graphic"
    other = "other"


class Material(str, Enum):
    cotton = "cotton"
    wool = "wool"
    synthetic = "synthetic"
    denim = "denim"
    leather = "leather"
    knit = "knit"
    unknown = "unknown"


class Fit(str, Enum):
    slim = "slim"
    regular = "regular"
    loose = "loose"
    oversized = "oversized"
    unknown = "unknown"


class SleeveLength(str, Enum):
    sleeveless = "sleeveless"
    short = "short"
    long = "long"
    na = "n/a"
