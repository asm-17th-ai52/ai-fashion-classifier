# 05. Backend — 사양

> 담당자: Backend 개발자 1명
> 책임: API Gateway / 이미지 전처리 / Agent 오케스트레이션 / 캐싱 / 관측성

## 1. 책임

1. REST API 제공 (Frontend ↔ Backend 경계)
2. 이미지 업로드 검증, 정규화, 얼굴 자동 블러
3. 3개 Agent의 오케스트레이션 (병렬/직렬 제어)
4. 세션 단위 캐싱 (멱등성)
5. 외부 의존성(OpenAI API) 키 관리 + rate limit
6. 관측성: 로깅, 메트릭, 트레이싱

## 2. 비-책임

| 항목 | 책임자 |
|---|---|
| 의류 속성 추출 | Vision Agent 담당자 |
| 점수 계산 | Recommendation Agent 담당자 |
| RAG 조회 | Context Agent 담당자 |
| UI 렌더링 | Frontend 담당자 |

Backend는 위 모듈을 **호출**할 뿐, 내부 로직은 담당자별 모듈에 위임.

## 3. 기술 스택

- 언어: Python 3.11+
- 프레임워크: FastAPI (기획서: `Spring Boot / FastAPI` → 본 spec은 FastAPI 채택, 단일 언어로 Agent 모듈과 통합)
- **오케스트레이션: LangGraph 0.2+** (각 Agent는 sub-graph, Backend는 super-graph)
- LLM 클라이언트: LangChain core (LangGraph 내부 사용) + 직접 OpenAI SDK 혼용 가능
- 비동기: `asyncio`, `httpx`
- 검증: Pydantic v2 (LangGraph State와 동일 모델 공유)
- 이미지 처리: Pillow + OpenCV (얼굴 블러용 MediaPipe)
- 관측성: LangSmith trace (선택, 환경변수로 활성화)
- 테스트: pytest, pytest-asyncio
- 로깅: structlog (JSON 로깅)

## 4. API 엔드포인트

### 4.1 `POST /v1/sessions`
세션 생성 + 이미지 업로드 + 백그라운드 분석 트리거. **즉시 202를 반환**하고 실제 진행 및 결과는 SSE 스트림(`4.2`)으로 전달한다.

**Request (multipart/form-data):**
```
image: file (jpeg/png, 1B ≤ size ≤ 10MB)
event_type: string (enum, see Context spec)
event_datetime: string (ISO 8601)
city_code: string (KR-SEOUL 등)
is_indoor: boolean (기본 false)
allow_live_research: boolean (기본 true)
```

**Response 202:**
```json
{ "session_id": "sess_01HXXXXXX" }
```

**Error responses (입력 단계에서만 발생):**
| HTTP 코드 | 의미 | 사용자 메시지 |
|---|---|---|
| 400 | 이미지 검증 실패 / 사람 미검출 | "사람이 정면으로 보이는 사진으로 다시 업로드해 주세요" |
| 413 | 파일 크기 초과 | "10MB 이하 이미지를 사용해 주세요" |
| 422 | 입력 schema 위반 | (필드별 메시지) |
| 429 | rate limit | "잠시 후 다시 시도해 주세요" |

분석 중 에러는 SSE `error` 이벤트(`4.2`)로 전달한다.

### 4.2 `GET /v1/sessions/{session_id}/stream` — SSE
LangGraph `astream_events()`를 통해 분석 진행 상황을 실시간으로 스트리밍한다.

**Response:** `Content-Type: text/event-stream`

모든 이벤트는 아래 두 필드를 공통으로 포함한다.

| 공통 필드 | 타입 | 설명 |
|---|---|---|
| `type` | string | 이벤트 종류 (`progress` \| `done` \| `error`) |
| `pct` | integer 0–100 | 전체 진행률. 프론트엔드 프로그레스바 구동에 직접 사용 |

#### `progress` 이벤트
분석 파이프라인의 각 단계마다 방출된다. `message`는 **한국어 자연어**로 프론트엔드가 별도 변환 없이 그대로 화면에 표시할 수 있다.

