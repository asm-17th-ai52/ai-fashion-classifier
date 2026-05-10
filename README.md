# AI Fashion Classifier — FitCheck

착장 이미지와 일정 상황을 입력하면 **드레스코드 적합도를 점수로 평가**하고, 구체적인 개선 제안을 제공하는 멀티 에이전트 시스템.

## 팀원

위승빈, 박상돈, 박현규, 이유리, 이태규

## 데모 플로우

```
이미지 업로드 + 상황 선택 (면접 / 오피스 / 결혼식 등)
        ↓
Vision Agent   — 의류 속성 추출 (카테고리, 색상, 격식도)
Context Agent  — 상황별 드레스코드 기준 조회
Recommendation Agent — 13개 항목 체크 + 종합 점수 + 개선 제안
        ↓
결과 화면: 점수 게이지 · 체크리스트 · 제안 카드 · 시뮬레이션
```

## 아키텍처

```
Frontend (React + Vite)
    │  multipart upload / SSE streaming
    ▼
Backend (FastAPI)  —  이미지 전처리 · 세션 관리 · Super-graph 오케스트레이션
    ├── Vision Agent        (LangGraph sub-graph)
    │     Gemini VLM → Verifier 5종 → Critic LLM → 색상 보정
    ├── Context Agent       (stub — Tier-1/2 아키텍처)
    │     상황별 드레스코드 기준 반환
    └── Recommendation Agent (LangGraph sub-graph)
          13개 binary 체크 → 그룹 가중 점수 → 제안 생성 → LLM 내러터
```

## 기술 스택

| 영역 | 기술 |
|---|---|
| AI / Agent | LangGraph 0.2, Gemini (`gemini-3.1-flash-lite`), Google Gen AI SDK |
| Backend | FastAPI, Python 3.13, Pydantic v2, SSE (astream_events) |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Zod |
| 테스트 | pytest, pytest-asyncio |

## 디렉토리 구조

```
ai-fashion-classifier/
├── agents/
│   ├── vision/             # Vision Agent (LangGraph sub-graph)
│   │   ├── nodes/          # step0~3 노드 (validate → VLM → verifiers → critic)
│   │   ├── tools/          # dominant_rgb, clip_image, color_lookup 등
│   │   └── tests/
│   └── recommendation/     # Recommendation Agent (LangGraph sub-graph)
│       ├── checks.py       # 13개 binary 체크
│       ├── scoring.py      # 그룹 가중 점수 + blocker cap
│       ├── suggestions.py  # 개선 제안 생성
│       ├── simulator.py    # 제안 적용 시뮬레이션
│       └── narrator.py     # LLM 자연어화
├── api/
│   ├── app/
│   │   ├── api/            # FastAPI 라우터 (sessions, health)
│   │   ├── orchestration/  # Super-graph, SSE 스트리밍
│   │   ├── agents_stub/    # 실 에이전트 ↔ stub 셀렉터
│   │   ├── schemas/        # 공개 계약 스키마 (07-data-contracts 기반)
│   │   └── services/       # 이미지 전처리, 캐시, rate limit
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/          # UploadPage → AnalyzingPage → ResultPage
│       ├── components/     # ScoreGauge, ChecklistSection, SuggestionCard
│       ├── api/            # HTTP/Mock 어댑터, Zod 스키마
│       └── hooks/          # useSession (SSE 구독)
├── docs/specs/             # 설계 문서 (01~08)
├── tests/                  # Recommendation Agent 단위 테스트
├── data/test_cases/        # 테스트 이미지
└── .env.example
```

## 실행 방법

### 1. 환경 변수 설정

```bash
# repo 루트
cp .env.example .env
# GOOGLE_API_KEY 입력 (Google AI Studio에서 발급)
```

```bash
# frontend/
cp frontend/.env.example frontend/.env
```

### 2. 의존성 설치

```bash
# Backend (Python 3.13)
python -m venv api/.venv
api/.venv/bin/pip install -r api/requirements.txt

# Agents
python -m venv agents/.venv
agents/.venv/bin/pip install -r agents/requirements.txt

# Frontend
cd frontend && npm install
```

### 3. 백엔드 서버 실행

```bash
# repo 루트에서
PYTHONPATH=api:. api/.venv/bin/uvicorn main:app --port 8000 --env-file .env
```

### 4. 프론트엔드 실행

```bash
cd frontend && npm run dev
# → http://localhost:5173
```

### 5. 헬스체크

```bash
curl http://localhost:8000/v1/health
# {"status":"ok", ...}
```

## 테스트 실행

```bash
# Backend
PYTHONPATH=api:. api/.venv/bin/python -m pytest api/tests/ -q

# Vision Agent
agents/.venv/bin/python -m pytest agents/vision/tests/ -q

# Recommendation Agent
PYTHONPATH=. agents/.venv/bin/python -m pytest tests/ -q
```

## 주요 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/v1/sessions` | 이미지 업로드, 전처리, 세션 생성 (202) |
| `GET` | `/v1/sessions/{id}/stream` | SSE 스트리밍 — progress / done / error |
| `GET` | `/v1/sessions/{id}` | 분석 결과 조회 |
| `POST` | `/v1/sessions/{id}/simulate` | 제안 적용 시뮬레이션 |

## 지원 상황 (event_type)

`interview` · `business_meeting` · `presentation` · `wedding_guest` · `office_daily` · `casual_date` · `school_daily` · `outdoor_activity` · `general`
