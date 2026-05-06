# 02. Vision Agent — 사양

> 담당자: AI 개발 #1
> 책임: 착장 이미지 → **정량화 가능한 의류 속성 JSON** 추출
> **Architecture**: Verify-and-Refine 루프 (VLM Extractor + 결정적 Verifier 도구 + Critic 라우터)

## 1. Agent로 분류되는 근거

본 모듈은 단일 LLM 호출이 아닌 **에이전틱 워크플로우**를 가진다.

| Agentic 속성 | 본 Agent 구현 |
|---|---|
| **Tool use** | OpenCV 색상 추출, MediaPipe 포즈/얼굴, schema validator, consistency checker 등 결정적 도구 5종 호출 |
| **Self-critique** | Verifier 결과를 보고 어떤 필드가 잘못되었는지 자기 진단 |
| **Multi-step** | Extract → Verify → Critic → Targeted Re-extract (최대 3 step) |
| **Adaptive routing** | Verifier 통과 시 1 step 종료, 실패 시 부분 재호출 (전체 재호출 금지) |
| **결정성 유지** | LLM은 "추출"과 "어떤 슬롯을 다시 볼지 결정"만 담당, 모든 검증·계산은 결정적 도구 |

## 2. 책임 (Responsibilities)

1. 이미지 입력 검증 (해상도, 인물 존재, 정면성) — 결정적 도구
2. 슬롯별 ROI 자동 산출 (포즈 키포인트 기반)
3. VLM으로 의류 속성 1차 추출 (전체 슬롯 일괄)
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
    {"tool": "pose_keypoints", "ms": 45},
    {"tool": "vlm_extract", "ms": 2300, "scope": "all"},
    {"tool": "extract_dominant_rgb", "ms": 12, "slot": "top"},
    {"tool": "verify_color_label_consistency", "ms": 1, "passed": false},
    {"tool": "critic_llm", "ms": 380, "decision": "reextract_top_color"},
    {"tool": "vlm_extract", "ms": 1800, "scope": "top"}
  ]
}
```

## 5. 도구 (Tools) — 결정성 분류

### 5.1 결정적 도구 (Tools, 순수 함수)

| Tool | 입력 | 출력 | 라이브러리 |
|---|---|---|---|
| `validate_image(bytes)` | 이미지 바이트 | `ImageQuality{resolution_ok, frontal, occlusion_ratio}` | Pillow + OpenCV |
| `pose_keypoints(image)` | 이미지 | `Keypoints{shoulders, hips, knees, ankles, ...}` + `slot_bboxes{top, bottom, outer, shoes}` | MediaPipe Pose |
| `face_detector(image)` | 이미지 | `face_bboxes` (블러 적용 검증용) | MediaPipe Face |
| `extract_dominant_rgb(image, bbox)` | 이미지 + 영역 | `RGB(int, int, int)` | OpenCV (k-means k=3, 가장 많은 클러스터) |
| `verify_schema(json)` | LLM 응답 | `{valid: bool, errors: [...]}` | Pydantic |
| `verify_vocabulary(garments)` | 의류 리스트 | 위반 enum 필드 목록 | 어휘 화이트리스트 lookup |
| `verify_color_label_consistency(garment)` | 단일 garment | RGB ↔ name 매칭 일치 여부 | RGB → 색상 분류 룩업 (web color → 한글 라벨) |
| `verify_no_duplicate_slot(garments)` | 의류 리스트 | 슬롯 중복 여부 | 단순 카운트 |
| `verify_required_slots(garments, event_type?)` | 의류 리스트 | 누락 슬롯 목록 | (event_type 미주어지면 [top, bottom, shoes]가 기본 필수) |
| `clip_image_by_bbox(image, bbox, padding=20px)` | 이미지 + 영역 | 잘린 이미지 | Pillow |

### 5.2 LLM 도구

| Tool | 호출 횟수 | 모델 | temperature |
|---|---|---|---|
| `vlm_extract(image, scope, prev_result?)` | 1~2회 | GPT-4o Vision (또는 동등 VLM) | 0 |
| `critic_llm(extraction, violations)` | 0~1회 | GPT-4o-mini (또는 텍스트만 가능한 경량 모델) | 0 |

## 6. 워크플로우 (Verify-and-Refine 루프)

```
┌─────────────────────────────────────────────────────────┐
│ Step 0: 결정적 전처리                                    │
│   validate_image() → person_detected? frontal?          │
│   pose_keypoints() → slot_bboxes                        │
│   face_detector() → blur 검증                            │
│   실패 시 즉시 400 (Backend로 에러 전파)                  │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: VLM 1차 추출 (전체 슬롯)                         │
│   vlm_extract(image, scope="all")                       │
│   → garments[] (LLM 출력)                                │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: 결정적 Verifier (병렬 실행)                      │
│   - verify_schema(json)                                 │
│   - verify_vocabulary(garments)                         │
│   - verify_no_duplicate_slot(garments)                  │
│   - for each garment:                                    │
│       extract_dominant_rgb(image, slot_bbox)             │
│       verify_color_label_consistency(garment, true_rgb)  │
│       (LLM의 RGB도 함께 비교 + true_rgb로 덮어쓰기)         │
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
│     cropped = clip_image_by_bbox(image, slot_bboxes[slot])│
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

