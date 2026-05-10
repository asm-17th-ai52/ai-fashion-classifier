# 02. Vision Agent — 사양

> 담당자: AI 개발 #1
> 책임: 착장 이미지 → **정량화 가능한 의류 속성 JSON** 추출
> **Architecture**: Verify-and-Refine 루프 (VLM Extractor + 결정적 Verifier 도구 + Critic 라우터)

## 1. Agent로 분류되는 근거

본 모듈은 단일 LLM 호출이 아닌 **에이전틱 워크플로우**를 가진다.

| Agentic 속성 | 본 Agent 구현 |
|---|---|
| **Tool use** | rembg 배경 제거, OpenCV k-means 색상 추출, schema validator, consistency checker 등 결정적 도구 호출 |
| **Self-critique** | Verifier 결과를 보고 어떤 필드가 잘못되었는지 자기 진단 |
| **Multi-step** | Extract → Verify → Critic → Targeted Re-extract (최대 3 step) |
| **Adaptive routing** | Verifier 통과 시 1 step 종료, 실패 시 부분 재호출 (전체 재호출 금지) |
| **결정성 유지** | LLM은 "추출"과 "어떤 슬롯을 다시 볼지 결정"만 담당, 모든 검증·계산은 결정적 도구 |

## 2. 책임 (Responsibilities)

1. 이미지 입력 검증 (해상도, 인물 존재, 정면성) — 결정적 도구
2. 슬롯별 수직 영역 산출 (이미지 높이 비율 휴리스틱 기반)
3. VLM으로 의류 속성 1차 추출 (전체 슬롯 일괄) + `color_hint` 반환
4. 결정적 Verifier로 추출 결과 검증 (색상 일치, 어휘 위반, 슬롯 중복 등)
5. Verifier 위반 시 Critic LLM이 재추출 대상 결정
6. Targeted re-extraction (위반 슬롯만 ROI 잘라 재호출)
7. 최종 JSON 반환 (schema 100% 준수)

## 3. 비-책임 (명시적 금지)

| 금지 항목 | 이유 |
|---|---|
| 얼굴 인식 / 식별 | 개인정보 + 윤리 위험 |
| 체형 / 신체 비율 분석 | 외모 평가 윤리 위험 |
| 인종 / 성별 / 연령 추론 | 편향 위험 |
| "어울린다 / 멋있다" 평가 | 본 Agent는 추출만, 평가는 Recommendation Agent |
| 가격 / 브랜드 추정 | 신뢰성 부족 |
| 트렌드 분석 | MVP 범위 외 |
| Recommendation 차원 점수 계산 | 책임 분리 위반 |
| 포즈 / 얼굴 감지 (MediaPipe) | MVP 범위 외, 별도 없이 휴리스틱으로 대체 |

## 4. 입력 / 출력

### 4.1 Input
```python
class VisionRequest(BaseModel):
    session_id: str
    image_bytes: bytes  # JPEG/PNG, ≥ 480p, ≤ 10MB (Backend가 전처리)
```

### 4.2 Output
`07-data-contracts.md §2` 의 VisionResponse schema 100% 준수.

추가 메타 필드 (관측성용, 응답에 포함):
```json
"agent_meta": {
  "steps_taken": 2,
  "vlm_calls": 2,
  "verifiers_failed": ["color_label_consistency"],
  "reextracted_slots": ["top"],
  "tool_call_log": [
    {"tool": "validate_image", "ms": 12},
    {"tool": "vlm_extract_all", "ms": 2300, "garment_count": 4},
    {"tool": "overwrite_colors", "slot": "outer", "source": "kmeans", "ms": 45, "rgb": [199, 152, 120], "name": "카멜"},
    {"tool": "overwrite_colors", "slot": "top", "source": "vlm_hint", "ms": 0, "rgb": [255, 255, 255], "name": "흰색"}
  ]
}
```

## 5. 도구 (Tools) — 결정성 분류

### 5.1 결정적 도구 (Tools, 순수 함수)

