# 00. 프로젝트 개요 — AI 패션 상황 추천 Agent

## 1. 한 줄 정의
착장 이미지 + 일정/환경 컨텍스트를 입력받아, **정량화된 상황 적합도 점수**와 **설명 가능한 개선 제안**을 산출하는 Vision 기반 패션 Recommendation Agent.

## 2. 설계 철학 (가장 중요)

본 프로젝트는 "AI native 개발"을 지향한다. 모든 Agent 출력은 **재현 가능 / 검증 가능 / 정량화 가능**해야 하며, 다음 원칙을 따른다.

### 2.1 정량화 우선 (Quantification First)
- Agent의 모든 판단은 **숫자 점수 + 명시적 rubric**으로 환원되어야 한다.
- "어울린다 / 안 어울린다" 같은 주관 표현은 출력에 포함하지 않는다.
- 모든 점수는 `[0.0, 1.0]` 또는 `[0, 100]` 범위에서 명시된 rubric에 따라 산출한다.

### 2.2 명시적 제외 영역 (Out-of-Scope, 주관적 추론 금지)
다음과 같은 **사회심리·관계·인상 기반 추론**은 본 시스템에서 다루지 않는다.

| 제외 항목 | 이유 |
|---|---|
| "소개팅에서 호감도가 높을지" | 정량화 불가, 사회심리 추론 영역 |
| "신뢰감을 주는 인상" | 주관적, 평가자 편향 |
| "성격이 어떻게 보일지" | 외형 기반 인격 추론 — 윤리적 위험 |
| "이성에게 어떻게 비칠지" | 평가자 다양성 미반영 |
| "세련됨 / 촌스러움" 단독 평가 | rubric 정의 불가능 |
| 얼굴 인식 / 신체 비율 평가 | 개인정보 + 외모 평가 윤리 위험 |
| 인종·성별·연령 추론 | 편향 위험 |

### 2.3 다루는 정량적 차원 (In-Scope Quantitative Dimensions)
| 차원 | 입력 | 산출 | 단위 |
|---|---|---|---|
| **포멀니스(Formality)** | 의류 카테고리·소재 라벨 | 0~100 점수 | rubric 기반 |
| **드레스코드 적합도** | 일정 유형 → 드레스코드 RAG | 0.0~1.0 매칭률 | 코사인 거리 |
| **온도 적합도(Thermal Fit)** | 외기온도 / 의류 보온지수 | -1.0 ~ +1.0 | 회귀 모델 |
| **강수 대비도** | 강수확률 / 강수강도 / 의류 방수성 | 0.0~1.0 | rubric |
| **색 대비(Color Contrast)** | 의류 RGB → CIELAB ΔE | 0~100 | ΔE2000 |
| **톤 균형(Tone Balance)** | 명도/채도 분포 | 0.0~1.0 | 표준편차 정규화 |
| **포멀니스 일관성** | 상의/하의/신발 포멀니스 분산 | 0.0~1.0 | 1 - normalized variance |
| **상황 적합도(종합)** | 위 차원의 가중합 | 0~100 | 명시적 가중치 |

### 2.4 설명 가능성 (Explainability)
- 모든 점수는 **차원별 sub-score** + **수정 시 점수 증가량**을 반환한다.
- "왜 이 점수인지"는 차원별 contribution으로 자동 설명된다.
- LLM의 자유 서술은 **사실 보고형(fact-reporting)**으로 제한한다. (예: "신발 포멀니스 32점, 상의 포멀니스 78점 → 일관성 분산 0.46")

### 2.5 결정성(Determinism) 우선
- 동일 입력 → 동일 출력. LLM 호출은 `temperature=0`, JSON 강제, schema validation.
- LLM 출력은 항상 schema 검증을 거치며 실패 시 재시도(최대 2회) 후 fallback 룰 적용.

## 3. MVP 범위

### 포함 (3주)
- 착장 단일 이미지 분석 (1인, 정면)
- 의류 속성 추출(JSON) — 상의/하의/외투/신발
- 일정 유형 + 외부 기온/강수 컨텍스트 반영
- 정량 점수 산출 (8개 차원)
- 1~3개 구체적 개선 제안 생성

### 제외
- 쇼핑 연동 / SNS / 실시간 영상 / 장기 사용자 메모리
- 얼굴/체형 분석 / 트렌드 분석 / 가격 추천
- 주관적 인상 평가 (위 2.2 항목 전체)

## 4. 대상 사용자
- 20~30대 직장인 / 대학생
- 미팅·면접·발표 등 **공식적 일정 전 객관적 점검**이 필요한 사용자
- 패션 도메인 지식이 적지만 "이 정도면 괜찮은가?"의 정량적 답을 원하는 사용자

## 5. 핵심 가치
> 단순 코디 추천이 아니라, **현재 착장이 현재 상황(일정 + 날씨)에 맞는지를 정량 지표로 판정하고, 점수를 올릴 구체적 행동 1~3개를 제안한다.**

## 6. 성공 지표 (KPI)

| 지표 | 정의 | 측정 방법 | 목표 |
|---|---|---|---|
| Schema Pass Rate | LLM 출력이 schema 검증 통과한 비율 | 서버 로그 | ≥ 98% |
| Score Reproducibility | 동일 입력 5회 호출 시 종합 점수 표준편차 | 자동 테스트 | ≤ 2.0 (0~100 기준) |
| Latency (P95) | 업로드 → 결과 표시 | 클라이언트 측정 | ≤ 8초 |
| Suggestion Acceptance | 제안 카드 "수용/거절" 클릭 비율 | 프론트 이벤트 | ≥ 50% |
| Score-Suggestion Coherence | 제안 적용 시 종합 점수 시뮬레이션 증가량 | 자동 검증 | ≥ +5점 |

## 7. 팀 구성 (5인)
| 역할 | 인원 | 책임 문서 |
|---|---|---|
| Vision Agent 개발 | 1 | `02-agent-vision-spec.md` |
| Context Agent 개발 | 1 | `03-agent-context-spec.md` |
| Recommendation Agent 개발 | 1 | `04-agent-recommendation-spec.md` |
| Backend 개발 | 1 | `05-backend-spec.md` |
| Frontend 개발 | 1 | `06-frontend-spec.md` |

상세 협업 인터페이스는 `08-roles-and-handoffs.md` 참조.

## 8. 문서 맵
```
docs/specs/
├── 00-overview.md              # 본 문서
├── 01-architecture.md          # 시스템 아키텍처
├── 02-agent-vision-spec.md     # Vision Agent
├── 03-agent-context-spec.md    # Context Agent
├── 04-agent-recommendation-spec.md  # Recommendation Agent
├── 05-backend-spec.md          # Backend (API Gateway / 오케스트레이션)
├── 06-frontend-spec.md         # Frontend (React)
├── 07-data-contracts.md        # JSON 스키마 / API 계약 (모든 역할 공통)
└── 08-roles-and-handoffs.md    # 역할 분담 / 인터페이스 / 마일스톤
```