### 6.2 RGB 우선 원칙
- VLM이 보고한 RGB는 **참고용** (LLM 환각 가능성)
- 모든 garment의 `primary_color.rgb` 는 항상 `extract_dominant_rgb(image, slot_bbox)` 의 결과로 **덮어쓴다**.
- 색상 `name` 도 RGB → 한글 색상 라벨 룩업으로 결정적으로 산출 (LLM의 name 무시).
- 즉, **색상은 VLM이 추정하지 않는다.** VLM은 카테고리·패턴·소재·핏만 담당.

이 원칙으로 정량성·재현성을 크게 강화한다.

## 7. VLM 프롬프트 설계

### 7.1 1차 추출 (scope="all")
```
[SYSTEM]
You are a clothing attribute extractor. Output JSON ONLY matching the
provided schema. Use ONLY allowed enum values. Do not infer wearer's
identity, body shape, age, gender, or aesthetic judgment.

For each garment slot present in the image (top, bottom, outer, shoes,
bag, watch), return: category, subcategory, pattern, estimated_material,
fit, sleeve_length, formality_label, confidence.

DO NOT output color RGB values. Color will be measured separately by
deterministic tools. Set primary_color to {"rgb": [0,0,0], "name": "_pending"}
as placeholder; it will be overwritten.

If a field is uncertain, use "unknown" and confidence ≤ 0.5.

[USER]
Extract garment attributes from this image.
Return JSON: <schema>
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
input: garment{primary_color.rgb (LLM 보고치), primary_color.name}, true_rgb (OpenCV)
algorithm:
  1. ΔE2000(LLM_rgb, true_rgb) > 25 → violation: "vlm_rgb_mismatch"
  2. RGB → 한글 라벨 lookup (color_lookup.csv) ≠ garment.primary_color.name → violation: "name_rgb_mismatch"
output: violation 또는 None
```
- 단, **이 verifier는 정보용**이다. 최종 RGB는 항상 OpenCV 값으로 덮어쓰므로 LLM 라벨이 틀려도 결과에는 영향 없음.
- 하지만 카테고리·패턴 추정도 색상 인식에 의존하므로, 큰 불일치는 다른 필드 신뢰도가 낮다는 신호.

### 8.2 verify_vocabulary
- 모든 enum 필드가 화이트리스트 안에 있는지 확인.
- 위반 시 violation: `{type: "vocab", slot, field, value}`

### 8.3 verify_no_duplicate_slot
- 같은 slot에 2개 이상 garment가 있으면 violation.
- 예외: `bag`, `watch` 는 0~1개로 강제하되 누락은 violation 아님.

### 8.4 verify_required_slots
- 기본 필수: `top`, `bottom`, `shoes`
- thermal_band가 cold 이상일 때 (Backend가 별도로 검증, Vision은 알지 못함)
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
| `validate_image` 실패 (사람 미검출 등) | Backend로 400 즉시 전파 |
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
    slot_bboxes: dict = {}

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
```

### 11.2 그래프 정의

```python
from langgraph.graph import StateGraph, END

