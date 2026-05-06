# 03. Context Agent — 사양

> 담당자: AI 개발 #2
> 책임: 일정/위치 → 컨텍스트 데이터 조회.
> **2-Tier 구조**: Tier-1(결정적, 캐시 히트) + Tier-2(ReAct 기반 실시간 웹 리서치 + 동적 RAG 보강)

## 1. 책임

1. 일정 정보 정규화 (event_type, datetime, location)
2. 외부 날씨 API 호출 → 정량 지표 산출 (결정적)
3. **Tier-1 정적 RAG**: 사전 구축된 9개 event_type 드레스코드 문서 검색
4. **Tier-2 Live Research Agent (ReAct)**: 정적 RAG가 미흡하거나 새로운 사용자 정의 event_type일 때, 웹 검색을 통해 외부 정보(블로그, 유튜브 자막, 공식 가이드)를 수집해 **임시 RAG 문서 생성** 후 검색
5. 수집된 정보는 **정량 지표(formality range, expected_categories, color guidance)로 추출/정규화**해서 반환 — 자유 서술 금지
6. 검증된 Tier-2 문서는 **승격(promote)** 절차를 거쳐 정적 RAG에 편입

## 2. 비-책임 (명시적 금지)

| 금지 항목 | 이유 |
|---|---|
| 의류 평가 | Recommendation Agent의 책임 |
| 사용자 일정 자동 추론 (캘린더 연동) | MVP 범위 외 |
| "어떤 자리인지 분위기 추정" | 주관적 추론 → 금지 |
| 사용자 위치 자동 추적 | 프라이버시 |
| 웹 검색 결과를 그대로 자연어로 사용자에게 전달 | 본 Agent는 **정량 지표 추출**까지만, 표시는 Recommendation/Frontend 책임 |
| Tier-2 결과를 자동으로 정적 RAG에 영구 저장 | 검증 없이 편입 시 환각 누적 위험 — 승격 절차 필수 |

## 3. 입력

```python
class ContextRequest(BaseModel):
    session_id: str
    event_type: str  # 9개 enum 또는 사용자 정의 free-text
    event_type_is_custom: bool = False  # true면 Tier-2 강제
    event_datetime: datetime
    city_code: str
    is_indoor: bool = False
    allow_live_research: bool = True  # 사용자가 비활성화 가능 (오프라인/속도 우선)
```

`event_type` 은 Tier-1을 우선 사용하지만, **사용자가 직접 입력한 free-text** 또는 **Tier-1 RAG match score < 0.6** 인 경우 Tier-2로 자동 폴백.

## 4. 2-Tier 처리 흐름

```
ContextRequest
    │
    ├──► Weather API (결정적, 항상 실행, 병렬)
    │
    └──► DressCode 해석
           │
           ├─ Tier-1: Static RAG 검색
           │    │
           │    ├─ match_score ≥ 0.6 → Tier-1 결과 반환 (LLM 미사용, ~50ms)
           │    │
           │    └─ match_score < 0.6 OR event_type_is_custom=true
           │         │
           │         └─► Tier-2 활성화
           │
           └─ Tier-2: Live Research Agent (ReAct + LLM)
                  │
                  ├─ 1. 검색어 생성
                  ├─ 2. Web Search (제한된 도메인)
                  ├─ 3. 결과 fetch + 본문 추출
                  ├─ 4. LLM이 정량 지표로 구조화 (schema 강제)
                  ├─ 5. 임시 RAG 문서 생성 + 인메모리 인덱스 저장
                  ├─ 6. 임시 인덱스에서 retrieve → 결과 반환
                  └─ 7. (비동기) 승격 큐에 적재 → 사람 검수 후 정적 RAG 편입
```

## 5. Tier-1: Static RAG (사전 구축)

### 5.1 데이터 구성
- `data/dresscode/static/` 에 9개 event_type별 마크다운 문서
- 각 문서 구조 (LLM 출력과 동일한 정규화 schema):
  ```yaml
  event_type: interview
  expected_formality_range: [70, 95]
  expected_categories:
    top: [shirt, blouse]
    bottom: [slacks, skirt]
    outer: [blazer, jacket]
    shoes: [dress_shoes, loafers]
  color_guidance:
    preferred_tones: [neutral, dark]
    avoid_tones: [neon, fluorescent]
  source: hand_curated
  curated_at: 2025-04-15
  ```
