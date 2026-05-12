import type { SessionResponse, SimulateResponse, Check } from "../schemas";

// Scenario: business_meeting
// Outfit: white dress shirt + navy chino + brown loafers
// Fails: A1(shoes), A3(bottom), B2(style consistency), C2(saturation)
// Not applicable: A5(winter coat)

export const MOCK_CHECKS: Check[] = [
  // ── Group A: dresscode ──────────────────────────────────────────────────────
  {
    id: "A1",
    group: "dresscode",
    label: "신발 카테고리가 기대 범위에 포함",
    result: "fail",
    applicable: true,
    is_blocker: false,
    evidence_facts: [
      "착용 신발: 로퍼 (casual 계열)",
      "business_meeting 기대 신발: 옥스퍼드, 더비, 몽크스트랩",
    ],
  },
  {
    id: "A2",
    group: "dresscode",
    label: "상의 카테고리가 기대 범위에 포함",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["착용 상의: 드레스 셔츠 (business_meeting 적합)"],
  },
  {
    id: "A3",
    group: "dresscode",
    label: "하의 카테고리가 기대 범위에 포함",
    result: "fail",
    applicable: true,
    is_blocker: false,
    evidence_facts: [
      "착용 하의: 치노 팬츠 (smart_casual 계열)",
      "business_meeting 기대 하의: 슬랙스, 정장 바지",
    ],
  },
  {
    id: "A4",
    group: "dresscode",
    label: "평균 포멀니스가 기대 범위 안",
    result: "pass",
    applicable: true,
    is_blocker: true,
    evidence_facts: [
      "평균 포멀니스 점수: 68",
      "business_meeting 기대 범위: 60–85",
    ],
  },
  {
    id: "A5",
    group: "dresscode",
    label: "한겨울 외투 착용 여부",
    result: "not_applicable",
    applicable: false,
    is_blocker: true,
    evidence_facts: ["캐주얼~비즈니스 복장 기준, 외투 검사 미해당"],
  },
  {
    id: "A6",
    group: "dresscode",
    label: "착장 색상이 드레스코드 기피 톤에 해당하지 않음",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["흰색·네이비 조합: business_meeting 권장 색상 범위 내"],
  },
  // ── Group B: consistency ────────────────────────────────────────────────────
  {
    id: "B1",
    group: "consistency",
    label: "top/bottom/shoes 포멀니스 표준편차 ≤ 15",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["포멀니스 SD: 10.2 (기준 ≤ 15)"],
  },
  {
    id: "B2",
    group: "consistency",
    label: "전체 착장 스타일 카테고리 일관성",
    result: "fail",
    applicable: true,
    is_blocker: false,
    evidence_facts: [
      "상의 포멀니스: business_formal (85)",
      "하의 포멀니스: smart_casual (45)",
      "신발 포멀니스: casual (20)",
      "스타일 혼재: formal + casual 조합",
    ],
  },
  {
    id: "B3",
    group: "consistency",
    label: "상의·하의 패턴 조합 적절성",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["상의: 솔리드, 하의: 솔리드 — 패턴 충돌 없음"],
  },
  // ── Group C: color ──────────────────────────────────────────────────────────
  {
    id: "C1",
    group: "color",
    label: "top-bottom ΔE2000 색차 ∈ [10, 50]",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["흰색–네이비 ΔE2000: 32.4 (기준 10–50 내)"],
  },
  {
    id: "C2",
    group: "color",
    label: "강한 채도 의류 ≤ 1개",
    result: "fail",
    applicable: true,
    is_blocker: false,
    evidence_facts: [
      "채도 ≥ 70 의류: 2개 (상의 채도 82, 신발 채도 78)",
      "기준: 강한 채도 의류 최대 1개",
    ],
  },
  {
    id: "C3",
    group: "color",
    label: "드레스코드 색상 가이드 준수",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["네이비·화이트 조합: business_meeting 권장 색상"],
  },
  // ── Group D: confidence ─────────────────────────────────────────────────────
  {
    id: "D1",
    group: "confidence",
    label: "Vision 평균 confidence ≥ 0.6",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["Vision 평균 confidence: 0.87"],
  },
  {
    id: "D2",
    group: "confidence",
    label: "Context tier 신뢰도 충분",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["Dress code tier: tier1 (RAG 매칭 점수 0.91)"],
  },
];

// Score:
// dresscode:   3/5 applicable = 0.60  (A1, A3 fail; A5 N/A)
// consistency: 2/3 applicable = 0.67  (B2 fail)
// color:       2/3 applicable = 0.67  (C2 fail)
// confidence:  2/2 applicable = 1.00
// overall = mean([0.60, 0.67, 0.67, 1.00]) * 100 ≈ 73
export const ORIGINAL_OVERALL = 73;