```
data: {"type": "progress", "pct": 5,  "message": "이미지를 전처리하고 있어요"}
data: {"type": "progress", "pct": 12, "message": "사진에서 사람을 감지했어요"}
data: {"type": "progress", "pct": 20, "message": "상의: 드레스 셔츠 · 솔리드 패턴"}
data: {"type": "progress", "pct": 28, "message": "신발: 로퍼 · 브라운"}
data: {"type": "progress", "pct": 35, "message": "착장 분석을 완료했어요"}
data: {"type": "progress", "pct": 45, "message": "드레스코드 기준을 조회하고 있어요"}
data: {"type": "progress", "pct": 58, "message": "오늘 날씨 정보를 가져왔어요 · 8.5°C"}
data: {"type": "progress", "pct": 65, "message": "상황 컨텍스트 준비 완료"}
data: {"type": "progress", "pct": 72, "message": "17개 항목을 체크하고 있어요"}
data: {"type": "progress", "pct": 85, "message": "드레스코드 · 색상 · 환경 적합성 평가 완료"}
data: {"type": "progress", "pct": 92, "message": "개선 제안을 생성하고 있어요"}
data: {"type": "progress", "pct": 98, "message": "분석 결과를 정리하고 있어요"}
```

**`message` 작성 규칙:**
- 완전한 한국어 문장 또는 구. 프론트엔드는 이 값을 그대로 렌더링한다.
- 사용자에게 불안감을 주는 기술적 오류 메시지 금지 (예: `NullPointerException`)
- 의류 속성 등 동적 값은 `·`(가운뎃점)으로 구분해 인라인 포함 가능 (예: `"상의: 드레스 셔츠 · 솔리드"`)

#### `done` 이벤트
파이프라인 전체 완료 시 1회 방출. `result` 에 `SessionResponse` 전체를 담아 전달하므로 프론트엔드는 별도로 `GET /sessions/{id}`를 호출할 필요가 없다.

```
data: {"type": "done", "pct": 100, "message": "분석이 완료됐어요", "result": { ...SessionResponse... }}
```

#### `error` 이벤트
분석 중 복구 불가능한 오류 발생 시 방출하고 스트림을 닫는다. `message`는 프론트엔드가 사용자에게 직접 표시한다.

```
data: {"type": "error", "pct": 0, "message": "AI 분석에 실패했어요. 다시 시도해 주세요", "code": "agent_failed"}
```

**`code` 값:**
| `code` | 의미 |
|---|---|
| `agent_failed` | Agent 내부 오류 |
| `person_not_detected` | 전처리 단계 사람 미검출 |
| `rate_limited` | 외부 API 한도 초과 |

**구현 (FastAPI):**
```python
@router.get("/v1/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    state = await cache.get(f"pending:{session_id}")

    async def generate():
        try:
            async for event in SUPER_GRAPH.astream_events(state, version="v2"):
                sse = map_langgraph_event(event)   # 노드 이벤트 → SSE dict 변환
                if sse:
                    yield f"data: {json.dumps(sse, ensure_ascii=False)}\n\n"
        except AppError as e:
            yield f"data: {json.dumps({'type': 'error', 'pct': 0, 'message': e.user_message, 'code': e.code}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

`map_langgraph_event()`는 LangGraph `on_chain_start` / `on_chain_end` 이벤트를 위 SSE 포맷으로 변환하는 내부 헬퍼. Agent 노드는 SSE를 알지 못하며, `message`와 `pct`는 Backend가 `event["name"]`과 `event["data"]["output"]`을 읽어 직접 포맷팅한다. 각 Agent별 이벤트 구조와 꺼낼 수 있는 데이터는 `02/03/04-agent-*-spec.md §astream_events() 참조 정보`에 정의되어 있다.

### 4.3 `GET /v1/sessions/{session_id}`
- 완료된 분석 결과 재조회 (멱등). SSE 연결이 끊겼을 때 결과를 다시 받아올 때 사용.
- 분석이 아직 진행 중이면 `202 { "status": "pending" }` 반환.
- TTL: 24시간

### 4.4 `POST /v1/sessions/{session_id}/simulate`
- 사용자가 제안을 수용했을 때의 시뮬레이션 점수 재계산
- 입력: `applied_suggestion_ids: [str]`
- LLM 미사용 (결정적, < 100ms)

### 4.4 `GET /v1/health`
- 외부 의존성 헬스체크 (`openai`, `vector_db`)

## 5. 오케스트레이션 (LangGraph Super-graph)

본 Backend는 모든 Agent를 **하나의 LangGraph super-graph로 묶어** 실행한다. 각 Agent의 sub-graph는 담당자가 자체 spec에 따라 구현하여 export하고, Backend는 이를 노드로 받아 흐름만 정의한다.

### 5.1 SessionState

```python
from typing import Optional
from pydantic import BaseModel

