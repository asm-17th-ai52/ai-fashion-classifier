from .checks import evaluate_checks
from .schemas import (
    Action,
    ActionType,
    CheckResult,
    ContextResponse,
    FormalityLabel,
    Garment,
    GarmentSlot,
    Material,
    Pattern,
    RGBColor,
    SleeveLength,
    VisionResponse,
)
from .scoring import Score, calculate_score


CANONICAL_FORMALITY = {
    "shirt": FormalityLabel.BUSINESS_FORMAL,
    "셔츠": FormalityLabel.BUSINESS_FORMAL,
    "blouse": FormalityLabel.BUSINESS_FORMAL,
    "블라우스": FormalityLabel.BUSINESS_FORMAL,
    "blazer": FormalityLabel.BUSINESS_FORMAL,
    "블레이저": FormalityLabel.BUSINESS_FORMAL,
    "자켓": FormalityLabel.BUSINESS_FORMAL,
    "coat": FormalityLabel.BUSINESS_FORMAL,
    "코트": FormalityLabel.BUSINESS_FORMAL,
    "slacks": FormalityLabel.BUSINESS_FORMAL,
    "슬랙스": FormalityLabel.BUSINESS_FORMAL,
    "skirt": FormalityLabel.BUSINESS_FORMAL,
    "치마": FormalityLabel.BUSINESS_FORMAL,
    "dress_shoes": FormalityLabel.BUSINESS_FORMAL,
    "구두": FormalityLabel.BUSINESS_FORMAL,
    "loafers": FormalityLabel.BUSINESS_CASUAL,
    "로퍼": FormalityLabel.BUSINESS_CASUAL,
    "sneakers": FormalityLabel.CASUAL,
    "스니커즈": FormalityLabel.CASUAL,
    "knit": FormalityLabel.BUSINESS_CASUAL,
    "니트": FormalityLabel.BUSINESS_CASUAL,
    "tshirt": FormalityLabel.CASUAL,
    "티셔츠": FormalityLabel.CASUAL,
    "chino": FormalityLabel.SMART_CASUAL,
    "치노": FormalityLabel.SMART_CASUAL,
    "jeans": FormalityLabel.CASUAL,
    "청바지": FormalityLabel.CASUAL,
}

CANONICAL_RGB = {
    "black": ((35, 35, 35), "black"),
    "검정": ((35, 35, 35), "검정"),
    "navy": ((25, 45, 85), "navy"),
    "네이비": ((25, 45, 85), "네이비"),
    "gray": ((80, 80, 80), "gray"),
    "회색": ((80, 80, 80), "회색"),
    "진회색": ((64, 64, 64), "진회색"),
    "white": ((235, 235, 235), "white"),
    "흰색": ((235, 235, 235), "흰색"),
    "오프화이트": ((245, 245, 245), "오프화이트"),
    "베이지": ((245, 245, 220), "베이지"),
    "빨강": ((255, 0, 0), "빨강"),
    "노랑": ((255, 255, 0), "노랑"),
    "핑크": ((255, 105, 180), "핑크"),
    "코랄": ((255, 127, 80), "코랄"),
    "연두": ((0, 255, 0), "연두"),
    "주황": ((255, 165, 0), "주황"),
    "neutral": ((80, 80, 80), "회색"),
    "중립": ((80, 80, 80), "회색"),
}


def simulate_action(
    outfit: VisionResponse,
    context: ContextResponse,
    action: Action,
) -> tuple[VisionResponse, list[CheckResult], Score]:
    simulated_outfit = apply_action(outfit, action)
    simulated_checks = evaluate_checks(simulated_outfit, context)
    simulated_score = calculate_score(simulated_checks)
    return simulated_outfit, simulated_checks, simulated_score


def apply_action(outfit: VisionResponse, action: Action) -> VisionResponse:
    simulated = outfit.model_copy(deep=True)
    target_slot = GarmentSlot(action.target_slot) if action.target_slot else None

    if action.type == ActionType.ADD and target_slot is not None:
        simulated.garments.append(_canonical_garment(target_slot, _target_name(action)))
        return simulated

    if action.type == ActionType.SWAP and target_slot is not None:
        replacement = _canonical_garment(target_slot, _target_name(action))
        simulated.garments = [
            replacement if garment.slot == target_slot else garment
            for garment in simulated.garments
        ]
        if not any(garment.slot == target_slot for garment in simulated.garments):
            simulated.garments.append(replacement)
        return simulated

    if action.type == ActionType.REMOVE and target_slot is not None:
        simulated.garments = [
            garment for garment in simulated.garments if garment.slot != target_slot
        ]
        return simulated

    if action.type == ActionType.RECOLOR:
        tone = _target_name(action)
        simulated.garments = [
            _recolored_garment(garment, tone)
            if target_slot is None or garment.slot == target_slot
            else garment
            for garment in simulated.garments
        ]
        return simulated

    return simulated


def _canonical_garment(slot: GarmentSlot, category: str) -> Garment:
    return Garment(
        slot=slot,
        category=category,
        subcategory=None,
        primary_color=_rgb_color("neutral"),
        secondary_colors=[],
        pattern=Pattern.SOLID,
        estimated_material=_material_for_slot(slot),
        fit=None,
        sleeve_length=SleeveLength.NA,
        formality_label=CANONICAL_FORMALITY.get(category, FormalityLabel.BUSINESS_CASUAL),
        confidence=0.7,
    )


def _recolored_garment(garment: Garment, tone: str) -> Garment:
    return garment.model_copy(update={"primary_color": _rgb_color(tone)})


def _rgb_color(tone: str) -> RGBColor:
    rgb, name = CANONICAL_RGB.get(tone, CANONICAL_RGB["neutral"])
    return RGBColor(rgb=rgb, name=name)


def _material_for_slot(slot: GarmentSlot) -> Material:
    if slot == GarmentSlot.SHOES:
        return Material.LEATHER
    if slot == GarmentSlot.BOTTOM:
        return Material.WOOL
    return Material.COTTON


def _target_name(action: Action) -> str:
    if not action.to:
        return ""
    return action.to.split(" (", 1)[0]
