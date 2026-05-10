from .checks import FORMALITY_SCORE
from .schemas import (
    Action,
    ActionType,
    CheckResult,
    CheckStatus,
    ContextResponse,
    FormalityLabel,
    Garment,
    GarmentSlot,
    Suggestion,
    VisionResponse,
)
from .scoring import calculate_score
from .simulator import simulate_action


SLOT_LABELS = {
    GarmentSlot.TOP: "상의",
    GarmentSlot.BOTTOM: "하의",
    GarmentSlot.OUTER: "아우터",
    GarmentSlot.SHOES: "신발",
}

EVENT_LABELS = {
    "interview": "면접",
}

ITEM_LABELS = {
    "loafers": "로퍼",
    "dress_shoes": "구두",
}

TARGET_FORMALITY = {
    GarmentSlot.TOP: (FormalityLabel.BUSINESS_FORMAL, 85),
    GarmentSlot.BOTTOM: (FormalityLabel.BUSINESS_FORMAL, 85),
    GarmentSlot.SHOES: (FormalityLabel.BUSINESS_CASUAL, 65),
}


def build_suggestions(
    outfit: VisionResponse,
    context: ContextResponse,
    checks: list[CheckResult],
) -> list[Suggestion]:
    failed_checks = [check for check in checks if check.applicable and check.result == CheckStatus.FAIL]
    if not failed_checks:
        return []

    current_overall = calculate_score(checks).overall
    candidates = [
        _build_candidate(outfit, context, checks, failed_check, current_overall)
        for failed_check in failed_checks
    ]
    suggestions = [candidate for candidate in candidates if candidate is not None]
    suggestions = _dedupe_suggestions(suggestions)
    suggestions.sort(
        key=lambda suggestion: (
            not suggestion.removes_blocker,
            -suggestion.expected_overall_delta,
            suggestion.id,
        )
    )
    return [
        suggestion.model_copy(update={"id": f"sg_{idx}"})
        for idx, suggestion in enumerate(suggestions[:3], start=1)
    ]


def build_explanation(
    outfit: VisionResponse,
    context: ContextResponse,
    checks: list[CheckResult],
    suggestions: list[Suggestion],
) -> str:
    failed_ids = {check.id for check in checks if check.result == CheckStatus.FAIL}
    low, high = context.dress_code.expected_formality_range
    avg = _current_formality_avg(outfit)

    if not failed_ids:
        return (
            f"{_event_label(context)} 기준의 13개 체크를 모두 통과했습니다. "
            f"평균 포멀니스는 {avg}점으로 기대 범위 {low}~{high} 안에 있습니다."
        )

    first = suggestions[0] if suggestions else None
    if "B3" in failed_ids and first is not None:
        missing = _missing_required_slots(outfit)
        missing_text = ", ".join(SLOT_LABELS[slot] for slot in missing) or "필수 슬롯"
        return (
            f"필수 슬롯 중 {missing_text} 정보가 없어 B3 핵심 미스가 발생했습니다. "
            f"{_action_target_text(first.action)}를 추가하면 필수 슬롯 조건을 충족합니다."
        )

    if "A4" in failed_ids and first is not None:
        simulated_avg = _simulated_formality_avg(outfit, first.action)
        return (
            f"{_event_label(context)} 기대 포멀니스 {low}~{high} 대비 현재 평균은 {avg}점입니다. "
            f"신발을 {_action_target_text(first.action)}로 교체하면 평균 {simulated_avg}점으로 올라가 핵심 미스가 해소됩니다."
        )

    failed_labels = ", ".join(sorted(failed_ids))
    return f"체크리스트 기반 평가에서 {failed_labels} 항목 조정이 필요합니다."


def _build_candidate(
    outfit: VisionResponse,
    context: ContextResponse,
    checks: list[CheckResult],
    failed_check: CheckResult,
    current_overall: int,
) -> Suggestion | None:
    action = _action_for_failed_check(outfit, context, failed_check)
    if action is None:
        return None

    _, simulated_checks, simulated_score = simulate_action(outfit, context, action)
    if _introduces_regression(checks, simulated_checks):
        return None

    fixed_ids = _fixed_check_ids(checks, simulated_checks)
    if failed_check.id not in fixed_ids:
        return None

    expected_delta = max(0, simulated_score.overall - current_overall)
    if expected_delta < 2:
        return None

    return Suggestion(
        id=f"candidate_{failed_check.id}",
        fixes_check_ids=fixed_ids,
        action=action,
        rationale_facts=_rationale_facts(outfit, context, checks, action, fixed_ids),
        expected_overall_delta=expected_delta,
        removes_blocker=any(_check_by_id(checks, check_id).is_blocker for check_id in fixed_ids),
        user_facing_text=_user_facing_text(outfit, action, fixed_ids),
    )