class SessionState(BaseModel):
    # 입력
    session_id: str
    image_bytes: bytes
    request: SessionCreateRequest

    # 전처리 결과
    preprocessed_image: Optional[bytes] = None
    preprocess_meta: Optional[dict] = None

    # Agent sub-graph 산출물 (각 sub-graph가 채움)
    outfit: Optional[VisionResponse] = None
    context: Optional[ContextResponse] = None
    recommendation: Optional[RecommendationResponse] = None

    # 메타
    agent_latencies_ms: dict = {}
    cache_hits: list[str] = []
    tier2_triggered: bool = False
    errors: list[dict] = []
```

### 5.2 Super-graph 정의

```python
from langgraph.graph import StateGraph, END
from app.agents.vision import vision_subgraph        # compiled sub-graph
from app.agents.context import context_subgraph
from app.agents.recommendation import recommendation_subgraph

def build_super_graph():
    g = StateGraph(SessionState)

    g.add_node("preprocess", preprocess_node)            # 결정적
    g.add_node("vision", vision_subgraph)                # Agent sub-graph
    g.add_node("context", context_subgraph)              # Agent sub-graph
    g.add_node("recommendation", recommendation_subgraph)# Agent sub-graph
    g.add_node("pack_response", pack_response_node)      # 결정적

    g.set_entry_point("preprocess")

    # 병렬 fan-out: preprocess 후 vision과 context 동시 실행
    g.add_edge("preprocess", "vision")
    g.add_edge("preprocess", "context")

    # join: vision과 context 모두 끝나야 recommendation 진입
    g.add_edge(["vision", "context"], "recommendation")

    g.add_edge("recommendation", "pack_response")
    g.add_edge("pack_response", END)

    return g.compile()

SUPER_GRAPH = build_super_graph()
```

### 5.3 FastAPI 라우터에서의 호출

`POST /v1/sessions`는 상태를 캐시에 적재하고 즉시 202를 반환한다. 실제 그래프 실행은 SSE 스트림 연결 시점에 시작된다.

```python
@router.post("/v1/sessions", status_code=202)
async def create_session(req: SessionCreateRequest):
    session_id = mint_session_id()
    initial_state = SessionState(
        session_id=session_id,
        image_bytes=await req.image.read(),
        request=req,
    )
    # 전처리 검증만 선행 실행 (사람 미검출 등 즉시 400 가능)
    initial_state = await preprocess_node(initial_state)
    # 나머지 분석은 SSE 스트림에서 astream_events()로 실행
    await cache.put(f"pending:{session_id}", initial_state, ttl=300)
    return {"session_id": session_id}
```

### 5.4 Backend가 직접 책임지는 노드

| 노드 | 종류 | 책임 |
|---|---|---|
| `preprocess` | 결정적 | EXIF 정규화, 사람 검출, 얼굴 블러, 리사이즈, JPEG 재인코딩 |
| `pack_response` | 결정적 | SessionState → SessionResponse 변환, agent_latencies 합산, cache 키 산출 |

Agent sub-graph(`vision_subgraph`, `context_subgraph`, `recommendation_subgraph`)의 내부 노드는 **각 Agent 담당자가 자체 spec(02/03/04)에 따라 정의**한다. Backend는 sub-graph의 입출력 schema만 알면 된다.

### 5.5 에러 전파

- 각 sub-graph는 실패 시 `state.errors` 에 항목 추가하고 다음 노드로 진행하거나, fatal 에러는 예외로 전파.
- super-graph 차원에서 fatal 예외는 FastAPI 에러 핸들러가 HTTP 코드로 변환 (`07-data-contracts.md §5.4`).
- 부분 실패 (예: Tier-2 timeout)는 errors에 기록하되 그래프는 계속 진행.

### 5.6 LangSmith 통합 (선택)

환경변수로 제어:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=ai-swm-52
```
활성화 시 모든 노드 입출력, latency, token이 자동 기록되며, `session_id` 가 trace ID로 연결된다.

## 6. 이미지 전처리 파이프라인

