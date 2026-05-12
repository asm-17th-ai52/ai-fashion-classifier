from math import sqrt

from .schemas import (
    CheckGroup,
    CheckResult,
    CheckStatus,
    ContextResponse,
    DressCodeTier,
    FormalityLabel,
    Garment,
    GarmentSlot,
    VisionResponse,
)


FORMALITY_SCORE = {
    FormalityLabel.CASUAL: 20,
    FormalityLabel.SMART_CASUAL: 45,
    FormalityLabel.BUSINESS_CASUAL: 65,
    FormalityLabel.BUSINESS_FORMAL: 85,
    FormalityLabel.FORMAL: 95,
}


CHECK_LABELS = {
    "A1": "상의 카테고리가 기대 범위에 포함",
    "A2": "하의 카테고리가 기대 범위에 포함",
    "A3": "신발 카테고리가 기대 범위에 포함",
    "A4": "평균 포멀니스가 기대 범위 안에 위치",
    "A5": "피해야 할 색상 톤이 없음",
    "B1": "포멀니스 편차가 기준 이하",
    "B2": "상의 슬롯이 하나만 존재",
    "B3": "필수 슬롯이 모두 존재",
    "C1": "상의와 하의 색상 대비가 적정 범위",
    "C2": "강한 채도 색상이 과하지 않음",
    "C3": "명도 다양성이 적정 범위",
    "D1": "Vision 평균 신뢰도가 기준 이상",
    "D2": "드레스코드 해석 신뢰도가 기준 이상",
}


def evaluate_checks(outfit: VisionResponse, context: ContextResponse) -> list[CheckResult]:
    garments_by_slot = _garments_by_slot(outfit)
    return [
        _category_check("A1", CheckGroup.DRESSCODE, garments_by_slot, GarmentSlot.TOP, context.dress_code.expected_categories.top),
        _category_check("A2", CheckGroup.DRESSCODE, garments_by_slot, GarmentSlot.BOTTOM, context.dress_code.expected_categories.bottom),
        _category_check("A3", CheckGroup.DRESSCODE, garments_by_slot, GarmentSlot.SHOES, context.dress_code.expected_categories.shoes),
        _a4_formality_avg(outfit, context),
        _a5_no_avoid_tones(outfit, context),
        _b1_formality_spread(garments_by_slot),
        _b2_no_duplicate_top_categories(garments_by_slot),
        _b3_required_slots_complete(garments_by_slot),
        _c1_top_bottom_contrast(garments_by_slot),
        _c2_not_too_many_strong_colors(outfit),
        _c3_tone_diversity(outfit),
        _d1_vision_avg_confidence(outfit),
        _d2_dresscode_resolution_confident(context),
    ]


def _check(
    check_id: str,
    group: CheckGroup,
    result: CheckStatus,
    applicable: bool,
    evidence_facts: list[str],
    is_blocker: bool = False,
) -> CheckResult:
    return CheckResult(
        id=check_id,
        group=group,
        label=CHECK_LABELS[check_id],
        result=result,
        applicable=applicable,
        evidence_facts=evidence_facts,
        is_blocker=is_blocker,
    )


def _garments_by_slot(outfit: VisionResponse) -> dict[GarmentSlot, list[Garment]]:
    by_slot: dict[GarmentSlot, list[Garment]] = {}
    for garment in outfit.garments:
        by_slot.setdefault(garment.slot, []).append(garment)
    return by_slot


def _primary_garment(
    garments_by_slot: dict[GarmentSlot, list[Garment]],
    slot: GarmentSlot,
) -> Garment | None:
    garments = garments_by_slot.get(slot, [])
    return garments[0] if garments else None


def _category_check(
    check_id: str,
    group: CheckGroup,
    garments_by_slot: dict[GarmentSlot, list[Garment]],
    slot: GarmentSlot,
    expected_categories: list[str],
) -> CheckResult:
    garment = _primary_garment(garments_by_slot, slot)
    slot_label = slot.value
    if garment is None or not expected_categories:
        return _check(
            check_id,
            group,
            CheckStatus.NOT_APPLICABLE,
            False,
            [
                f"expected {slot_label} categories={_fmt_list(expected_categories)}",
                f"current {slot_label} category=missing",
            ],
        )

    result = CheckStatus.PASS if garment.category in expected_categories else CheckStatus.FAIL
    return _check(
        check_id,
        group,
        result,
        True,
        [
            f"expected {slot_label} categories={_fmt_list(expected_categories)}",
            f"current {slot_label} category={garment.category}",
        ],
    )