- 임베딩: `text-embedding-3-small` 또는 `ko-sroberta-multitask`
- 벡터 저장소: 로컬 FAISS index (정적, 앱 시작 시 로드)

### 5.2 쿼리
- 입력: `event_type` (한국어 키워드까지 허용)
- 검색: top-2 retrieve → score > 0.6 시 사용
- score < 0.6 시 Tier-2 폴백

## 6. Tier-2: Live Research Agent (ReAct)

### 6.1 트리거 조건
- Tier-1 match score < 0.6
- 또는 `event_type_is_custom = true` (예: "회사 송년회", "와인 시음회")
- 단, `allow_live_research = false` 면 Tier-2 비활성, "general" fallback

### 6.2 ReAct 루프 구조

```
LLM (planner) ──► Tool 호출 ──► 관찰 ──► LLM ──► ... (max 5 step)
```

**허용 도구 (제한적, 화이트리스트):**
| Tool | 설명 |
|---|---|
| `web_search(query, limit=5)` | 검색엔진 API. 도메인 화이트리스트 적용. |
| `fetch_page(url)` | URL 본문 추출. robots.txt 존중. 최대 50KB 본문. |
| `youtube_transcript(video_id)` | 자막만 추출 (영상 미다운로드). |
| `extract_facts(content, schema)` | 추출된 본문에서 schema에 맞춘 정량 지표 추출 (LLM 호출). |

**금지된 도구:**
- 임의의 코드 실행
- 파일 시스템 쓰기 (캐시 외)
- 외부 API 호출 (위 4개 외)

### 6.3 도메인 화이트리스트
신뢰 가능 도메인만 허용 (환각 + 부적절 콘텐츠 방지):

```yaml
allowed_domains:
  # 한국 패션/생활 가이드
  - brunch.co.kr
  - blog.naver.com   # 매거진 카테고리만
  - tistory.com
  - velog.io
  - magazine.hankyung.com
  - news.naver.com
  - vogue.co.kr
  - elle.co.kr
  - gqkorea.co.kr
  # 기업/공식
  - jobkorea.co.kr
  - saramin.co.kr
  - linkedin.com
  # 영상
  - youtube.com  # 자막만
blocked_patterns:
  - "*.adult.*"
  - "*shopping*"   # 광고/쇼핑몰 제외
```

### 6.4 검색 전략 (LLM이 생성하는 쿼리 템플릿)

LLM은 다음 패턴 중에서 쿼리를 생성한다 (자유 입력 금지, 템플릿 강제):
```
"한국 {event_type} 드레스코드"
"{event_type} 복장 가이드 한국"
"{event_type} {계절} 옷차림"
"{event_type} 면접 추천 복장"  // event_type별 변형
```

### 6.5 정량 지표 추출 (extract_facts)

LLM이 fetch한 본문을 다음 schema로 강제 추출:
```json
{
  "expected_formality_range": [number, number],   // 0-100
  "expected_categories": {
    "top": ["허용된 카테고리 enum 값"],
    "bottom": ["..."],
    "outer": ["..."],
    "shoes": ["..."]
  },
  "color_guidance": {
    "preferred_tones": ["neutral", "dark", ...],
    "avoid_tones": ["neon", ...]
  },
  "evidence_quotes": [
    {"url": "...", "quote": "...", "fetched_at": "..."}
  ],
  "extraction_confidence": 0.0-1.0
}
```

**제약:**
- 본문에서 "어울린다/매력적이다" 같은 주관 표현은 무시.
- `expected_categories` 의 값은 `02-agent-vision-spec.md` 의 controlled vocabulary 만 사용.
- `extraction_confidence < 0.5` 면 결과 폐기.

### 6.6 다중 소스 합의 (Consensus)

Tier-2는 **최소 2개 독립 소스** 에서 합의된 값만 채택:
- 각 소스에서 추출한 값을 모은 뒤 다음 룰 적용:
  - `expected_formality_range`: 모든 소스의 교집합 → 비면 평균±10
  - `expected_categories`: 2개 이상 소스에 공통으로 나타난 카테고리만 채택
  - `color_guidance`: 합집합 (관용적)

소스가 1개뿐이면 `rag_match_score = 0.5` 로 강등 + warning 표시.

### 6.7 임시 RAG 인덱스

