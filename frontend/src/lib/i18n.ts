import type { CheckGroup } from "@/api/schemas";

export const GROUP_LABELS: Record<CheckGroup, string> = {
  dresscode: "드레스코드 충족",
  consistency: "의류 간 일관성",
  color: "색상",
  environment: "날씨/환경 적합성",
  confidence: "분석 신뢰도",
};

export const CITY_OPTIONS = [
  { value: "KR-SEOUL", label: "서울" },
  { value: "KR-BUSAN", label: "부산" },
  { value: "KR-INCHEON", label: "인천" },
  { value: "KR-DAEGU", label: "대구" },
  { value: "KR-DAEJEON", label: "대전" },
  { value: "KR-GWANGJU", label: "광주" },
  { value: "KR-SUWON", label: "수원" },
  { value: "KR-ULSAN", label: "울산" },
] as const;