def _a4_formality_avg(outfit: VisionResponse, context: ContextResponse) -> CheckResult:
    garments = _required_slot_garments(_garments_by_slot(outfit))
    if not garments:
        return _check(
            "A4",
            CheckGroup.DRESSCODE,
            CheckStatus.NOT_APPLICABLE,
            False,
            ["required_slots=[top, bottom, shoes]", "available_required_slots=[]"],
            is_blocker=True,
        )

    avg = round(sum(_formality_score(g) for g in garments) / len(garments))
    low, high = context.dress_code.expected_formality_range
    result = CheckStatus.PASS if low <= avg <= high else CheckStatus.FAIL
    return _check(
        "A4",
        CheckGroup.DRESSCODE,
        result,
        True,
        [f"expected_formality_range=[{low}, {high}]", f"outfit_formality_avg={avg}"],
        is_blocker=True,
    )


def _a5_no_avoid_tones(outfit: VisionResponse, context: ContextResponse) -> CheckResult:
    avoid_tones = set(context.dress_code.color_guidance.avoid_tones)
    color_names = {garment.primary_color.name for garment in outfit.garments}
    matched = sorted(color_names & avoid_tones)
    result = CheckStatus.PASS if not matched else CheckStatus.FAIL
    return _check(
        "A5",
        CheckGroup.DRESSCODE,
        result,
        True,
        [
            f"avoid_tones={_fmt_list(context.dress_code.color_guidance.avoid_tones)}",
            f"matched_avoid_tones={_fmt_list(matched)}",
        ],
    )


def _b1_formality_spread(garments_by_slot: dict[GarmentSlot, list[Garment]]) -> CheckResult:
    garments = _required_slot_garments(garments_by_slot)
    missing = _missing_required_slots(garments_by_slot)
    if missing:
        return _check(
            "B1",
            CheckGroup.CONSISTENCY,
            CheckStatus.NOT_APPLICABLE,
            False,
            ["required_slots_for_spread=[top, bottom, shoes]", f"missing_slots={_fmt_list(missing)}"],
        )

    values = [_formality_score(garment) for garment in garments]
    spread = round(_std(values))
    result = CheckStatus.PASS if spread <= 15 else CheckStatus.FAIL
    return _check(
        "B1",
        CheckGroup.CONSISTENCY,
        result,
        True,
        [f"formality_values={_fmt_list(values)}", f"formality_std={spread}"],
    )


def _b2_no_duplicate_top_categories(garments_by_slot: dict[GarmentSlot, list[Garment]]) -> CheckResult:
    top_count = len(garments_by_slot.get(GarmentSlot.TOP, []))
    result = CheckStatus.PASS if top_count == 1 else CheckStatus.FAIL
    return _check(
        "B2",
        CheckGroup.CONSISTENCY,
        result,
        True,
        [f"top_slot_count={top_count}"],
    )


def _b3_required_slots_complete(garments_by_slot: dict[GarmentSlot, list[Garment]]) -> CheckResult:
    missing = _missing_required_slots(garments_by_slot)
    result = CheckStatus.PASS if not missing else CheckStatus.FAIL
    return _check(
        "B3",
        CheckGroup.CONSISTENCY,
        result,
        True,
        ["required_slots=[top, bottom, shoes]", f"missing_slots={_fmt_list(missing)}"],
        is_blocker=True,
    )


def _c1_top_bottom_contrast(garments_by_slot: dict[GarmentSlot, list[Garment]]) -> CheckResult:
    top = _primary_garment(garments_by_slot, GarmentSlot.TOP)
    bottom = _primary_garment(garments_by_slot, GarmentSlot.BOTTOM)
    if top is None or bottom is None:
        return _check(
            "C1",
            CheckGroup.COLOR,
            CheckStatus.NOT_APPLICABLE,
            False,
            ["required_slots_for_color_contrast=[top, bottom]", "missing_slots=[top or bottom]"],
        )

    contrast = _contrast_score(top.primary_color.rgb, bottom.primary_color.rgb)
    result = CheckStatus.PASS if 10 <= contrast <= 50 else CheckStatus.FAIL
    return _check(
        "C1",
        CheckGroup.COLOR,
        result,
        True,
        [f"delta_e2000_top_bottom={contrast}", "expected_delta_e2000_range=[10, 50]"],
    )