```
1. MIME / size 검증 (10MB, jpeg|png)
2. PIL.Image.open + verify (decode 가능 여부)
3. EXIF orientation 정규화 (ImageOps.exif_transpose)
4. 사람 검출 (MediaPipe Pose) — 미검출 시 400
5. 얼굴 검출 + 가우시안 블러 (MediaPipe Face Detector, 강도 σ=20)
6. 긴 변 1024px 리사이즈 (LANCZOS)
7. JPEG quality=90 재인코딩
```

## 7. 캐싱

| 데이터 | 키 | TTL | 저장소 |
|---|---|---|---|
| 세션 결과 (전체) | `session:{id}` | 24h | Redis (또는 SQLite for dev) |
| Dress code Tier-1 RAG | `dresscode:tier1:{event_type}` | 영구 (앱 시작 시 로드) | 메모리 |
| Dress code Tier-2 결과 | `dresscode:tier2:{normalized_event_type}` | 24h | Redis |
| Web fetch 결과 | `webfetch:{url_hash}` | 24h | Redis (Tier-2 효율화) |
| Vision 응답 | 세션 결과에 포함 | - | - |

## 8. Rate Limiting

- IP 기준: 10 req/min
- 글로벌: OpenAI API 호출 큐 (max concurrency 5)
- **Tier-2 글로벌 한도** (외부 검색 API + 웹 fetch 비용 보호):
  - 일일 200회 (configurable, env: `TIER2_DAILY_BUDGET`)
  - 분당 10회 (env: `TIER2_RPM_LIMIT`)
  - 한도 초과 시 Context Agent에 `budget_exhausted=true` 신호 → fallback_general 사용
- Tier-2 호출 카운터는 Redis INCR (atomic), 자정 KST 리셋

## 9. 관측성

### 9.1 구조적 로깅 (필수 필드)
```json
{
  "ts": "...",
  "level": "info",
  "event": "agent_call",
  "session_id": "...",
  "agent": "vision|context|recommendation|context_tier2_react",
  "latency_ms": 1234,
  "tokens_in": 1024,
  "tokens_out": 512,
  "schema_pass": true,
  "retry_count": 0,
  "tier2_meta": {
    "react_steps": 4,
    "web_search_calls": 2,
    "fetch_calls": 4,
    "sources_count": 2,
    "extraction_confidence": 0.78,
    "budget_consumed": 1
  }
}
```

### 9.2 메트릭 (Prometheus 권장)
- `agent_latency_seconds{agent}`
- `agent_failures_total{agent, reason}`
- `schema_pass_rate{agent}`
- `external_api_errors_total{api}`

### 9.3 트레이싱
- 세션ID를 trace ID로 사용
- Agent 호출은 child span

## 10. 보안

- API 키는 환경변수 (`OPENAI_API_KEY`)
- CORS: Frontend origin만 허용
- 업로드 이미지: 24시간 후 자동 삭제 cron
- 로그에 raw 이미지 base64 저장 금지

## 11. 테스트 전략

### 11.1 단위 테스트
- 이미지 전처리 각 단계 (orientation, blur, resize)
- 오케스트레이터 mock agent로 시퀀스 검증
- 에러 매핑 (Agent error → HTTP 코드)

### 11.2 통합 테스트
- 골든 이미지 1장 + 모킹된 Context Agent → 응답 schema 검증
- session 캐시 hit 검증

### 11.3 E2E (CI gating)
- 실제 OpenAI 호출 (mocked in CI default, real in nightly)
- 5개 시나리오 (event_type별)

## 12. 성능 목표

| 지표 | 목표 |
|---|---|
| Latency P50 (cold) | ≤ 6s |
| Latency P95 (cold) | ≤ 8s |
| Latency P50 (cache hit) | ≤ 200ms |
| 동시 요청 처리 | ≥ 5 req 동시 |
| 메모리 사용량 | ≤ 1GB |

## 13. 마일스톤

| 주차 | 산출물 |
|---|---|
| 1주차 | FastAPI 스캐폴드 + 이미지 전처리 + Vision Agent 호출 |
| 2주차 | Context Agent 통합 + 병렬 오케스트레이션 + 캐시 |
| 3주차 | Recommendation 통합 + 시뮬레이션 endpoint + 관측성 + E2E |

## 14. 다른 역할과의 인터페이스

- **Frontend**: API 계약 (07-data-contracts.md)을 단일 진실 소스로 사용. OpenAPI schema 자동 생성/배포.
- **Vision/Context/Recommendation Agent 담당자**: 각 모듈의 함수 시그니처가 본 spec의 `agents/*/agent.py`와 일치하도록 협의.