| Tool | 입력 | 출력 | 라이브러리 |
|---|---|---|---|
| `validate_image(bytes)` | 이미지 바이트 | `ImageQuality{resolution_ok, frontal, occlusion_ratio}` | Pillow + OpenCV |
| `extract_dominant_rgb(image, slot, bbox?)` | 이미지 + 슬롯명 | `(RGB(int,int,int), 한글색상명)` | rembg(배경 제거) + OpenCV k-means (k=5) |
| `verify_schema(json)` | LLM 응답 | `{valid: bool, errors: [...]}` | Pydantic |
| `verify_vocabulary(garments)` | 의류 리스트 | 위반 enum 필드 목록 | 어휘 화이트리스트 lookup |
| `verify_color_label_consistency(garment)` | 단일 garment | RGB ↔ name 매칭 일치 여부 | color_lookup 테이블 |
| `verify_no_duplicate_slot(garments)` | 의류 리스트 | 슬롯 중복 여부 | 단순 카운트 |
| `verify_required_slots(garments)` | 의류 리스트 | 누락 슬롯 목록 | (`top`, `bottom`, `shoes` 기본 필수) |
| `clip_image_by_slot(image_bytes, slot, padding)` | 이미지 바이트 + 슬롯명 + 패딩 비율 | 잘린 이미지 바이트 | Pillow |

**`extract_dominant_rgb` 상세:**
- rembg로 배경(벽, 가구 등) 제거 후 사람 픽셀만 남긴다.
- 슬롯별 수직 비율 힌트로 영역을 자른다 (예: `bottom`은 이미지 높이 58~82%).
- 가로는 중앙 60%만 사용해 팔·손 피부 픽셀을 제외한다.
- k=5 k-means로 지배적 색상을 선택한다.
- rembg 미설치 환경에서는 밝기 임계값(R+G+B < 520) fallback을 사용한다.

### 5.2 LLM 도구

| Tool | 호출 횟수 | 모델 | temperature |
|---|---|---|---|
| `vlm_extract_all(image)` | 1~2회 | Gemini 2.5 Flash (`google.genai` SDK) | 0 |
| `critic_llm(extraction, violations)` | 0~1회 | Gemini 2.5 Flash (또는 경량 텍스트 모델) | 0 |

## 6. 워크플로우 (Verify-and-Refine 루프)

```
┌─────────────────────────────────────────────────────────┐
│ Step 0: 결정적 전처리                                    │
│   validate_image() → resolution_ok? frontal?            │
│   실패 시 즉시 400 (Backend로 에러 전파)                  │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: VLM 1차 추출 (전체 슬롯)                         │
│   vlm_extract_all(image)                                │
│   → garments[] (category, pattern, fit, color_hint 등)  │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1-B: 색상 덮어쓰기                                  │
│   for each garment:                                     │
│     가려진 슬롯 (예: outer 아래 top)                      │
│       → VLM color_hint 사용                              │
│     노출된 슬롯                                           │
│       → rembg + k-means → primary_color 덮어쓰기         │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: 결정적 Verifier (병렬 실행)                      │
│   - verify_schema(json)                                 │
│   - verify_vocabulary(garments)                         │
│   - verify_no_duplicate_slot(garments)                  │
│   - verify_color_label_consistency(garments)            │
│   - verify_required_slots(garments)                     │
│   → violations[] (각 항목: {type, slot, detail})         │
└─────────────────────────────────────────────────────────┘
                  │
              violations 비어있음? ──Yes──► 결과 반환 (1 step 종료)
                  │ No
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Critic LLM (어디를 다시 볼지 결정)                │
│   critic_llm(extraction, violations)                    │
│   → ReextractPlan{                                       │
│       slots: ["top"],            # 재추출 대상 슬롯       │
│       fields: ["category", "primary_color"],             │
│       reason: "RGB(20,20,20) ≠ label 'white'",           │
│       give_up: false              # true면 재시도 안 함   │
│     }                                                    │
│   give_up=true면 부분 결과 + warnings 반환                 │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: Targeted Re-extract                             │
│   for slot in plan.slots:                                │
│     cropped = clip_image_by_bbox(image, slot_bbox)       │
│     vlm_extract(cropped, scope=slot, prev_result=...)    │
│   merge into garments[]                                  │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
                Step 2 재실행 (최대 1회 더, 총 step ≤ 3)
                  │
              여전히 violations? ──Yes──► 부분 결과 + warnings
                  │ No
                  ▼
                결과 반환
```