- Tier-2 결과는 **세션 단위 인메모리 RAG**에 저장 (`session_id` 키)
- 동일 세션 내 추가 질의 발생 시 재사용
- 세션 종료 24시간 후 자동 삭제

### 6.8 비용/속도 제한

| 항목 | 제한 |
|---|---|
| 1 요청당 web_search 호출 | 최대 3회 |
| 1 요청당 fetch_page 호출 | 최대 5회 |
| ReAct step 수 | 최대 5 |
| Tier-2 전체 latency 상한 | 12초 (초과 시 부분 결과 + warning) |
| 일일 Tier-2 호출 글로벌 상한 | 200회 (외부 API 비용 보호) |

상한 초과 시 `general` fallback + `tier2_budget_exceeded` warning.

## 7. 출력

```json
{
  "session_id": "sess_xxx",
  "weather": {
    "available": true,
    "temperature_celsius": 6.5,
    "feels_like_celsius": 3.2,
    "precipitation_probability": 0.65,
    "precipitation_intensity_mm_h": 1.2,
    "wind_speed_mps": 4.5,
    "humidity": 0.71,
    "is_outdoor_relevant": true
  },
  "dress_code": {
    "event_type": "interview",
    "tier": "tier1",
    "rag_match_score": 0.91,
    "expected_formality_range": [70, 95],
    "expected_categories": {
      "top": ["shirt", "blouse"],
      "bottom": ["slacks", "skirt"],
      "outer": ["blazer", "jacket"],
      "shoes": ["dress_shoes", "loafers"]
    },
    "color_guidance": {
      "preferred_tones": ["neutral", "dark"],
      "avoid_tones": ["neon", "fluorescent"]
    },
    "source_doc_ids": ["dc_interview_v1"],
    "evidence_quotes": [],   // tier1은 비어있음
    "extraction_confidence": 1.0
  },
  "thermal_band": "cool",
  "warnings": []
}
```

### 7.1 Tier-2 응답 예 (사용자 정의 event_type)
```json
"dress_code": {
  "event_type": "회사 송년회",
  "tier": "tier2_live",
  "rag_match_score": 0.74,
  "expected_formality_range": [55, 80],
  "expected_categories": { ... },
  "color_guidance": { ... },
  "source_doc_ids": ["live_session_xxx_doc1"],
  "evidence_quotes": [
    {"url": "https://brunch.co.kr/...", "quote": "송년회는...", "fetched_at": "..."},
    {"url": "https://tistory.com/...", "quote": "...", "fetched_at": "..."}
  ],
  "extraction_confidence": 0.78,
  "live_research_meta": {
    "search_queries_used": ["한국 송년회 드레스코드", "회사 연말회식 복장"],
    "sources_count": 2,
    "react_steps": 4,
    "latency_ms": 8400
  }
}
```

## 8. 승격 (Promotion) 절차

Tier-2 결과의 정적 RAG 편입은 **자동이 아닌 사람 검수**.

```
Tier-2 결과 → promotion_queue (DB 또는 JSONL)
   │
   ▼
사람(팀원)이 주기적으로 큐 검토 (주 1회)
   │
   ├─ 승인: data/dresscode/static/ 에 PR 생성 → 머지 후 정적 RAG 재인덱싱
   └─ 거절: 큐에서 삭제 + 거절 사유 기록
```

자동 승격 금지 이유: LLM 환각이 정적 RAG에 누적되면 모든 후속 사용자에게 영향.

## 9. 결정성 (Tier별)

| Tier | 결정성 | 이유 |
|---|---|---|
| Tier-1 | 100% | 사전 구축 인덱스 + 결정적 retrieve |
| Tier-2 | 부분 결정성 | LLM + 외부 웹. 단, schema 강제 + 다중 소스 합의로 변동성 제한 |
| Weather | 캐시 히트시 100% | (city, hour) 키 1시간 TTL |

Tier-2 응답은 항상 `evidence_quotes` 를 포함하므로, 동일 입력에 다른 결과가 나오면 사용자가 출처를 직접 검증 가능.

## 10. Thermal Band 변환 (결정적 룰)

| 체감온도 | thermal_band |
|---|---|
| < -5°C | `very_cold` |
| -5 ~ 5°C | `cold` |
| 5 ~ 15°C | `cool` |
| 15 ~ 22°C | `mild` |
| 22 ~ 28°C | `warm` |
| > 28°C | `hot` |

