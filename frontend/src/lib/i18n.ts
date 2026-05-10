import type { CheckGroup } from "@/api/schemas";

export const GROUP_LABELS: Record<CheckGroup, string> = {
  dresscode: "드레스코드 충족",
  consistency: "의류 간 일관성",
  color: "색상",
  confidence: "분석 신뢰도",
};

