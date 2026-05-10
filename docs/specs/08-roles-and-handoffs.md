# 08. 역할 분담 및 협업 인터페이스

> 5인 팀 (AI Agent 개발 3명, Backend 1명, Frontend 1명) 의 책임 경계, 인계 지점, 일정.

## 1. 역할 매트릭스

| 역할 | 인원 | 주 책임 | 단일 책임 모듈 | 명시적 비-책임 |
|---|---|---|---|---|
| **AI/Vision Agent** | 1 | 이미지 → 의류 속성 JSON 추출 | `backend/app/agents/vision/` | 점수 계산, 컨텍스트 조회 |
| **AI/Context Agent** | 1 | 일정 → 드레스코드 | `backend/app/agents/context/` | LLM 사용, 의류 평가 |
| **AI/Recommendation Agent** | 1 | 점수 산출 + 제안 생성 | `backend/app/agents/recommendation/`, `backend/app/scoring/` | 의류 추출, 외부 API 직접 호출 |
| **Backend** | 1 | API Gateway / 오케스트레이션 / 전처리 / 캐싱 | `backend/app/api/`, `backend/app/services/preprocess.py` | Agent 내부 로직 |
| **Frontend** | 1 | UI 전체 | `frontend/` | 점수 계산, Agent 직접 호출 |

## 2. 인계(Handoff) 지점

```
[Frontend]
   │ multipart upload (07-data-contracts §5.1)
   ▼
[Backend: /v1/sessions]
   │ image_bytes (전처리됨), session_id
   ▼
[Vision Agent]  ──────────►  VisionResponse (07 §2)
   │                          │
   │ ContextRequest (03 §3)   │
   ▼                          │
[Context Agent] ─────────►  ContextResponse (07 §3)
                              │
                              ▼
                        [Recommendation Agent]
                              │
                              ▼
                        RecommendationResponse (07 §4)
                              │
                              ▼
                        [Backend: SessionResponse]
                              │
                              ▼
                        [Frontend: 결과 화면]
```

각 화살표는 **schema가 명시된 경계**다. schema 변경은 양쪽 담당자의 동의가 필요하다.

## 3. 핵심 협업 규칙

### 3.1 Schema-First
- 모든 인터페이스는 `07-data-contracts.md` 의 schema가 먼저 머지된 후 구현 시작.
- 구현 전 schema PR을 5명 모두 approve.
- Backend는 Pydantic, Frontend는 Zod로 schema에서 **자동 생성** (수기 동기화 금지).

### 3.2 Mock-First 개발
1주차에 모든 담당자는 자신의 입력/출력에 대한 **mock 응답 fixture**를 먼저 작성한다. 이로써 5명이 동시 병렬로 작업 가능.

| 담당자 | 1주차 mock 위치 |
|---|---|
| Vision | `backend/tests/fixtures/vision/expected.json` |
| Context | `backend/tests/fixtures/context/expected.json` |
| Recommendation | `backend/tests/fixtures/recommendation/expected.json` |
| Backend | mock agents로 Frontend에 응답 |
| Frontend | MSW(Mock Service Worker) 로 Backend mock |

### 3.3 코드 소유권 (CODEOWNERS)