`scoring/thermal.py` 의 룩업 테이블로 고정.

## 11. LangGraph Sub-graph 구조

본 Agent는 **두 개의 sub-graph (weather + dresscode)** 를 합쳐 단일 sub-graph로 export한다. 내부에서 weather와 dresscode가 병렬 실행되며, dresscode는 Tier-1/Tier-2 분기 + Tier-2의 ReAct 루프를 가진다.

### 11.1 ContextState

```python
class ContextState(BaseModel):
    # 입력
    request: ContextRequest

    # Weather lane
    weather: Optional[WeatherInfo] = None
    weather_available: bool = False

    # Dresscode lane
    tier1_result: Optional[DressCode] = None
    tier1_score: float = 0.0

    # Tier-2 ReAct 상태
    tier2_active: bool = False
    react_step: int = 0
    search_queries_used: list[str] = []
    fetched_pages: list[FetchedPage] = []
    extracted_facts_per_source: list[ExtractedFacts] = []
    tier2_consensus: Optional[DressCode] = None
    tier2_meta: dict = {}

    # 최종 결과
    dress_code: Optional[DressCode] = None
    thermal_band: Optional[str] = None

    warnings: list[str] = []
```

### 11.2 그래프 정의

```python
from langgraph.graph import StateGraph, END

def build_context_graph():
    g = StateGraph(ContextState)

    # Weather lane (단일 노드, 병렬용)
    g.add_node("fetch_weather", node_fetch_weather)

    # Dresscode lane
    g.add_node("tier1_retrieve", node_tier1_retrieve)
    g.add_node("decide_tier", node_decide_tier)             # 결정적 분기 헬퍼

    # Tier-2 ReAct 루프 노드들
    g.add_node("tier2_plan_query", node_tier2_plan_query)   # LLM
    g.add_node("tier2_web_search", node_tier2_web_search)   # 도구
    g.add_node("tier2_fetch_pages", node_tier2_fetch_pages) # 도구
    g.add_node("tier2_extract_facts", node_tier2_extract_facts)  # LLM
    g.add_node("tier2_consensus", node_tier2_consensus)     # 결정적
    g.add_node("tier2_promotion_enqueue", node_tier2_promotion_enqueue)

    # 최종 합류
    g.add_node("compute_thermal_band", node_compute_thermal_band)
    g.add_node("pack_context", node_pack_context)

    g.set_entry_point("__start__")  # langgraph가 fan-out

    # 병렬 fan-out
    g.add_edge("__start__", "fetch_weather")
    g.add_edge("__start__", "tier1_retrieve")

    # Tier 결정 (Tier-1 score + custom 플래그 + budget)
    g.add_edge("tier1_retrieve", "decide_tier")
    g.add_conditional_edges(
        "decide_tier",
        decide_dresscode_tier,
        {
            "use_tier1": "compute_thermal_band",
            "fallback_general": "compute_thermal_band",
            "go_tier2": "tier2_plan_query",
        }
    )

    # Tier-2 ReAct 루프
    g.add_edge("tier2_plan_query", "tier2_web_search")
    g.add_edge("tier2_web_search", "tier2_fetch_pages")
    g.add_edge("tier2_fetch_pages", "tier2_extract_facts")
    g.add_conditional_edges(
        "tier2_extract_facts",
        decide_tier2_continue,
        {
            "more_search": "tier2_plan_query",   # step < 5 이고 소스 < 2
            "consensus": "tier2_consensus",
            "abort": "compute_thermal_band",     # budget/timeout
        }
    )
    g.add_edge("tier2_consensus", "tier2_promotion_enqueue")
    g.add_edge("tier2_promotion_enqueue", "compute_thermal_band")

    # weather와 dresscode 합류 (compute_thermal_band가 fan-in 지점)
    g.add_edge("fetch_weather", "compute_thermal_band")

    g.add_edge("compute_thermal_band", "pack_context")
    g.add_edge("pack_context", END)

    return g.compile()

context_subgraph = build_context_graph()
```

### 11.3 분기 함수

