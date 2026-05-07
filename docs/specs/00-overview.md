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

### 2.3 평가 방식 — 이분법 체크리스트 (Binary Checklist)
본 시스템은 **연속값 sub-score(0~100) + 가중합** 대신 **13개의 binary 체크 항목**을 평가한다.
각 체크는 `pass / fail / not_applicable` 셋 중 하나로 결정적 함수가 산출한다.

| 그룹 | 체크 수 | 예시 |
|---|---|---|
| Group A: 드레스코드 충족 | 5 | 신발 카테고리가 기대 범위에 포함, 평균 포멀니스가 기대 범위 안 |
| Group B: 일관성 | 3 | top/bottom/shoes 포멀니스 표준편차 ≤ 15 |
| Group C: 색상 | 3 | top-bottom ΔE2000 ∈ [10, 50], 강한 채도 의류 ≤ 1개 |
| Group D: 신뢰도 메타 | 2 | Vision 평균 confidence ≥ 0.6, Context tier 신뢰도 |

**점수 산출:**
```
group_pass_rate(g) = passed(g) / applicable(g)
overall = mean(group_pass_rate) * 100
if any blocker check failed: overall = min(overall, 50)
```

가중치 튜닝 없이 그룹별 동등 가중. blocker 체크(예: A5 포멀니스 격차, B3 필수 슬롯 누락) 실패 시 cap 적용. 상세는 `04-agent-recommendation-spec.md` 참조.

### 2.4 설명 가능성 (Explainability)
- 모든 점수 변동의 원인은 정확히 N개의 failed check로 설명된다.
- 각 failed check는 자기 `evidence_facts` 와 `fix_template` 을 갖는다 → 제안과 1:1 매핑.
- LLM의 자유 서술은 **사실 보고형(fact-reporting)** 으로 제한 (예: "면접 기대 70~95, 평균 58 → A5 fail").

### 2.5 결정성(Determinism) 우선
- 동일 입력 → 동일 출력. LLM 호출은 `temperature=0`, JSON 강제, schema validation.
- LLM 출력은 항상 schema 검증을 거치며 실패 시 재시도(최대 2회) 후 fallback 룰 적용.

## 3. MVP 범위

### 포함 (3주)
- 착장 단일 이미지 분석 (1인, 정면)
- 의류 속성 추출(JSON) — 상의/하의/외투/신발
- 일정 유형 + 드레스코드 컨텍스트 반영
- **13개 binary 체크 평가** + 그룹별 pass rate + blocker cap
- failed check ↔ fix action 1:1 매핑으로 1~3개 제안 생성

### 제외
- 쇼핑 연동 / SNS / 실시간 영상 / 장기 사용자 메모리
- 얼굴/체형 분석 / 트렌드 분석 / 가격 추천
- 주관적 인상 평가 (위 2.2 항목 전체)

## 4. 대상 사용자
- 20~30대 직장인 / 대학생
- 미팅·면접·발표 등 **공식적 일정 전 객관적 점검**이 필요한 사용자
- 패션 도메인 지식이 적지만 "이 정도면 괜찮은가?"의 정량적 답을 원하는 사용자

## 5. 핵심 가치
> 단순 코디 추천이 아니라, **현재 착장이 현재 상황(일정)에 맞는지를 정량 지표로 판정하고, 점수를 올릴 구체적 행동 1~3개를 제안한다.**

## 6. 성공 지표 (KPI)

| 지표 | 정의 | 측정 방법 | 목표 |
|---|---|---|---|
| Schema Pass Rate | LLM 출력이 schema 검증 통과한 비율 | 서버 로그 | ≥ 98% |
| Score Reproducibility | 동일 입력 5회 호출 시 종합 점수 표준편차 | 자동 테스트 | **= 0** (체크리스트는 100% 결정적) |
| Check Stability | 동일 입력 5회 호출 시 13개 체크 결과 동일률 | 자동 테스트 | 100% |
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
