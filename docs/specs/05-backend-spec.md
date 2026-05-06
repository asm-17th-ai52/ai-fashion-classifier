# 05. Backend — 사양

> 담당자: Backend 개발자 1명
> 책임: API Gateway / 이미지 전처리 / Agent 오케스트레이션 / 캐싱 / 관측성

## 1. 책임

1. REST API 제공 (Frontend ↔ Backend 경계)
2. 이미지 업로드 검증, 정규화, 얼굴 자동 블러
3. 3개 Agent의 오케스트레이션 (병렬/직렬 제어)
4. 세션 단위 캐싱 (멱등성)
5. 외부 의존성(Weather API, OpenAI API) 키 관리 + rate limit
6. 관측성: 로깅, 메트릭, 트레이싱

## 2. 비-책임

| 항목 | 책임자 |
|---|---|
| 의류 속성 추출 | Vision Agent 담당자 |
| 점수 계산 | Recommendation Agent 담당자 |
| Weather/RAG 조회 | Context Agent 담당자 |
| UI 렌더링 | Frontend 담당자 |

Backend는 위 모듈을 **호출**할 뿐, 내부 로직은 담당자별 모듈에 위임.

## 3. 기술 스택

- 언어: Python 3.11+
- 프레임워크: FastAPI (기획서: `Spring Boot / FastAPI` → 본 spec은 FastAPI 채택, 단일 언어로 Agent 모듈과 통합)
- 비동기: `asyncio`, `httpx`
- 검증: Pydantic v2
- 이미지 처리: Pillow + OpenCV (얼굴 블러용 MediaPipe)
- 테스트: pytest, pytest-asyncio
- 로깅: structlog (JSON 로깅)

## 4. API 엔드포인트

### 4.1 `POST /v1/sessions`
세션 생성 + 이미지 업로드 + 즉시 분석 트리거 (단일 호출)

**Request (multipart/form-data):**
```
image: file (jpeg/png, 1B ≤ size ≤ 10MB)
event_type: string (enum, see Context spec)
event_datetime: string (ISO 8601)
city_code: string
is_indoor: bool (default: false)
```

**Response 200:**
```json
{
  "session_id": "sess_01HXXXXXX",
  "outfit": { ... VisionResponse ... },
  "context": { ... ContextResponse ... },
  "recommendation": { ... RecommendationResponse ... },
  "meta": {
    "latency_ms": 6234,
    "agent_latencies_ms": {
      "vision": 2400, "context": 800, "recommendation": 2900
    },
    "cache_hits": ["weather"]
  }
}
```

**Error responses:**
| 코드 | 의미 | 사용자 메시지 |
|---|---|---|
| 400 | 이미지 검증 실패 / 사람 미검출 | "사람이 정면으로 보이는 사진으로 다시 업로드해 주세요" |
| 413 | 파일 크기 초과 | "10MB 이하 이미지를 사용해 주세요" |
| 422 | 입력 schema 위반 | (필드별 메시지) |
| 429 | rate limit | "잠시 후 다시 시도해 주세요" |
| 502 | Vision/Recommendation Agent 실패 | "AI 분석에 실패했습니다. 다시 시도해 주세요" |
| 503 | Weather API 다운 | (날씨 차원 제외 후 정상 응답으로 처리, 502 아님) |

### 4.2 `GET /v1/sessions/{session_id}`
- 캐시된 분석 결과 재조회 (멱등)
- TTL: 24시간 (이미지 보존 정책에 종속)

### 4.3 `POST /v1/sessions/{session_id}/simulate`
- 사용자가 제안을 수용했을 때의 시뮬레이션 점수 재계산
- 입력: `applied_suggestion_ids: [str]`
- LLM 미사용 (결정적, < 100ms)

### 4.4 `GET /v1/health`
- 외부 의존성 헬스체크 (`weather_api`, `openai`, `vector_db`)

## 5. 오케스트레이션 (핵심 로직)

```python
async def analyze_session(req: SessionCreateRequest) -> SessionResponse:
    image_bytes = await preprocess_image(req.image)  # blur, resize, EXIF
    session_id = mint_session_id()

    # Phase 1: Vision + Context 병렬
    vision_task = vision_agent.analyze_outfit(session_id, image_bytes)
    context_task = context_agent.resolve_context(req.to_context_request())
    outfit, context = await asyncio.gather(vision_task, context_task)

    # Phase 2: Recommendation (직렬)
    recommendation = await recommendation_agent.score_and_suggest(outfit, context)

    # Phase 3: 캐시 저장
    await cache.put(session_id, ttl=86400, ...)

    return SessionResponse(...)
```

Phase 1 병렬은 latency를 ≈ max(vision, context)로 단축한다.

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
| Weather API 응답 | `weather:{city}:{hour}` | 1h | Redis |
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

- API 키는 환경변수 (`OPENAI_API_KEY`, `WEATHER_API_KEY`)
- CORS: Frontend origin만 허용
- 업로드 이미지: 24시간 후 자동 삭제 cron
- 로그에 raw 이미지 base64 저장 금지

## 11. 테스트 전략

### 11.1 단위 테스트
- 이미지 전처리 각 단계 (orientation, blur, resize)
- 오케스트레이터 mock agent로 시퀀스 검증
- 에러 매핑 (Agent error → HTTP 코드)

### 11.2 통합 테스트
- 골든 이미지 1장 + 모킹된 Weather → 응답 schema 검증
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