> **[협의 필요]** 아래 경로는 `backend/` 루트 기준으로 작성되어 있으나, Backend 스캐폴드(PR #3)에서 `api/` 루트로 구현되었습니다. 전원 검토 후 실제 디렉토리 구조에 맞게 업데이트해야 합니다.

```
backend/app/agents/vision/         @vision-owner
backend/app/agents/context/        @context-owner
backend/app/agents/recommendation/ @rec-owner
backend/app/scoring/               @rec-owner
backend/app/api/                   @backend-owner
backend/app/services/              @backend-owner
frontend/                          @frontend-owner
docs/specs/07-data-contracts.md    @vision-owner @context-owner @rec-owner @backend-owner @frontend-owner
```

`07-data-contracts.md` 변경은 5인 전원 승인 필요.

### 3.4 PR 사이즈
- 1 PR 당 ≤ 400 LOC
- 영역 횡단 PR 금지 (예: Vision Agent 코드 + Frontend 라벨 동시 변경 금지). 단, 체크 항목 추가는 예외 (3.5 참조).

### 3.5 체크 항목 추가/제거/이동 (Cross-cutting)
체크리스트 변경 시 단일 PR에 다음이 모두 포함되어야 한다:
- `04-agent-recommendation-spec.md` 의 체크 표 업데이트
- `backend/app/scoring/checks/` 에 새 Check 클래스 추가/제거
- Check Registry 업데이트
- blocker 여부 결정 (해당 시)
- `07-data-contracts.md` 의 `CheckGroup` enum (그룹 추가 시에만)
- `RecommendationResponse` schema 영향 검토 (체크 단순 추가는 schema 변경 없음)
- 새 체크의 `label` (한글) — 서버에서 직접 제공
- 단위 테스트 ≥ 4 케이스 (pass / fail / N/A / 경계값)
- 골든 시나리오 5개 회귀 검증

리뷰어: rec-owner + backend-owner. (Frontend는 `label`을 그대로 표시하므로 코드 변경 보통 불필요.)

## 4. 정량성/주관성 가드레일 (전 역할 공통)

본 프로젝트의 **명시적 금지 영역**은 다음과 같이 다층 방어한다.

| 레이어 | 방어 수단 |
|---|---|
| Vision Agent 프롬프트 | "Do not infer wearer's identity, body shape, age, gender, aesthetic judgment" |
| Recommendation LLM 프롬프트 | "Use only provided facts and numbers. Forbidden: 매력, 호감, 인상, 성격, 외모 평가" |
| Recommendation 후처리 | 금지 단어 리스트 정규식 매칭 → 위반 시 재시도 |
| Backend 로깅 | LLM 출력에 금지 단어 검출 시 `policy_violation` 메트릭 +1 |
| Frontend 표시 | 서버에서 받은 텍스트만 표시, 자체 추론 금지 |
| 테스트 | 금지 단어 회귀 테스트 (CI gating) |

### 4.1 금지 단어 리스트 (한국어)
```
매력, 매력적, 호감, 호감도, 잘생, 예쁘, 멋지,
인상, 성격, 신뢰감, 어울리는 사람,
체형, 몸매, 키, 마른, 통통, 슬림한 (체형 의미일 때),
나이, 연령, 성별, 직업이 ~처럼 보이는,
세련, 촌스러, 평범
```

### 4.2 허용 표현 (참고)
- 점수 인용 ("드레스코드 적합도 60점")
- 사실 인용 ("외기온 6.5°C, 보온지수 5")
- 행동 권장 ("신발을 로퍼로 교체")
- 범위 비교 ("기대 범위 70~95 대비 현재 65")

## 5. 마일스톤 통합 보기

| 주차 | Vision | Context | Recommendation | Backend | Frontend |
|---|---|---|---|---|---|
| **1주** | LangGraph sub-graph 골격 + 결정적 도구 노드(validate/pose/blur/dominant_rgb) + 1차 VLM 노드 + 골든 5장 | LangGraph sub-graph 골격 + Tier-1 RAG 노드 | LangGraph sub-graph 골격 + Group A,B 8개 체크 노드 + 점수 산출 노드 | LangGraph 셋업 + super-graph 골격(stub sub-graph) + FastAPI 스캐폴드 + 전처리 노드 | 라우팅 + Upload UI |
| **2주** | Verifier 5종 노드 + Critic LLM 노드 + 색상 overwrite + 분기 함수 + 골든 20장 | Tier-2 ReAct 노드들(plan_query / web_search / fetch_pages / extract_facts / consensus) + 도메인 화이트리스트 + 분기 함수 | Group C,D 5개 체크 + blocker cap + simulator 노드 + candidates 노드 | super-graph에 실제 sub-graph 연결 + 캐시 + 병렬 fan-out/fan-in 검증 | Result UI + 체크리스트 시각화 |
| **3주** | 얼굴 블러 통합 + 회귀 테스트 + LangSmith trace 확인 | 결정성 테스트 + 승격 큐 노드 + 통합 + LangSmith trace 확인 | narrate 노드 + safety_filter 분기 + 통합 테스트 | simulate endpoint + 관측성 + E2E + LangGraph checkpoint 활성화 | 시뮬 인터랙션 + Tier-2 출처 패널 + 발표 폴리싱 |

각 주 종료 시점 **인테그레이션 데이**: 금요일 오후, 5인 모두 코드 머지 후 e2e 시나리오 1회 통과.

### 5.1 LangGraph 공통 규칙 (전 Agent + Backend)
- 각 Agent는 자신의 sub-graph를 `compile()` 결과로 export. 모듈 경로: `app.agents.{name}.{name}_subgraph`
- State 모델은 Pydantic v2. 변경 시 sub-graph 담당자 + Backend 담당자 동시 리뷰.
- 노드는 **단일 책임** (한 가지 도구 OR 한 가지 LLM 호출). 노드 함수 시그니처: `(state) -> dict[str, Any]` (부분 업데이트 반환).
- 분기 함수는 결정적. State의 결정적 필드만 참조.
- 노드 이름은 snake_case 동사구 (예: `vlm_extract_all`, `tier1_retrieve`).
- 모든 sub-graph는 단위 테스트로 4개 시나리오 이상 통과해야 한다 (정상 / 분기 일부 / 분기 전부 / 실패).
- Backend의 super-graph는 Agent sub-graph의 **State schema 변경에 자동으로 영향받지 않는다** — sub-graph가 출력하는 최종 필드(VisionResponse / ContextResponse / RecommendationResponse)만 보면 된다.
- LangSmith는 환경변수로 활성화 (`LANGCHAIN_TRACING_V2=true`). 운영은 선택, 디버깅 시 권장.

## 6. 의사결정 로그 (DACI)

| 결정 항목 | Driver | Approver | Contributors | Informed |
|---|---|---|---|---|
| 새 enum 값 추가 (event_type 등) | 발의자 | 5인 전원 | - | - |
| 점수 차원 추가 | rec-owner | rec + backend + frontend | vision/context | - |
| LLM 모델 교체 | vision-owner / rec-owner | 해당 owner | backend (비용/속도) | 전원 |
| UI 큰 변경 | frontend-owner | frontend + 발표 담당 | - | 전원 |

## 7. 통합 테스트 시나리오 (E2E 5개)

3주차 발표 전 모두 통과 필수.

| # | event_type | 의도 | 기대 결과 |
|---|---|---|---|
| 1 | interview | 면접 적정 착장 | overall ≥ 80, suggestion ≤ 1 |
| 2 | interview | 면접에 캐주얼 | overall ≤ 60, swap shoes 제안 |
| 3 | office_daily | 포멀니스 기대치 충족 | overall ≥ 70, suggestion ≤ 2 |
| 4 | wedding_guest | 너무 캐주얼 | overall ≤ 50 (blocker cap), swap 제안 |
| 5 | presentation | 드레스코드 완전 불일치 | overall ≤ 40, 복수 제안 |

각 시나리오는 골든 이미지 + 기대 응답 fixture로 저장 (`backend/tests/fixtures/e2e/`).

## 8. 발표 자료 책임

| 항목 | 담당 |
|---|---|
| 슬라이드 (배경/문제/접근법) | 1인 (위승빈 — 임의, 팀 협의) |
| 데모 시연 | Frontend 담당 |
| 아키텍처/Agent 흐름 설명 | Backend 담당 |
| 정량 평가 결과 | Recommendation 담당 |
| Vision/Context 디테일 | 각 담당자 백업 슬라이드 |

## 9. 리스크 및 컨틴전시

| 리스크 | 컨틴전시 |
|---|---|
| VLM이 어휘 위반 빈발 | Vision Agent: 카테고리만 LLM, 색상은 OpenCV로 따로 추출 |
| 점수 분포가 이상 (모두 80+) | rec-owner: 가중치 재조정, 골든 셋 재라벨 |
| LLM 비용 초과 | Backend: rate limit 강화, 데모 시 캐시된 시나리오 우선 |
| 발표 시연 실패 | 사전 녹화한 데모 영상 fallback 준비 |

## 10. 정의된 "완료(Done)" 기준

다음을 모두 만족해야 프로젝트 완료로 본다.

- [ ] 13개 binary 체크 모두 단위 테스트 통과 (pass/fail/N/A 케이스)
- [ ] 그룹별 pass rate + blocker cap 산출 정합성 테스트 통과
- [ ] 시뮬레이션 정합성 ≥ 99% (적용 후 expected_delta ±1)
- [ ] 5개 E2E 시나리오 통과
- [ ] Schema Pass Rate ≥ 98% (자동 측정)
- [ ] 동일 입력 5회 호출 시 종합 점수 + 13개 체크 결과 100% 동일
- [ ] 금지 단어 회귀 테스트 통과 (위반 0건)
- [ ] Latency P95 ≤ 8s
- [ ] 발표 데모 1회 무사고 시연