export const MOCK_SESSION: SessionResponse = {
  session_id: "mock-session-001",
  outfit: {
    session_id: "mock-session-001",
    person_detected: true,
    image_quality: { resolution_ok: true, frontal: true, occlusion_ratio: 0.05 },
    garments: [
      {
        slot: "top",
        category: "드레스 셔츠",
        primary_color: { rgb: [240, 240, 245], name: "화이트" },
        pattern: "solid",
        formality_label: "business_formal",
        confidence: 0.92,
      },
      {
        slot: "bottom",
        category: "치노 팬츠",
        primary_color: { rgb: [30, 50, 100], name: "네이비" },
        pattern: "solid",
        formality_label: "smart_casual",
        confidence: 0.88,
      },
      {
        slot: "shoes",
        category: "로퍼",
        primary_color: { rgb: [80, 50, 30], name: "브라운" },
        pattern: "solid",
        formality_label: "casual",
        confidence: 0.85,
      },
    ],
    warnings: [],
  },
  context: {
    dress_code: {
      tier: "tier1",
      evidence_quotes: [],
    },
  },
  recommendation: {
    session_id: "mock-session-001",
    score: {
      overall: ORIGINAL_OVERALL,
      method: "group_weighted_with_blocker_cap",
      group_scores: {
        dresscode: 0.60,
        consistency: 0.67,
        color: 0.67,
        confidence: 1.00,
      },
      blocker_failed: false,
      cap_applied: null,
    },
    checks: MOCK_CHECKS,
    blockers_failed: [],
    suggestions: [
      {
        id: "sg_1",
        fixes_check_ids: ["A1", "B2"],
        action: { type: "swap", target_slot: "shoes", from: "로퍼", to: "옥스퍼드" },
        rationale_facts: [
          "옥스퍼드는 business_meeting 기대 신발 범위에 포함",
          "옥스퍼드 포멀니스: business_formal (85) → 스타일 일관성 개선",
        ],
        expected_overall_delta: 10,
        removes_blocker: false,
        user_facing_text:
          "신발을 로퍼에서 옥스퍼드로 교체하면 드레스코드와 스타일 일관성이 개선됩니다.",
      },
      {
        id: "sg_2",
        fixes_check_ids: ["A3"],
        action: { type: "swap", target_slot: "bottom", from: "치노 팬츠", to: "슬랙스" },
        rationale_facts: [
          "슬랙스는 business_meeting 기대 하의 범위에 포함",
          "슬랙스 포멀니스: business_formal (85)",
        ],
        expected_overall_delta: 5,
        removes_blocker: false,
        user_facing_text:
          "하의를 치노에서 슬랙스로 교체하면 드레스코드 기대 범위에 부합합니다.",
      },
    ],
    explanation:
      "비즈니스 미팅 복장으로 상의와 전반적 포멀니스는 적합하나, 신발과 하의 카테고리가 기대 범위를 벗어났습니다. 스타일 일관성과 채도 조정이 필요합니다.",
  },
  meta: {
    latency_ms: 4230,
    tier2_triggered: false,
  },
};

// suggestions가 fix하는 check ID 매핑
const SUGGESTION_FIXES: Record<string, string[]> = {
  sg_1: ["A1", "B2"],
  sg_2: ["A3"],
};

export function computeSimulation(
  sessionId: string,
  appliedIds: string[]
): SimulateResponse {
  const flippedToPass = new Set(
    appliedIds.flatMap((id) => SUGGESTION_FIXES[id] ?? [])
  );

  const updatedChecks = MOCK_CHECKS.map((c) =>
    flippedToPass.has(c.id) ? { ...c, result: "pass" as const } : c
  );

  const groups = [
    "dresscode",
    "consistency",
    "color",
    "confidence",
  ] as const;

  const groupScores = Object.fromEntries(
    groups.map((g) => {
      const applicable = updatedChecks.filter((c) => c.group === g && c.applicable);
      const passed = applicable.filter((c) => c.result === "pass");
      return [g, applicable.length > 0 ? passed.length / applicable.length : 1];
    })
  ) as Record<(typeof groups)[number], number>;

  const simulated = Math.round(
    (Object.values(groupScores).reduce((a, b) => a + b, 0) / groups.length) * 100
  );

  return {
    session_id: sessionId,
    original_overall: ORIGINAL_OVERALL,
    simulated_overall: simulated,
    delta: simulated - ORIGINAL_OVERALL,
    applied: appliedIds.map((id) => ({
      id,
      individual_delta: (SUGGESTION_FIXES[id]?.length ?? 0) * 5,
      removes_blocker: false,
    })),
    simulated_score: {
      overall: simulated,
      method: "group_weighted_with_blocker_cap",
      group_scores: groupScores,
      blocker_failed: false,
      cap_applied: null,
    },
    checks_flipped: {
      to_pass: [...flippedToPass],
      to_fail: [],
    },
  };
}