```python
def decide_dresscode_tier(state: ContextState) -> str:
    if state.tier1_score >= 0.6 and not state.request.event_type_is_custom:
        return "use_tier1"
    if not state.request.allow_live_research or budget_exhausted():
        return "fallback_general"
    return "go_tier2"

def decide_tier2_continue(state: ContextState) -> str:
    n_sources = len([e for e in state.extracted_facts_per_source
                     if e.extraction_confidence >= 0.5])
    if state.react_step >= 5 or latency_exceeded(state):
        return "abort"
    if n_sources >= 2:
        return "consensus"
    return "more_search"
```

### 11.4 노드 책임

| 노드 | 종류 | 책임 |
|---|---|---|
| `fetch_weather` | 도구 (HTTP) | Weather API 호출 + 캐시 |
| `tier1_retrieve` | 도구 (FAISS) | Static RAG 검색 |
| `decide_tier` | 결정적 헬퍼 | Tier 분기 신호 산출 |
| `tier2_plan_query` | LLM | 다음 검색 쿼리 1개 생성 (템플릿 강제) |
| `tier2_web_search` | 도구 | 검색 API 호출, 화이트리스트 필터 |
| `tier2_fetch_pages` | 도구 | URL fetch (robots.txt 존중, 50KB cap) |
| `tier2_extract_facts` | LLM | 본문 → 정량 schema 강제 추출 |
| `tier2_consensus` | 결정적 | 다중 소스 합의 룰 적용 |
| `tier2_promotion_enqueue` | 결정적 | 승격 큐(JSONL)에 비동기 기록 |
| `compute_thermal_band` | 결정적 | 룩업 테이블 |
| `pack_context` | 결정적 | ContextResponse 패키징 |

### 11.5 Super-graph 노출

```python
# backend/app/agents/context/__init__.py
from .graph import context_subgraph

__all__ = ["context_subgraph"]
```

## 12. 테스트 전략

### 12.1 Tier-1 단위 테스트
- 9개 event_type 모두 score > 0.6 검증
- 한국어 동의어 입력 (예: "면접" vs "interview") → 동일 매칭

### 12.2 Tier-2 단위 테스트 (모킹)
- `web_search`/`fetch_page` 모킹 → 골든 결과 schema 검증
- ReAct step 5회 초과 시 종료 검증
- 단일 소스만 발견 → `rag_match_score ≤ 0.5` 강등 검증
- 도메인 화이트리스트 위반 URL → 자동 차단 검증
- LLM 출력에 금지 단어 ("매력적", "어울리는") → 필터링 검증

### 12.3 통합 테스트 (Tier-2 실제 호출)
- 사용자 정의 event_type 5개 (예: "송년회", "와인 시음회", "친구 결혼식 2부", "동호회 모임", "전시 오프닝")
- 결과 schema + evidence_quotes 존재 검증
- 야간 빌드에서만 실행 (비용)

### 12.4 회귀: 정적 RAG 변경 영향
- 정적 RAG 문서 수정 시 9개 시나리오 점수 변동 ≤ 5점 확인

## 13. 성능 목표

| 지표 | 목표 |
|---|---|
| Tier-1 latency | ≤ 50ms |
| Tier-2 latency P50 | ≤ 8s |
| Tier-2 latency P95 | ≤ 12s (상한) |
| Tier-1 hit rate (9개 event_type) | ≥ 95% |
| Tier-2 schema pass rate | ≥ 90% |
| Tier-2 다중 소스 합의 비율 | ≥ 70% |

## 14. 마일스톤

| 주차 | 산출물 |
|---|---|
| 1주차 | Weather API 통합 + thermal_band + Tier-1 정적 RAG 9개 문서 + FAISS index |
| 2주차 | Tier-2 ReAct 골격 (web_search + fetch_page mock) + extract_facts schema + 다중 소스 합의 룰 |
| 3주차 | 도메인 화이트리스트 + 비용 제한 + 승격 큐 + 통합 테스트 + 야간 실호출 검증 |

## 15. 다른 역할과의 인터페이스

- **Backend**: `resolve_context(req)` 호출. `live_research_agent` 의 비용 제한(글로벌 카운터)을 Backend가 관리.
- **Recommendation Agent**: `dress_code.tier` 값에 따라 가중치 조정 가능 (예: tier2일 때 `dresscode_alignment` 가중치 -0.05).
- **Frontend**: tier가 `tier2_live` 인 경우 결과 화면에 "외부 출처 기반 추정" 배지 + `evidence_quotes` 의 출처 링크 노출 (사용자에게 투명성 제공).