def _action_for_failed_check(
    outfit: VisionResponse,
    context: ContextResponse,
    failed_check: CheckResult,
) -> Action | None:
    if failed_check.id == "B3":
        missing = _missing_required_slots(outfit)
        if not missing:
            return None
        slot = missing[0]
        return Action(type=ActionType.ADD, target_slot=slot.value, to=_target_item(context, slot))

    if failed_check.id in {"A3", "A4", "B1"}:
        slot = _lowest_formality_slot(outfit) or GarmentSlot.SHOES
        current = _primary_garment(outfit, slot)
        return Action(
            type=ActionType.SWAP,
            target_slot=slot.value,
            from_=_current_item(current),
            to=_target_item(context, slot),
        )

    if failed_check.id in {"A1", "A2"}:
        slot = GarmentSlot.TOP if failed_check.id == "A1" else GarmentSlot.BOTTOM
        current = _primary_garment(outfit, slot)
        return Action(
            type=ActionType.SWAP,
            target_slot=slot.value,
            from_=_current_item(current),
            to=_target_item(context, slot),
        )

    if failed_check.id == "A5":
        return Action(type=ActionType.RECOLOR, to=_preferred_tone(context))

    if failed_check.id in {"C1", "C2", "C3"}:
        return Action(type=ActionType.RECOLOR, target_slot="top", to=_preferred_tone(context))

    return None


def _dedupe_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    deduped: dict[tuple[object, ...], Suggestion] = {}
    for suggestion in suggestions:
        key = (
            suggestion.action.type,
            suggestion.action.target_slot,
            suggestion.action.from_,
            suggestion.action.to,
        )
        existing = deduped.get(key)
        if existing is None or _suggestion_rank(suggestion) < _suggestion_rank(existing):
            deduped[key] = suggestion
    return list(deduped.values())


def _suggestion_rank(suggestion: Suggestion) -> tuple[bool, int]:
    return (not suggestion.removes_blocker, -suggestion.expected_overall_delta)


def _rationale_facts(
    outfit: VisionResponse,
    context: ContextResponse,
    checks: list[CheckResult],
    action: Action,
    fixed_ids: list[str],
) -> list[str]:
    facts: list[str] = []
    for check_id in fixed_ids:
        if check_id == "A3":
            facts.append(_check_by_id(checks, check_id).evidence_facts[0])
        elif check_id == "B3":
            facts.extend(_check_by_id(checks, check_id).evidence_facts)

    if action.target_slot == "shoes" and action.type == ActionType.SWAP:
        current_avg = _current_formality_avg(outfit)
        next_avg = _simulated_formality_avg(outfit, action)
        current_std = _current_formality_std(outfit)
        next_std = _simulated_formality_std(outfit, action)
        facts.append(f"swapping shoes raises outfit_formality_avg from {current_avg} to {next_avg}")
        facts.append(f"swapping shoes lowers formality_std from {current_std} to {next_std}")
    elif action.type == ActionType.ADD and action.target_slot == "shoes":
        facts.append(f"adding {_target_name(action)} completes required slots")
    elif action.type == ActionType.RECOLOR:
        facts.append(f"preferred_tones={_fmt_list(context.dress_code.color_guidance.preferred_tones)}")

    return _unique(facts)


def _user_facing_text(outfit: VisionResponse, action: Action, fixed_ids: list[str]) -> str:
    target = _action_target_text(action)
    if action.type == ActionType.ADD:
        return f"누락된 신발 슬롯에 {target}를 추가하면 필수 슬롯 미스가 해소됩니다."
    if action.type == ActionType.SWAP and "A4" in fixed_ids:
        current_avg = _current_formality_avg(outfit)
        next_avg = _simulated_formality_avg(outfit, action)
        return f"신발을 {target}로 교체하면 평균 포멀니스가 {current_avg}점에서 {next_avg}점으로 올라가고 핵심 미스가 해소됩니다."
    if action.type == ActionType.SWAP:
        slot = SLOT_LABELS.get(GarmentSlot(action.target_slot), "항목") if action.target_slot else "항목"
        return f"{slot}을 {target}로 교체하면 실패한 체크를 개선할 수 있습니다."
    return f"색상을 {target} 계열로 조정하면 실패한 색상 체크를 개선할 수 있습니다."


def _target_item(context: ContextResponse, slot: GarmentSlot) -> str:
    categories = getattr(context.dress_code.expected_categories, slot.value, [])
    category = _preferred_category(categories, slot)
    _, formality = TARGET_FORMALITY.get(slot, (FormalityLabel.BUSINESS_CASUAL, 65))
    if slot in TARGET_FORMALITY:
        return f"{category} (formality>={formality})"
    return category


