from .schemas import CheckGroup, CheckResult, CheckStatus, Score


def calculate_score(checks: list[CheckResult]) -> Score:
    group_scores = {
        group: _group_pass_rate(checks, group)
        for group in CheckGroup
        if _applicable_count(checks, group) > 0
    }
    raw_score = round((sum(group_scores.values()) / len(group_scores)) * 100) if group_scores else 0
    blockers_failed = get_blockers_failed(checks)
    blocker_failed = bool(blockers_failed)
    overall = min(raw_score, 50) if blocker_failed else raw_score

    return Score(
        overall=overall,
        method="group_weighted_with_blocker_cap",
        group_scores=group_scores,
        blocker_failed=blocker_failed,
        cap_applied="blocker_cap_50" if blocker_failed else None,
    )


def get_blockers_failed(checks: list[CheckResult]) -> list[str]:
    return [
        check.id
        for check in checks
        if check.is_blocker and check.applicable and check.result == CheckStatus.FAIL
    ]


def _group_pass_rate(checks: list[CheckResult], group: CheckGroup) -> float:
    applicable = [
        check
        for check in checks
        if check.group == group and check.result != CheckStatus.NOT_APPLICABLE
    ]
    if not applicable:
        return 0

    passed = sum(1 for check in applicable if check.result == CheckStatus.PASS)
    return round(passed / len(applicable), 2)


def _applicable_count(checks: list[CheckResult], group: CheckGroup) -> int:
    return sum(
        1
        for check in checks
        if check.group == group and check.result != CheckStatus.NOT_APPLICABLE
    )
