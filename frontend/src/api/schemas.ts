import { z } from "zod";

// ─── Enums ────────────────────────────────────────────────────────────────────

export const StandardEventType = z.enum([
  "business_meeting",
  "interview",
  "presentation",
  "casual_date",
  "wedding_guest",
  "office_daily",
  "school_daily",
  "outdoor_activity",
  "general",
]);
export type StandardEventType = z.infer<typeof StandardEventType>;

export const STANDARD_EVENT_LABELS: Record<StandardEventType, string> = {
  business_meeting: "비즈니스 미팅",
  interview: "면접",
  presentation: "발표",
  casual_date: "캐주얼 데이트",
  wedding_guest: "결혼식 (하객)",
  office_daily: "사무실 출근",
  school_daily: "학교/캠퍼스",
  outdoor_activity: "야외 활동",
  general: "일반",
};

export const CheckGroup = z.enum([
  "dresscode",
  "consistency",
  "color",
  "environment",
  "confidence",
]);
export type CheckGroup = z.infer<typeof CheckGroup>;

export const DressCodeTier = z.enum(["tier1", "tier2_live", "fallback_general"]);
export type DressCodeTier = z.infer<typeof DressCodeTier>;

export const SuggestionAction = z.enum(["swap", "add", "remove", "recolor"]);
export type SuggestionAction = z.infer<typeof SuggestionAction>;

// ─── Upload form ──────────────────────────────────────────────────────────────

export const UploadFormSchema = z.object({
  image: z
    .instanceof(File)
    .refine((f) => f.size <= 10 * 1024 * 1024, "10MB 이하 이미지만 사용 가능합니다")
    .refine(
      (f) => ["image/jpeg", "image/png", "image/webp"].includes(f.type),
      "jpeg / png / webp 형식만 지원합니다"
    ),
  event_type: z.string().min(1, "일정 유형을 선택하거나 입력해 주세요"),
  event_type_is_custom: z.boolean().default(false),
  event_datetime: z.string().min(1, "일정 날짜/시간을 입력해 주세요"),
  city_code: z.string().min(1, "도시를 선택해 주세요"),
  is_indoor: z.boolean().default(false),
  allow_live_research: z.boolean().default(true),
});
export type UploadFormValues = z.infer<typeof UploadFormSchema>;

// ─── API response schemas ─────────────────────────────────────────────────────

export const CheckSchema = z.object({
  id: z.string().regex(/^[A-E][0-9]+$/),
  group: CheckGroup,
  label: z.string(),
  result: z.enum(["pass", "fail", "not_applicable"]),
  applicable: z.boolean(),
  is_blocker: z.boolean(),
  evidence_facts: z.array(z.string()),
});
export type Check = z.infer<typeof CheckSchema>;

export const SuggestionSchema = z.object({
  id: z.string(),
  fixes_check_ids: z.array(z.string()).min(1),
  action: z.object({
    type: SuggestionAction,
    target_slot: z.enum(["top", "bottom", "outer", "shoes"]).optional(),
    from: z.string().optional(),
    to: z.string().optional(),
  }),
  rationale_facts: z.array(z.string()).min(1),
  expected_overall_delta: z.number().int(),
  removes_blocker: z.boolean(),
  user_facing_text: z.string().max(200).optional(),
});
export type Suggestion = z.infer<typeof SuggestionSchema>;

export const ScoreSchema = z.object({
  overall: z.number().int().min(0).max(100),
  method: z.literal("group_weighted_with_blocker_cap"),
  group_scores: z.record(
    z.enum(["dresscode", "consistency", "color", "environment", "confidence"]),
    z.number().min(0).max(1)
  ),
  blocker_failed: z.boolean(),
  cap_applied: z.enum(["blocker_cap_50"]).nullable(),
});
export type Score = z.infer<typeof ScoreSchema>;

export const SessionResponseSchema = z.object({
  session_id: z.string(),
  outfit: z.unknown(),
  context: z.object({
    dress_code: z.object({
      tier: DressCodeTier,
      evidence_quotes: z
        .array(
          z.object({
            url: z.string().url(),
            quote: z.string().max(500),
            fetched_at: z.string(),
          })
        )
        .optional(),
    }),
    weather: z.object({
      available: z.boolean(),
      temperature_celsius: z.number().optional(),
      feels_like_celsius: z.number().optional(),
      precipitation_probability: z.number().min(0).max(1).optional(),
    }),
  }),
  recommendation: z.object({
    session_id: z.string(),
    score: ScoreSchema,
    checks: z.array(CheckSchema),
    blockers_failed: z.array(z.string()),
    suggestions: z.array(SuggestionSchema).max(3),
    explanation: z.string().max(400),
  }),
  meta: z.object({
    latency_ms: z.number().int(),
    tier2_triggered: z.boolean(),
  }),
});
export type SessionResponse = z.infer<typeof SessionResponseSchema>;

export const SimulateResponseSchema = z.object({
  session_id: z.string(),
  original_overall: z.number().int(),
  simulated_overall: z.number().int(),
  delta: z.number().int(),
  applied: z.array(
    z.object({
      id: z.string(),
      individual_delta: z.number().int(),
      removes_blocker: z.boolean(),
    })
  ),
  simulated_score: ScoreSchema,
  checks_flipped: z.object({
    to_pass: z.array(z.string()),
    to_fail: z.array(z.string()),
  }),
});
export type SimulateResponse = z.infer<typeof SimulateResponseSchema>;