def _preferred_category(categories: list[str], slot: GarmentSlot) -> str:
    if slot == GarmentSlot.SHOES and "loafers" in categories:
        return "loafers"
    return categories[0] if categories else slot.value


def _preferred_tone(context: ContextResponse) -> str:
    tones = context.dress_code.color_guidance.preferred_tones
    return tones[0] if tones else "neutral"


def _current_item(garment: Garment | None) -> str | None:
    if garment is None:
        return None
    return f"{garment.category} (formality={FORMALITY_SCORE[garment.formality_label]})"


def _target_name(action: Action) -> str:
    if not action.to:
        return ""
    return action.to.split(" (", 1)[0]


def _action_target_text(action: Action) -> str:
    name = _target_name(action) or action.to or "권장 항목"
    return ITEM_LABELS.get(name, name)


def _event_label(context: ContextResponse) -> str:
    return EVENT_LABELS.get(context.dress_code.event_type, context.dress_code.event_type)


def _current_formality_avg(outfit: VisionResponse) -> int:
    garments = _required_slot_garments(outfit)
    if not garments:
        return 0
    return round(sum(_formality_score(garment) for garment in garments) / len(garments))


def _simulated_formality_avg(outfit: VisionResponse, action: Action) -> int:
    values = _simulated_formality_values(outfit, action)
    if not values:
        return 0
    return round(sum(values) / len(values))


def _current_formality_std(outfit: VisionResponse) -> int:
    return _std([_formality_score(garment) for garment in _required_slot_garments(outfit)])


def _simulated_formality_std(outfit: VisionResponse, action: Action) -> int:
    return _std(_simulated_formality_values(outfit, action))


def _simulated_formality_values(outfit: VisionResponse, action: Action) -> list[int]:
    values: list[int] = []
    target_slot = GarmentSlot(action.target_slot) if action.target_slot else None
    target_value = _target_formality_value(target_slot)
    for slot in (GarmentSlot.TOP, GarmentSlot.BOTTOM, GarmentSlot.SHOES):
        garment = _primary_garment(outfit, slot)
        if garment is None:
            if action.type == ActionType.ADD and target_slot == slot:
                values.append(target_value)
            continue
        values.append(target_value if action.type == ActionType.SWAP and target_slot == slot else _formality_score(garment))
    return values


def _target_formality_value(slot: GarmentSlot | None) -> int:
    if slot is None:
        return 65
    return TARGET_FORMALITY.get(slot, (FormalityLabel.BUSINESS_CASUAL, 65))[1]


def _lowest_formality_slot(outfit: VisionResponse) -> GarmentSlot | None:
    garments = _required_slot_garments(outfit)
    if not garments:
        return None
    return min(garments, key=_formality_score).slot


def _required_slot_garments(outfit: VisionResponse) -> list[Garment]:
    garments = []
    for slot in (GarmentSlot.TOP, GarmentSlot.BOTTOM, GarmentSlot.SHOES):
        garment = _primary_garment(outfit, slot)
        if garment is not None:
            garments.append(garment)
    return garments


def _missing_required_slots(outfit: VisionResponse) -> list[GarmentSlot]:
    return [
        slot
        for slot in (GarmentSlot.TOP, GarmentSlot.BOTTOM, GarmentSlot.SHOES)
        if _primary_garment(outfit, slot) is None
    ]


def _primary_garment(outfit: VisionResponse, slot: GarmentSlot) -> Garment | None:
    return next((garment for garment in outfit.garments if garment.slot == slot), None)


def _formality_score(garment: Garment) -> int:
    return FORMALITY_SCORE[garment.formality_label]


def _std(values: list[int]) -> int:
    if not values:
        return 0
    mean = sum(values) / len(values)
    return round((sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5)


def _check_by_id(checks: list[CheckResult], check_id: str) -> CheckResult:
    return next(check for check in checks if check.id == check_id)


def _fixed_check_ids(
    checks: list[CheckResult],
    simulated_checks: list[CheckResult],
) -> list[str]:
    simulated_by_id = {check.id: check for check in simulated_checks}
    return [
        check.id
        for check in checks
        if check.result == CheckStatus.FAIL
        and simulated_by_id[check.id].result == CheckStatus.PASS
    ]


def _introduces_regression(
    checks: list[CheckResult],
    simulated_checks: list[CheckResult],
) -> bool:
    simulated_by_id = {check.id: check for check in simulated_checks}
    return any(
        check.result == CheckStatus.PASS
        and simulated_by_id[check.id].result == CheckStatus.FAIL
        for check in checks
    )


def _unique(values: list[str]) -> list[str]:
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _fmt_list(values: list[object]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"
