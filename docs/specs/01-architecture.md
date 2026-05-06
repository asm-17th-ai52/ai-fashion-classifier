# 01. 시스템 아키텍처

## 1. 컴포넌트 구성도

```
┌─────────────────┐
│  Frontend (React)│  업로드 UI / 점수 카드 / 제안 UI
└────────┬────────┘
         │ HTTPS / multipart
         ▼
┌─────────────────────────────────────────────┐
│  Backend API Gateway (FastAPI)              │
│   - 이미지 검증 / 정규화                       │
│   - 세션ID 발급 / 요청 라우팅                  │
│   - Agent 오케스트레이션 (직렬 + 부분 병렬)      │
└──┬─────────────┬──────────────┬─────────────┘
   │             │              │
   ▼             ▼              ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────┐
│ Vision Agent       │  │ Context Agent      │  │ Recommendation │
│ (Verify-and-Refine)│  │ (2-Tier)           │  │ Agent          │
│                    │  │                    │  │                │
│ - VLM Extractor    │  │ Tier-1: Static RAG │  │ - 결정적 점수    │
│ - Critic LLM       │  │   (LLM 미사용)       │  │   함수 (8차원)   │
│ - Tools (det.):    │  │                    │  │ - Action 생성    │
│   pose_keypoints   │  │ Tier-2: Live ReAct │  │   + 시뮬레이션    │
│   dominant_rgb     │  │   - web_search     │  │ - LLM Narrator  │
│   face_blur        │  │   - fetch_page     │  │   (자연어화만)    │
│   verify_schema    │  │   - youtube_caption│  │                │
│   verify_vocab     │  │   - extract_facts  │  │                │
│   verify_color     │  │   - 도메인 화이트리스트│  │                │
└─────────┬──────────┘  └─────────┬──────────┘  └────────┬───────┘
          │                       │                      │
          └───────────────────────┴──────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │ External Resources       │
                    │ - Weather API            │
                    │ - Static FAISS index     │
                    │ - Web Search API         │
                    │ - URL fetcher            │
                    │ - Promotion Queue (JSONL)│
                    └─────────────────────────┘
```

## 2. 요청 흐름 (Sequence)

```
User → Frontend → Backend
  1. POST /v1/sessions (이미지 업로드, 일정 메타)
     → Backend: 이미지 검증, 세션 생성
  2. Backend → Vision Agent: analyze_outfit(image)
     → 의류 속성 JSON 반환
  3. Backend → Context Agent (병렬):
     - resolve_weather(location, datetime)
     - resolve_dresscode(event_type)
        ├─ Tier-1: Static RAG 검색 (LLM 미사용)
        └─ Tier-2: Live Research Agent (ReAct + 웹검색)
                   — Tier-1 score < 0.6 또는 사용자 정의 event_type일 때만
     → context JSON 반환
  4. Backend → Recommendation Agent: score_and_suggest(outfit, context)
     → scores + suggestions 반환
  5. Backend → Frontend: 종합 응답
```

LLM 호출 수: **최소 2회 (Vision 1차 + Recommendation), 평균 ~3회, 최대 5회** (Vision Verify-and-Refine 재추출 + Critic + Context Tier-2 트리거 시).

## 3. Agent 분담 원칙

| Agent | Agentic 패턴 | LLM 사용 | 결정성 |
|---|---|---|---|
| Vision Agent | **Verify-and-Refine** (Tool use + Self-critique + Adaptive routing). 결정적 도구(OpenCV, MediaPipe, schema/vocab/color verifier) + VLM Extractor + Critic LLM. 색상은 LLM이 추정하지 않고 OpenCV로 결정적 측정. | VLM 1~2회 + Critic 0~1회 (`temperature=0`) | 색상 100% 결정적, 카테고리는 schema/vocab 강제 |
| Context Agent | **2-Tier**: Tier-1 정적 RAG (LLM 미사용) / Tier-2 ReAct (LLM + 도구화이트리스트, 트리거 시에만) | Tier-1: 0회 / Tier-2: 1~5회 | Tier-1 100% / Tier-2 부분 결정성 (다중 소스 합의 + schema 강제) |
| Recommendation Agent | 결정적 점수 함수 + LLM Narrator + 시뮬레이션 검증 | LLM 1회 (자연어화만) | 점수 100% 결정적 |