### 6.1 종료 조건
- Verifier 모두 통과
- 또는 step 카운트 ≥ 3
- 또는 Critic이 `give_up=true`
- 또는 latency 누적 > 7초 (timeout, 부분 결과 반환)

### 6.2 색상 결정 원칙 (Hybrid Strategy)

| 슬롯 조건 | 색상 결정 방식 |
|---|---|
| 외부 노출 슬롯 (outer, bottom, shoes 등) | rembg 배경 제거 후 k-means 픽셀 분석 |
| 가려진 슬롯 (`top` + `outer` 동시 감지 등) | VLM `color_hint` (의미론적 추정) 사용 |

- VLM은 `color_hint`를 반드시 허용된 한글 색상 이름 enum 중 하나로 반환한다 (테이블 외 이름 불허).
- 픽셀 분석 결과가 `(0,0,0)` (유효 픽셀 없음)이면 `color_hint` fallback 사용.
- 색상 `name`은 항상 `color_lookup` 테이블 기반으로 결정 (LLM의 자유 텍스트 이름 무시).

## 7. VLM 프롬프트 설계

### 7.1 1차 추출 (scope="all")
```
[SYSTEM]
You are a clothing attribute extractor. Output JSON ONLY matching the
provided schema. Use ONLY allowed enum values. Do not infer wearer's
identity, body shape, age, gender, or aesthetic judgment.

For color_hint, output the Korean color name that best describes the
garment's color. Choose ONLY from the allowed list in the schema.
color_hint is a semantic judgment — for partially hidden garments
(e.g., a shirt under a coat), estimate based on visible portion.

For each garment slot present in the image (top, bottom, outer, shoes,
bag, watch), return: category, subcategory, color_hint, pattern,
estimated_material, fit, sleeve_length, formality_label, confidence.

If a field is uncertain, use "unknown" and confidence ≤ 0.5.

[USER]
Extract garment attributes from this image.
Return JSON: <schema with color_hint enum list>
```

### 7.2 부분 재추출 (scope="top" 등)
```
[SYSTEM]
(같은 system 메시지)

[USER]
You previously extracted: <prev_garment_for_slot>
Verifiers reported: <violation_detail>
Re-examine ONLY the {slot} slot in the cropped image and output the
corrected garment object. Fields to re-evaluate: <fields>
```

### 7.3 Critic 프롬프트
```
[SYSTEM]
You are a routing critic. Decide which slots/fields need re-extraction.
Output JSON: {slots: [...], fields: [...], reason: "...", give_up: bool}
Set give_up=true ONLY if violations indicate the image is unanalyzable
(e.g., entire body occluded). Otherwise pick minimal scope.

[USER]
Current extraction: <json>
Violations: <list>
```

## 8. Verifier 상세 정의

### 8.1 verify_color_label_consistency
```
input: garment{primary_color.rgb, primary_color.name}
algorithm:
  RGB → 한글 라벨 lookup (color_lookup 테이블) ≠ garment.primary_color.name → violation: "name_rgb_mismatch"
output: violation 또는 None
```

### 8.2 verify_vocabulary
- 모든 enum 필드가 화이트리스트 안에 있는지 확인.
- 위반 시 violation: `{type: "vocab", slot, field, value}`

### 8.3 verify_no_duplicate_slot
- 같은 slot에 2개 이상 garment가 있으면 violation.
- 예외: `bag`, `watch` 는 0~1개로 강제하되 누락은 violation 아님.

### 8.4 verify_required_slots
- 기본 필수: `top`, `bottom`, `shoes`
- 누락 시 warnings에 추가, violation은 아님 (재촬영 권장 메시지 표시)

