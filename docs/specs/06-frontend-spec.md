# 06. Frontend — 사양

> 담당자: Frontend 개발자 1명
> 책임: 사용자 입력 수집 / 분석 결과 시각화 / 시뮬레이션 인터랙션

## 1. 책임

1. 이미지 업로드 + 일정 입력 폼
2. 분석 진행 상태 표시 (스트리밍 아님 — 단일 응답 대기)
3. 점수 결과 시각화 (8개 차원 + 종합)
4. 제안 카드 UI + 수용/거절 + 시뮬레이션 점수 갱신
5. 재촬영/입력 수정 흐름

## 2. 비-책임 (명시적 금지)

| 항목 | 이유 |
|---|---|
| 이미지 업로드 전 클라이언트측 의류 분석 | Vision Agent의 책임, 일관성 위반 |
| 클라이언트측 점수 재계산 | 서버 결정성 깨짐 |
| 사용자에 대한 주관적 평가 표시 | 본 프로젝트 명시적 금지 |
| 사용자 사진을 로컬스토리지에 영구 저장 | 프라이버시 |

## 3. 기술 스택

- React 18 + TypeScript
- 상태관리: 단순한 흐름이라 React Context + useReducer로 충분 (Redux 불필요)
- 라우팅: react-router-dom v6 (3개 화면)
- 스타일: Tailwind CSS
- 폼: react-hook-form + zod (서버 schema와 동일 검증)
- API 클라이언트: 자동생성 (OpenAPI → typescript-fetch)
- 빌드: Vite
- 테스트: Vitest + React Testing Library

## 4. 화면 구성

### 4.1 `/` — Upload (홈)
- 좌: 사진 드래그&드롭 / 카메라 촬영
- 우: 일정 입력 폼
  - `event_type` **콤보 입력** (드롭다운 9개 표준값 + "직접 입력" 옵션)
    - 표준값 선택 시: `event_type_is_custom = false`
    - 직접 입력 시: 한국어 free-text → `event_type_is_custom = true` 자동 설정
    - 직접 입력 옆에 안내 배지: "외부 자료를 실시간 검색해 분석합니다 (+5초)"
  - `event_datetime` datetime-local input
  - `city_code` 드롭다운 (KR-SEOUL, KR-BUSAN, ... 고정 리스트)
  - `is_indoor` 체크박스
  - `allow_live_research` 토글 (고급 옵션, 기본 ON)
    - OFF 안내 텍스트: "사용자 정의 일정은 일반 가이드로 분석됩니다"
- 하단: "분석하기" 버튼 (모든 필수 입력 충족 시 활성화)

### 4.2 `/analyzing` — 진행 상태
- 단일 요청 대기 (Tier-1: 6~8초 / Tier-2: 12~15초)
- 진행 텍스트 (시간 기반 fade, 서버에서 phase 알림 없음):
  1. "착장 분석 중…"
  2. "날씨/일정 컨텍스트 조회 중…"
  3. (사용자 정의 event_type일 때 추가) "외부 자료 검색 중…"
  4. "적합도 계산 중…"
- Tier-2 트리거 추정 시 진행 텍스트의 12초 임계 늘림
- 임계 초과 시 "예상보다 오래 걸리고 있어요" 메시지

### 4.3 `/result` — 결과
- 상단: **종합 점수 게이지** (0~100, 색상 단계: 30/60/80)
- 차원 점수: 8개 차원의 막대 차트 (정렬: weak → strong)
- **Dress Code Tier 배지** (`context.dress_code.tier` 기준):
  - `tier1` → 배지 없음 (디폴트)
  - `tier2_live` → 배지 "실시간 외부 자료 기반 추정" + ⓘ 클릭 시 출처 패널 펼침
    - 출처 패널: `evidence_quotes` 의 url + 짧은 인용문 + fetched_at
    - "출처가 부족하면 결과가 부정확할 수 있습니다" 디스클레이머
  - `fallback_general` → 배지 "일반 가이드 적용" + 사용자 안내
- 제안 카드 리스트 (1~3개):
  - 카드 구조: 행동 요약 / 근거 사실(facts) / 예상 점수 증가량
  - "이 제안 적용 시뮬레이션" 토글 → 종합 점수 게이지가 시뮬레이션 값으로 일시 변경
- 재촬영 / 새 분석 버튼

## 5. 데이터 흐름

```
Upload form
   │ submit
   ▼
POST /v1/sessions (multipart)
   │ 200
   ▼
SessionResponse → result store
   ▼
Result page render
   ↑
   │ "시뮬레이션" 클릭
POST /v1/sessions/{id}/simulate { applied_suggestion_ids: [...] }
   ↑ 200
```

## 6. 표시 규칙 (정량성/주관성 금지)