**핵심:** 점수는 **순수 함수(코드)**로 계산하고, LLM은 **계산된 점수를 자연어로 설명**하는 데에만 사용한다. 이로써 점수 재현성을 100% 보장한다.

## 4. 디렉토리 레이아웃 (제안)

```
ai-swm-52/
├── docs/specs/                # 본 spec 디렉토리
├── frontend/                  # React app (Frontend 담당)
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI 라우터 (Backend 담당)
│   │   ├── agents/
│   │   │   ├── vision/        # Vision Agent (담당자 1)
│   │   │   ├── context/       # Context Agent (담당자 2)
│   │   │   └── recommendation/# Recommendation Agent (담당자 3)
│   │   ├── schemas/           # Pydantic 모델 (07-data-contracts 기준)
│   │   ├── scoring/           # 결정적 점수 계산 모듈
│   │   └── services/
│   │       ├── weather.py
│   │       ├── dresscode_rag_static.py     # Tier-1
│   │       ├── live_research_agent.py      # Tier-2 ReAct 루프
│   │       ├── tools/
│   │       │   ├── web_search.py
│   │       │   ├── fetch_page.py
│   │       │   ├── youtube_transcript.py
│   │       │   └── extract_facts.py
│   │       └── promotion_queue.py          # Tier-2 → Tier-1 승격 큐
│   ├── data/
│   │   └── dresscode/
│   │       ├── static/                     # Tier-1 9개 마크다운
│   │       └── promotion_queue.jsonl       # 승격 대기열
│   ├── tests/
│   │   ├── fixtures/          # 골든 입력 이미지 + 기대 JSON
│   │   ├── test_vision.py
│   │   ├── test_scoring.py
│   │   └── test_e2e.py
│   └── pyproject.toml
└── README.md
```

## 5. 데이터 흐름 보장

### 5.1 멱등성
- `session_id` 단위로 모든 중간 산출물(outfit JSON, context JSON)을 캐시한다.
- 동일 `session_id` 재요청 시 LLM 재호출 없이 캐시 결과 반환.

### 5.2 실패 처리
| 단계 | 실패 유형 | 대응 |
|---|---|---|
| 이미지 업로드 | 해상도 < 480p, 사람 미검출 | 400 + 재촬영 요청 메시지 |
| Vision Agent | schema 검증 실패 | 재시도 2회 → 실패 시 502 |
| Weather API | 4xx/5xx | "기상 데이터 없음" 플래그 + 날씨 차원 점수 제외 |
| Dress Code Tier-1 | 매칭 임계 미만 | Tier-2 자동 트리거 (조건 충족 시) |
| Dress Code Tier-2 | 도메인 화이트리스트 위반 / 단일 소스 / extraction confidence < 0.5 | "general" 카테고리 fallback + warning |
| Dress Code Tier-2 | latency > 12s 또는 글로벌 일일 한도 초과 | 부분 결과 또는 fallback + `tier2_budget_exceeded` warning |
| Recommendation | LLM 텍스트 실패 | 점수만 반환 + 제안 텍스트는 룰 기반 템플릿 |

### 5.3 관측성 (Observability)
- 모든 Agent 호출은 다음을 로깅한다.
  - `session_id`, `agent_name`, `latency_ms`, `tokens`, `schema_pass`
- LLM 호출은 raw response를 7일간 보관 (디버깅 + 회귀 테스트 골든 셋 후보).

## 6. 보안 / 프라이버시

- 업로드 이미지: 처리 후 **24시간 내 삭제** (감사 로그만 보관).
- 얼굴 영역 감지 시 자동 블러 처리 후 VLM에 전달 (얼굴 분석 차단).
- 위치 정보: 좌표가 아닌 도시 단위(`city_code`)로만 수신.
- LLM 프롬프트에 PII 미포함.

## 7. 비-목표 (시스템 차원)

- 다중 사용자 인증 / 권한 (MVP는 단일 익명 세션)
- 학습 / 파인튜닝 (모든 추론은 zero-shot + RAG)
- 실시간 스트리밍 (단일 요청-응답)