### 8.5 verify_schema
- Pydantic strict mode로 전체 응답 검증.
- 실패 시 무조건 재추출 (스키마 위반은 critic 거치지 않고 자동 재시도).

## 9. confidence 처리

- VLM이 자체 보고하는 `confidence`. 단,
  - `confidence < 0.5` 인 garment의 `formality_label` / `category` 는 Recommendation Agent에서 가중치 0.5배 적용
  - `confidence < 0.3` 인 garment가 있으면 응답의 `warnings` 에 `"low_confidence:slot"` 추가
- Verifier가 통과해도 confidence가 낮으면 재추출 트리거 (옵션):
  - 임계: avg(confidence) < 0.6 → critic이 재추출 결정 가능

## 10. 실패 모드 / Fallback

| 상황 | 처리 |
|---|---|
| `validate_image` 실패 (해상도 미달 등) | `state.error` 설정 → Backend로 400 즉시 전파 |
| Step 1 VLM 호출 실패 (네트워크) | 재시도 1회 → 502 |
| Step 1 schema 위반 | 자동 재추출 (critic 미사용) |
| Step 3 Critic이 give_up | 부분 결과 + warnings, garment confidence 강제 0.4 |
| Step 4 재추출 후에도 위반 | 위반된 슬롯의 garment를 결과에서 제거 + warnings |
| Total latency > 7s | 현재까지의 부분 결과 반환 + `timeout` warning |

## 11. LangGraph Sub-graph 구조

본 Agent는 **LangGraph StateGraph**로 구현한다. Super-graph(Backend)는 이 sub-graph를 단일 노드처럼 호출한다.

### 11.1 VisionState

```python
from pydantic import BaseModel

class VisionState(BaseModel):
    session_id: str
    image: bytes

    # Step 0 산출물
    quality: Optional[ImageQuality] = None
    slot_bboxes: dict = {}          # 슬롯별 bbox (현재 미사용, Step 2 이후 활용 예정)

    # Step 1+ 산출물
    garments: list[Garment] = []
    violations: list[Violation] = []

    # Critic 결과
    reextract_plan: Optional[ReextractPlan] = None
    give_up: bool = False

    # 메타
    steps_taken: int = 0
    vlm_calls: int = 0
    tool_call_log: list[dict] = []
    warnings: list[str] = []
    error: Optional[str] = None     # 치명적 에러 (설정 시 Backend로 400 전파)
```

`Garment` 스키마에 추가된 필드:
```python
class Garment(BaseModel):
    # ... 기존 필드 ...
    color_hint: Optional[str] = None  # VLM 의미론적 색상 추정 (가려진 슬롯 fallback용)
```

### 11.2 그래프 정의

```python
from langgraph.graph import StateGraph, END

def build_vision_graph():
    g = StateGraph(VisionState)

    # 결정적 도구 노드
    g.add_node("validate_image",       node_validate_image)
    g.add_node("overwrite_colors",     node_overwrite_colors)
    g.add_node("run_verifiers",        node_run_verifiers)

    # LLM 노드
    g.add_node("vlm_extract_all",      node_vlm_extract_all)
    g.add_node("vlm_extract_targeted", node_vlm_extract_targeted)
    g.add_node("critic_llm",           node_critic_llm)

    g.set_entry_point("validate_image")

    # Step 0: 이미지 검증 결과에 따라 분기
    g.add_conditional_edges(
        "validate_image",
        _route_after_validate,
        {"ok": "vlm_extract_all", "fail": END}
    )

    # Step 1: VLM 추출 → 색상 덮어쓰기 → Verifier
    g.add_edge("vlm_extract_all",  "overwrite_colors")
    g.add_edge("overwrite_colors", "run_verifiers")

    # Step 2: Verifier 결과에 따라 분기
    g.add_conditional_edges(
        "run_verifiers",
        _route_after_verify,
        {"done": END, "exhausted": END, "critic": "critic_llm"}
    )

    # Step 3: Critic → give_up 또는 재추출
    g.add_conditional_edges(
        "critic_llm",
        _route_after_critic,
        {"give_up": END, "reextract": "vlm_extract_targeted"}
    )

    # Step 3 → Step 1 사이클: 재추출 후 색상 덮어쓰기 → 재검증
    g.add_edge("vlm_extract_targeted", "overwrite_colors")

    return g.compile()

vision_subgraph = build_vision_graph()
```

