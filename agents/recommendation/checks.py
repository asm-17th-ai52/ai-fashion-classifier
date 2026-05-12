from math import atan2, cos, degrees, exp, radians, sin, sqrt

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

COLOR_ALIASES = {
    "black": "black",
    "검정": "black",
    "navy": "navy",
    "네이비": "navy",
    "gray": "gray",
    "grey": "gray",
    "회색": "gray",
    "진회색": "gray",
    "white": "white",
    "흰색": "white",
    "오프화이트": "white",
    "beige": "beige",
    "베이지": "beige",
    "red": "red",
    "빨강": "red",
    "yellow": "yellow",
    "노랑": "yellow",
    "neon": "neon",
    "green": "green",
    "연두": "green",
    "orange": "orange",
    "주황": "orange",
    "pink": "pink",
    "핑크": "pink",
    "coral": "coral",
    "코랄": "coral",
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
    avoid_tones = {
        _canonical_tone(tone)
        for tone in context.dress_code.color_guidance.avoid_tones
    }
    color_names = {
        _canonical_color_name(garment)
        for garment in outfit.garments
    }
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
    return round(_delta_e2000(_rgb_to_lab(rgb1), _rgb_to_lab(rgb2)))


def _saturation(rgb: tuple[int, int, int]) -> float:
    high = max(rgb)
    low = min(rgb)
    if high == 0:
        return 0
    return (high - low) / high


def _value_std(garments: list[Garment]) -> int:
    values = [max(garment.primary_color.rgb) for garment in garments]
    return round(_std(values) / 2.55)


def _fmt_list(values: list[object]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def _canonical_color_name(garment: Garment) -> str:
    color_name = garment.primary_color.name.strip().lower()
    if color_name in COLOR_ALIASES:
        return COLOR_ALIASES[color_name]
    return _rgb_to_tone(garment.primary_color.rgb)


def _canonical_tone(tone: str) -> str:
    return COLOR_ALIASES.get(tone.strip().lower(), tone.strip().lower())


def _rgb_to_tone(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb
    saturation = _saturation(rgb)
    value = max(rgb)
    if value < 55:
        return "black"
    if saturation < 0.12:
        if value > 210:
            return "white"
        return "gray"

    hue = degrees(atan2(sqrt(3) * (green - blue), 2 * red - green - blue))
    if hue < 0:
        hue += 360
    if hue < 20 or hue >= 340:
        return "red"
    if hue < 45:
        return "orange"
    if hue < 75:
        return "yellow"
    if hue < 170:
        return "green"
    if hue < 255:
        return "navy"
    if hue < 330:
        return "pink"
    return "red"


def _rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    red, green, blue = [_srgb_to_linear(channel / 255) for channel in rgb]
    x = red * 0.4124564 + green * 0.3575761 + blue * 0.1804375
    y = red * 0.2126729 + green * 0.7151522 + blue * 0.0721750
    z = red * 0.0193339 + green * 0.1191920 + blue * 0.9503041

    fx = _lab_f(x / 0.95047)
    fy = _lab_f(y)
    fz = _lab_f(z / 1.08883)
    return (
        116 * fy - 16,
        500 * (fx - fy),
        200 * (fy - fz),
    )


def _srgb_to_linear(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _lab_f(value: float) -> float:
    if value > 0.008856:
        return value ** (1 / 3)
    return 7.787 * value + 16 / 116


def _delta_e2000(
    lab1: tuple[float, float, float],
    lab2: tuple[float, float, float],
) -> float:
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1 = sqrt(a1 ** 2 + b1 ** 2)
    c2 = sqrt(a2 ** 2 + b2 ** 2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - sqrt((c_bar ** 7) / (c_bar ** 7 + 25 ** 7)))
    a1_prime = (1 + g) * a1
    a2_prime = (1 + g) * a2
    c1_prime = sqrt(a1_prime ** 2 + b1 ** 2)
    c2_prime = sqrt(a2_prime ** 2 + b2 ** 2)
    h1_prime = _hue_degrees(a1_prime, b1)
    h2_prime = _hue_degrees(a2_prime, b2)

    delta_l_prime = l2 - l1
    delta_c_prime = c2_prime - c1_prime
    delta_h_prime = _delta_h_prime(c1_prime, c2_prime, h1_prime, h2_prime)
    delta_h_term = 2 * sqrt(c1_prime * c2_prime) * sin(radians(delta_h_prime / 2))

    l_bar_prime = (l1 + l2) / 2
    c_bar_prime = (c1_prime + c2_prime) / 2
    h_bar_prime = _mean_h_prime(c1_prime, c2_prime, h1_prime, h2_prime)

    t = (
        1
        - 0.17 * cos(radians(h_bar_prime - 30))
        + 0.24 * cos(radians(2 * h_bar_prime))
        + 0.32 * cos(radians(3 * h_bar_prime + 6))
        - 0.20 * cos(radians(4 * h_bar_prime - 63))
    )
    delta_theta = 30 * exp(-(((h_bar_prime - 275) / 25) ** 2))
    r_c = 2 * sqrt((c_bar_prime ** 7) / (c_bar_prime ** 7 + 25 ** 7))
    s_l = 1 + (0.015 * ((l_bar_prime - 50) ** 2)) / sqrt(20 + ((l_bar_prime - 50) ** 2))
    s_c = 1 + 0.045 * c_bar_prime
    s_h = 1 + 0.015 * c_bar_prime * t
    r_t = -sin(radians(2 * delta_theta)) * r_c

    return sqrt(
        (delta_l_prime / s_l) ** 2
        + (delta_c_prime / s_c) ** 2
        + (delta_h_term / s_h) ** 2
        + r_t * (delta_c_prime / s_c) * (delta_h_term / s_h)
    )


def _hue_degrees(a_value: float, b_value: float) -> float:
    if a_value == 0 and b_value == 0:
        return 0
    hue = degrees(atan2(b_value, a_value))
    return hue + 360 if hue < 0 else hue


def _delta_h_prime(
    c1_prime: float,
    c2_prime: float,
    h1_prime: float,
    h2_prime: float,
) -> float:
    if c1_prime * c2_prime == 0:
        return 0
    diff = h2_prime - h1_prime
    if abs(diff) <= 180:
        return diff
    if diff > 180:
        return diff - 360
    return diff + 360


def _mean_h_prime(
    c1_prime: float,
    c2_prime: float,
    h1_prime: float,
    h2_prime: float,
) -> float:
    if c1_prime * c2_prime == 0:
        return h1_prime + h2_prime
    if abs(h1_prime - h2_prime) <= 180:
        return (h1_prime + h2_prime) / 2
    if h1_prime + h2_prime < 360:
        return (h1_prime + h2_prime + 360) / 2
    return (h1_prime + h2_prime - 360) / 2