def _c2_not_too_many_strong_colors(outfit: VisionResponse) -> CheckResult:
    strong_count = sum(1 for garment in outfit.garments if _saturation(garment.primary_color.rgb) > 0.7)
    result = CheckStatus.PASS if strong_count <= 1 else CheckStatus.FAIL
    return _check(
        "C2",
        CheckGroup.COLOR,
        result,
        True,
        [f"strong_color_count={strong_count}", "max_allowed=1"],
    )


def _c3_tone_diversity(outfit: VisionResponse) -> CheckResult:
    if len(outfit.garments) < 2:
        return _check(
            "C3",
            CheckGroup.COLOR,
            CheckStatus.NOT_APPLICABLE,
            False,
            ["garment_count<2"],
        )

    value_std = _value_std(outfit.garments)
    result = CheckStatus.PASS if 10 <= value_std <= 60 else CheckStatus.FAIL
    return _check(
        "C3",
        CheckGroup.COLOR,
        result,
        True,
        [f"value_std={value_std}", "expected_value_std_range=[10, 60]"],
    )


def _d1_vision_avg_confidence(outfit: VisionResponse) -> CheckResult:
    if not outfit.garments:
        return _check(
            "D1",
            CheckGroup.CONFIDENCE,
            CheckStatus.NOT_APPLICABLE,
            False,
            ["garment_count=0"],
        )

    avg_confidence = round(sum(g.confidence for g in outfit.garments) / len(outfit.garments), 2)
    result = CheckStatus.PASS if avg_confidence >= 0.6 else CheckStatus.FAIL
    return _check(
        "D1",
        CheckGroup.CONFIDENCE,
        result,
        True,
        [f"vision_avg_confidence={avg_confidence}", "minimum=0.6"],
    )


def _d2_dresscode_resolution_confident(context: ContextResponse) -> CheckResult:
    tier = context.dress_code.tier
    confidence = context.dress_code.extraction_confidence
    passed = tier == DressCodeTier.TIER1 or (tier == DressCodeTier.TIER2_LIVE and confidence >= 0.7)
    return _check(
        "D2",
        CheckGroup.CONFIDENCE,
        CheckStatus.PASS if passed else CheckStatus.FAIL,
        True,
        [f"tier={tier.value}", f"extraction_confidence={confidence}"],
    )


def _required_slot_garments(garments_by_slot: dict[GarmentSlot, list[Garment]]) -> list[Garment]:
    garments = []
    for slot in (GarmentSlot.TOP, GarmentSlot.BOTTOM, GarmentSlot.SHOES):
        garment = _primary_garment(garments_by_slot, slot)
        if garment is not None:
            garments.append(garment)
    return garments


def _missing_required_slots(garments_by_slot: dict[GarmentSlot, list[Garment]]) -> list[str]:
    return [
        slot.value
        for slot in (GarmentSlot.TOP, GarmentSlot.BOTTOM, GarmentSlot.SHOES)
        if not garments_by_slot.get(slot)
    ]


def _formality_score(garment: Garment) -> int:
    return FORMALITY_SCORE[garment.formality_label]


def _std(values: list[int]) -> float:
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _contrast_score(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> int:
    return round(abs(_brightness(rgb1) - _brightness(rgb2)) / 3.75)


def _saturation(rgb: tuple[int, int, int]) -> float:
    high = max(rgb)
    low = min(rgb)
    if high == 0:
        return 0
    return (high - low) / high


def _value_std(garments: list[Garment]) -> int:
    values = [max(garment.primary_color.rgb) for garment in garments]
    return round(_std(values) / 2.55)


def _brightness(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return 0.299 * red + 0.587 * green + 0.114 * blue


def _fmt_list(values: list[object]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"