### 11.3 분기 함수

```python
def _route_after_validate(state: VisionState) -> str:
    """이미지 검증 실패 시 즉시 종료."""
    if state.error:
        return "fail"
    return "ok"

def decide_after_verify(state: VisionState) -> str:
    if not state.violations:
        return "done"
    if state.steps_taken >= 3:
        state.warnings.append("max_steps_reached")
        return "exhausted"
    return "critic"

def decide_after_critic(state: VisionState) -> str:
    if state.reextract_plan and state.reextract_plan.give_up:
        state.warnings.append("critic_gave_up")
        return "give_up"
    return "reextract"
```

### 11.4 노드 책임

각 노드는 **단일 책임**: 한 가지 도구 호출 또는 한 가지 LLM 호출. State를 받아 부분 업데이트(dict)를 반환.

| 노드 | 책임 | 결정성 | 구현 상태 |
|---|---|---|---|
| `validate_image` | 해상도 검증, person_detected | ✓ | 완료 |
| `vlm_extract_all` | 1차 의류 속성 추출 + color_hint | LLM, t=0 | 완료 |
| `overwrite_colors` | rembg+k-means 또는 VLM hint로 색상 결정 | ✓ (hybrid) | 완료 |
| `run_verifiers` | schema/vocab/duplicate/required 검증 일괄 | ✓ | 완료 |
| `critic_llm` | 재추출 대상 결정 | LLM, t=0 | 완료 |
| `vlm_extract_targeted` | 특정 슬롯만 재추출 | LLM, t=0 | 완료 |

### 11.5 Super-graph 노출

```python
# api/app/agents/vision/__init__.py
from .graph import vision_subgraph

async def analyze_outfit(session_id: str, image_bytes: bytes) -> VisionResponse:
    ...
```

Backend는 `analyze_outfit` 을 호출해 Vision Agent를 사용한다 (`05-backend-spec.md §5.2`).

## 12. `astream_events()` 참조 정보 (Backend 전용)

Backend가 `SUPER_GRAPH.astream_events()`를 호출할 때 본 sub-graph에서 발생하는 이벤트와, 각 이벤트에서 꺼낼 수 있는 데이터를 정의한다. Backend의 `map_langgraph_event()` 헬퍼는 이 정보를 기반으로 SSE `progress` 메시지를 포맷팅한다.

| LangGraph 이벤트 | `event["name"]` | `event["data"]["output"]`에서 꺼낼 값 | Backend가 생성할 `message` 예시 |
|---|---|---|---|
| `on_chain_start` | `validate_image` | — | `"사진을 확인하고 있어요"` |
| `on_chain_end` | `validate_image` | `state.preprocess_meta.person_detected` | `"사진에서 사람을 감지했어요"` |
| `on_chain_start` | `vlm_extract_all` | — | `"착장을 분석하고 있어요"` |
| `on_chain_end` | `vlm_extract_all` | `state.garments[i].category`, `state.garments[i].color_name` | `"상의: 드레스 셔츠 · 화이트"` (슬롯별 1회) |
| `on_chain_end` | `overwrite_colors` | — | `"색상 정보를 정밀 보정했어요"` |
| `on_chain_start` | `run_verifiers` | — | `"착장 정보를 검증하고 있어요"` |
| `on_chain_start` | `critic_llm` | — | `"세부 속성을 재확인하고 있어요"` |
| `on_chain_end` | `vision` (sub-graph 전체) | — | `"착장 분석을 완료했어요"` |