### 6.1 허용
- 숫자 점수 그대로 표시 ("드레스코드 적합도 60/100")
- 차원 이름 한글화: 고정 매핑 테이블 사용
- 근거 사실 그대로 출력 ("외기온 6.5°C, 현재 보온지수 5")
- 행동 권장 ("신발을 로퍼로 교체")

### 6.2 금지 표시
- "당신은 이 옷이 잘 어울려요"
- "매력적이에요" 등 평가형 문구
- 점수 변동을 별/하트 아이콘으로 의미 부여
- 사용자 외형/체형 언급
- 서버에서 안 준 추가 추론

### 6.3 차원 한글 매핑
| 서버 키 | 표시 라벨 |
|---|---|
| formality_match | 포멀니스 일치도 |
| formality_consistency | 포멀니스 일관성 |
| thermal_fit | 온도 적합도 |
| precipitation_readiness | 강수 대비도 |
| color_contrast | 색 대비 |
| tone_balance | 톤 균형 |
| dresscode_alignment | 드레스코드 정합도 |
| category_completeness | 의류 구성 완성도 |

## 7. 컴포넌트 구조

```
src/
├── pages/
│   ├── UploadPage.tsx
│   ├── AnalyzingPage.tsx
│   └── ResultPage.tsx
├── components/
│   ├── ImageDropzone.tsx
│   ├── EventForm.tsx
│   ├── ScoreGauge.tsx
│   ├── DimensionBars.tsx
│   ├── SuggestionCard.tsx
│   └── ErrorBoundary.tsx
├── api/
│   ├── client.ts            # 자동생성 OpenAPI client wrapper
│   └── schemas.ts           # zod schemas (07-data-contracts와 동기)
├── hooks/
│   ├── useSession.ts
│   └── useSimulation.ts
├── store/
│   └── sessionContext.tsx
├── lib/
│   ├── format.ts            # 점수 표시 유틸
│   └── i18n.ts              # 차원 라벨 매핑
└── App.tsx
```

## 8. 에러 처리 (사용자 메시지)

| 서버 에러 | UI 처리 |
|---|---|
| 400 (사람 미검출) | 모달: "사람이 정면으로 보이는 사진을 사용해 주세요" + 재업로드 버튼 |
| 413 | "10MB 이하 이미지만 사용 가능합니다" |
| 422 (입력 검증) | 폼 필드별 메시지 (react-hook-form) |
| 429 | "잠시 후 다시 시도해 주세요" toast |
| 502 | "AI 분석에 실패했어요. 다시 시도해 주세요" + 재시도 버튼 |
| 503 (날씨만 다운) | 정상 결과 표시 + 상단 배너: "날씨 데이터를 가져오지 못해 일부 점수에서 제외되었어요" |
| 네트워크 끊김 | offline 배너 |

## 9. 접근성 (a11y)

- 이미지 업로드: 키보드 접근 가능 (`<input type=file>`)
- 점수 차트: aria-label로 수치 제공 (스크린리더)
- 색상으로만 정보 전달 금지: 점수 단계 색상 + 텍스트 레이블 동시 표기
- 모든 인터랙티브 요소 focus visible

## 10. 성능 목표

| 지표 | 목표 |
|---|---|
| 첫 페이지 로드 (FCP) | ≤ 1.5s (3G fast) |
| 이미지 업로드 시작까지 | ≤ 100ms (UI 반응) |
| 결과 렌더링 | ≤ 100ms (서버 응답 후) |
| 번들 크기 (gzip) | ≤ 250KB |

## 11. 테스트 전략

### 11.1 단위
- 차원 라벨 매핑
- 점수 포맷 함수 (반올림, 단위)
- Zod schema 검증

### 11.2 컴포넌트
- ScoreGauge: 점수별 색상 단계
- SuggestionCard: 시뮬레이션 토글 동작
- EventForm: 필드 검증

### 11.3 E2E (Playwright)
- 골든 이미지 업로드 → 결과 화면 표시 (모킹된 Backend)
- 시뮬레이션 토글 → 점수 변경

## 12. 마일스톤

| 주차 | 산출물 |
|---|---|
| 1주차 | 라우팅 + Upload 화면 + API 클라이언트 자동생성 |
| 2주차 | Result 화면 + 점수 시각화 + 에러 처리 |
| 3주차 | 시뮬레이션 인터랙션 + 접근성 + 발표용 폴리싱 |

## 13. 다른 역할과의 인터페이스

- **Backend**: OpenAPI schema(`/openapi.json`)를 single source of truth로 받음. CI에서 schema diff 시 자동 PR 생성.
- **AI Agent 담당자들**: 차원 추가/제거 시 Frontend 라벨 매핑 업데이트 필요 → 변경 시 PR에 라벨 매핑 변경 포함 룰.
