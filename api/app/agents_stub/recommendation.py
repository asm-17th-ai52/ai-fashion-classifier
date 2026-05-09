"""Stub recommendation sub-graph. Produces schema-valid RecommendationResponse.

This stub is intentionally simplistic; the real Recommendation Agent owner
will replace it with the deterministic 13-check evaluator + LLM Narrator
described in docs/specs/04-agent-recommendation-spec.md.
"""
from __future__ import annotations

import time
from typing import Any

from app.orchestration.state_helpers import state_get
from app.schemas import (
    Check,
    CheckGroup,
    GarmentSlot,
    RecommendationResponse,
    Score,
    Suggestion,
)
from app.schemas.enums import FORMALITY_SCORE, SuggestionAction as ActionType
from app.schemas.recommendation import SuggestionAction


def _by_slot(garments) -> dict[str, Any]:
    out = {}
    for g in garments:
        out[g.slot.value] = g
    return out


def _stub_recommendation(state: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    session_id = state_get(state, "session_id", "sess_unknown")
    outfit = state_get(state, "outfit")
    context = state_get(state, "context")
    dc = context.dress_code
    garments = _by_slot(outfit.garments)

    checks: list[Check] = []

    def add_check(
        cid: str,
        group: CheckGroup,
        label: str,
        applicable: bool,
        passed: bool,
        is_blocker: bool,
        facts: list[str],
    ) -> None:
        result = "not_applicable" if not applicable else ("pass" if passed else "fail")
        checks.append(
            Check(
                id=cid,
                group=group,
                label=label,
                result=result,
                applicable=applicable,
                is_blocker=is_blocker,
                evidence_facts=facts,
            )
        )

    # ---- Group A — dresscode ----
    for slot, cid in [("top", "A1"), ("bottom", "A2"), ("shoes", "A3")]:
        g = garments.get(slot)
        expected = getattr(dc.expected_categories, slot)
        if g is None or not expected:
            add_check(
                cid,
                CheckGroup.dresscode,
                f"{slot} 카테고리가 기대 범위에 포함",
                applicable=g is not None and bool(expected),
                passed=False,
                is_blocker=False,
                facts=[],
            )
        else:
            add_check(
                cid,
                CheckGroup.dresscode,
                f"{slot} 카테고리가 기대 범위에 포함",
                applicable=True,
                passed=g.category in expected,
                is_blocker=False,
                facts=[
                    f"event_type={dc.event_type} expects {slot} in {expected}",
                    f"current {slot} category={g.category}",
                ],
            )

    # A4 — formality avg in expected range (blocker)
    formality_vals = [
        FORMALITY_SCORE[g.formality_label.value]
        for g in outfit.garments
        if g.slot.value in ("top", "bottom", "shoes")
    ]
    avg = round(sum(formality_vals) / len(formality_vals)) if formality_vals else 0
    lo, hi = dc.expected_formality_range
    add_check(
        "A4",
        CheckGroup.dresscode,
        "평균 포멀니스가 기대 범위 안",
        applicable=bool(formality_vals),
        passed=lo <= avg <= hi,
        is_blocker=True,
        facts=[
            f"expected_formality_range=[{lo}, {hi}]",
            f"outfit_formality_avg={avg}",
        ],
    )

    # A5 — no avoid tones (stub assumes pass; full check needs RGB→tone lookup)
    add_check(
        "A5",
        CheckGroup.dresscode,
        "회피 색상 톤 없음",
        applicable=bool(dc.color_guidance.avoid_tones),
        passed=True,
        is_blocker=False,
        facts=[f"avoid_tones={dc.color_guidance.avoid_tones}"],
    )

    # ---- Group B — consistency ----
    spread_ok = (
        max(formality_vals) - min(formality_vals) <= 30 if formality_vals else True
    )
    add_check(
        "B1",
        CheckGroup.consistency,
        "포멀니스 분산 임계 이하",
        applicable=bool(formality_vals),
        passed=spread_ok,
        is_blocker=False,
        facts=[f"formality_values={formality_vals}"],
    )
    add_check(
        "B2",
        CheckGroup.consistency,
        "top 슬롯 중복 없음",
        applicable=True,
        passed=sum(1 for g in outfit.garments if g.slot == GarmentSlot.top) <= 1,
        is_blocker=False,
        facts=[],
    )
    required = {"top", "bottom", "shoes"}
    present = {g.slot.value for g in outfit.garments}
    add_check(
        "B3",
        CheckGroup.consistency,
        "필수 슬롯(top/bottom/shoes) 모두 존재",
        applicable=True,
        passed=required.issubset(present),
        is_blocker=True,
        facts=[f"present_slots={sorted(present)}"],
    )

    # ---- Group C — color (stub: always pass) ----
    for cid, label in [
        ("C1", "상의-하의 대비 적절"),
        ("C2", "강한 채도 의류 1개 이하"),
        ("C3", "명도 다양성 적절"),
    ]:
        add_check(cid, CheckGroup.color, label, True, True, False, [])

    # ---- Group D — confidence ----
    avg_conf = (
        sum(g.confidence for g in outfit.garments) / len(outfit.garments)
        if outfit.garments
        else 0.0
    )
    add_check(
        "D1",
        CheckGroup.confidence,
        "Vision 평균 confidence ≥ 0.6",
        applicable=True,
        passed=avg_conf >= 0.6,
        is_blocker=False,
        facts=[f"avg_confidence={avg_conf:.2f}"],
    )
    add_check(
        "D2",
        CheckGroup.confidence,
        "드레스코드 해석 신뢰도 충분",
        applicable=True,
        passed=dc.tier.value == "tier1" or dc.extraction_confidence >= 0.7,
        is_blocker=False,
        facts=[f"tier={dc.tier.value}", f"extraction_confidence={dc.extraction_confidence}"],
    )

    # ---- Score ----
    groups = ["dresscode", "consistency", "color", "confidence"]
    group_scores: dict[str, float] = {}
    for grp in groups:
        applicable_checks = [c for c in checks if c.group.value == grp and c.applicable]
        if not applicable_checks:
            continue
        passed = sum(1 for c in applicable_checks if c.result == "pass")
        group_scores[grp] = round(passed / len(applicable_checks), 2)
    raw = (
        round(sum(group_scores.values()) / len(group_scores) * 100)
        if group_scores
        else 0
    )
    blockers_failed = [c.id for c in checks if c.is_blocker and c.result == "fail"]
    cap_applied = "blocker_cap_50" if blockers_failed else None
    overall = min(raw, 50) if blockers_failed else raw
    score = Score(
        overall=overall,
        group_scores=group_scores,
        blocker_failed=bool(blockers_failed),
        cap_applied=cap_applied,
    )

    # ---- Suggestions (stub: 1 swap suggestion if A3 failed) ----
    suggestions: list[Suggestion] = []
    a3 = next((c for c in checks if c.id == "A3"), None)
    if a3 and a3.result == "fail" and dc.expected_categories.shoes:
        target = dc.expected_categories.shoes[0]
        current = garments["shoes"].category if "shoes" in garments else "unknown"
        suggestions.append(
            Suggestion(
                id="sg_1",
                fixes_check_ids=["A3"],
                action=SuggestionAction(
                    type=ActionType.swap,
                    target_slot=GarmentSlot.shoes,
                    **{"from": current},
                    to=target,
                ),
                rationale_facts=[
                    f"event_type={dc.event_type} expects shoes in {dc.expected_categories.shoes}",
                    f"current shoes category={current}",
                ],
                expected_overall_delta=8,
                removes_blocker=False,
                user_facing_text=f"신발을 {target}(으)로 교체",
            )
        )

    explanation = (
        f"종합 {overall}점. 그룹 pass-rate: {group_scores}. "
        f"실패 블로커: {blockers_failed if blockers_failed else '없음'}."
    )

    response = RecommendationResponse(
        session_id=session_id,
        score=score,
        checks=checks,
        blockers_failed=blockers_failed,
        suggestions=suggestions,
        explanation=explanation[:400],
    )

    elapsed = int((time.monotonic() - t0) * 1000)
    return {
        "recommendation": response,
        "agent_latencies_ms": {"recommendation": elapsed},
    }


recommendation_subgraph_stub = _stub_recommendation