- `on_chain_start` 이벤트: `event["data"]`는 입력 state. 아직 출력이 없으므로 고정 메시지를 사용한다.
- `on_chain_end` 이벤트: `event["data"]["output"]`에 노드가 반환한 부분 state dict가 담긴다.
- 슬롯별 메시지(`vlm_extract_all`)는 `garments` 리스트를 순회해 상의 → 하의 → 신발 순으로 각 1회 방출한다.

## 13. 테스트 전략

### 12.1 골든 셋
- `tests/fixtures/vision/` — 라벨링된 이미지 20장 + `expected.json`
- 카테고리 일치율 ≥ 80% (slot별 category)
- 색상 RGB 정확도: extract_dominant_rgb 결과가 수동 측정값과 ΔE2000 ≤ 15

### 12.2 단위 테스트
- 각 Verifier 함수: 정상/위반 케이스 ≥ 5개씩
- Critic 응답 mock → ReextractPlan 파싱
- color overwrite: VLM이 잘못된 색상을 반환해도 최종 응답은 OpenCV 값

### 12.3 워크플로우 테스트
- **시나리오 A**: 1 step 통과 (verifier 모두 OK)
- **시나리오 B**: color 불일치 → critic → top 재추출 → 통과 (2 step)
- **시나리오 C**: 재추출 후에도 위반 → 부분 결과 + warnings (3 step)
- **시나리오 D**: 사람 미검출 → 즉시 400
- **시나리오 E**: VLM 환각 (의류 5개 중 1개 가짜) → consistency 위반 → 제거

### 12.4 회귀 테스트
- 동일 입력 5회 호출 시 카테고리 일치 100% (LLM temperature=0)
- RGB 값은 정확히 동일 (rembg + k-means는 결정적)

### 12.5 Agentic 동작 검증
- `agent_meta.steps_taken` 분포 측정 (목표: 1 step 통과 ≥ 70%, 2 step ≥ 25%, 3 step ≤ 5%)
- Critic 호출 비율 측정

## 13. 성능 목표

| 지표 | 목표 |
|---|---|
| Latency P50 (1 step 통과) | ≤ 2.8s |
| Latency P95 (3 step) | ≤ 6.5s |
| 1 step 통과율 | ≥ 70% |
| 색상 RGB 정확도 (ΔE) | ≤ 15 (수동 측정 대비) |
| 카테고리 정확도 (골든 20장) | ≥ 80% |
| Schema Pass Rate (최종) | ≥ 99% (재시도 후) |
| VLM 평균 호출 수 | ≤ 1.4회 |

## 14. 마일스톤

| 주차 | 산출물 |
|---|---|
| 1주차 | Step 0 결정적 도구(validate, dominant_rgb) + Step 1 VLM 1차 추출 + 골든 5장 |
| 2주차 | Verifier 5종 + 색상 overwrite + 골든 20장 통과 |
| 3주차 | Critic LLM + Targeted re-extract + 워크플로우 테스트 5개 시나리오 + 메트릭 |

## 15. 다른 역할과의 인터페이스

- **Backend**: `analyze_outfit(session_id, image_bytes)` 단일 진입점. 내부 step은 Backend에 노출되지 않음.
- **Recommendation Agent**: `garments[].confidence` 를 가중치 조정 시그널로 사용. `agent_meta` 는 사용하지 않음 (관측성 전용).
- **Frontend**: `agent_meta.steps_taken ≥ 2` 일 때 결과 화면에 작은 배지 "정밀 분석 적용" 표시 (선택, 없어도 무방).

## 16. 정직성 노트

- 이 Agent는 **헤비한 Plan-and-Execute 형태가 아니라** "Verify-and-Refine"이다.
- VLM 호출 1.4회/요청 평균이 목표이며, 비용은 단순 structured output 대비 약 1.5배.
- 색상 인식은 원칙적으로 픽셀 분석이 주이지만, 가려진 슬롯에 한해 VLM 의미론적 판단을 fallback으로 사용한다 — 이는 실용적 trade-off.
- 포즈/얼굴 감지(MediaPipe)는 MVP에서 제외되었으며, 슬롯 영역은 이미지 높이 비율 휴리스틱으로 산출한다.