def build_vision_graph():
    g = StateGraph(VisionState)

    # 결정적 도구 노드
    g.add_node("validate_image", node_validate_image)
    g.add_node("pose_keypoints", node_pose_keypoints)
    g.add_node("face_blur_check", node_face_blur_check)

    # LLM 노드
    g.add_node("vlm_extract_all", node_vlm_extract_all)
    g.add_node("vlm_extract_targeted", node_vlm_extract_targeted)
    g.add_node("critic_llm", node_critic_llm)

    # Verifier 노드 (병렬 실행 후 합류)
    g.add_node("run_verifiers", node_run_verifiers)
    g.add_node("overwrite_colors", node_overwrite_colors)

    g.set_entry_point("validate_image")

    # Step 0 직선
    g.add_edge("validate_image", "pose_keypoints")
    g.add_edge("pose_keypoints", "face_blur_check")
    g.add_edge("face_blur_check", "vlm_extract_all")

    # Step 1 → Verify (색상 항상 덮어쓰기)
    g.add_edge("vlm_extract_all", "overwrite_colors")
    g.add_edge("overwrite_colors", "run_verifiers")

    # 분기: violations 비어있으면 END, 아니면 critic
    g.add_conditional_edges(
        "run_verifiers",
        decide_after_verify,   # 함수: violations + steps_taken 확인
        {
            "done": END,
            "critic": "critic_llm",
            "exhausted": END,   # steps_taken ≥ 3
        }
    )

    # Critic 분기: give_up이면 END, 아니면 targeted re-extract
    g.add_conditional_edges(
        "critic_llm",
        decide_after_critic,
        {
            "reextract": "vlm_extract_targeted",
            "give_up": END,
        }
    )

    # Re-extract 후 다시 verify
    g.add_edge("vlm_extract_targeted", "overwrite_colors")

    return g.compile()

vision_subgraph = build_vision_graph()
```

### 11.3 분기 함수

```python
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

| 노드 | 책임 | 결정성 |
|---|---|---|
| `validate_image` | 사람 검출, 해상도 | ✓ |
| `pose_keypoints` | 슬롯 ROI 산출 | ✓ |
| `face_blur_check` | 블러 적용 검증 | ✓ |
| `vlm_extract_all` | 1차 의류 속성 추출 (color 제외) | LLM, t=0 |
| `overwrite_colors` | OpenCV로 RGB 측정해 garment 덮어쓰기 | ✓ |
| `run_verifiers` | schema/vocab/duplicate/required 검증 일괄 | ✓ |
| `critic_llm` | 재추출 대상 결정 | LLM, t=0 |
| `vlm_extract_targeted` | 특정 슬롯만 재추출 | LLM, t=0 |

### 11.5 Super-graph 노출

```python
# backend/app/agents/vision/__init__.py
from .graph import vision_subgraph

__all__ = ["vision_subgraph"]
```

Backend는 `vision_subgraph` 를 import해 super-graph의 노드로 추가한다 (`05-backend-spec.md §5.2`).

## 12. 테스트 전략

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
- 동일 입력 5회 호출 시 카테고리 일치 100% (LLM 결정성)
- RGB 값은 정확히 동일 (OpenCV는 결정적)

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
| 1주차 | Step 0 결정적 도구(validate, pose, face_blur, dominant_rgb) + Step 1 VLM 1차 추출 + 골든 5장 |
| 2주차 | Verifier 5종 + 색상 overwrite + 골든 20장 통과 |
| 3주차 | Critic LLM + Targeted re-extract + 워크플로우 테스트 5개 시나리오 + 메트릭 |

## 15. 다른 역할과의 인터페이스

- **Backend**: `analyze_outfit(session_id, image_bytes)` 단일 진입점. 내부 step은 Backend에 노출되지 않음.
- **Recommendation Agent**: `garments[].confidence` 를 가중치 조정 시그널로 사용. `agent_meta` 는 사용하지 않음 (관측성 전용).
- **Frontend**: `agent_meta.steps_taken ≥ 2` 일 때 결과 화면에 작은 배지 "정밀 분석 적용" 표시 (선택, 없어도 무방).

## 16. 정직성 노트

- 이 Agent는 **헤비한 Plan-and-Execute 형태가 아니라** "Verify-and-Refine"이다.
- LLM 호출 1.4회/요청 평균이 목표이며, 비용은 단순 structured output 대비 약 1.5배.
- 정확도와 결정성을 위해 색상 인식은 LLM에서 **완전히 분리**했다 — 이는 본 Agent의 핵심 설계 결정.
