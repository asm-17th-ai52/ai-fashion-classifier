# 04. Recommendation Agent — 사양

> 담당자: AI 개발 #3
> 책임: Vision 출력 + Context 출력 → **이분법 체크리스트 평가 + 설명 가능한 개선 제안** 산출
> **Architecture**: Pass/Fail 체크 항목 → Group-weighted score + Critical Blocker → Failed-check 1:1 제안 생성 → LLM Narrator

## 1. 책임

1. 17개 binary 체크 항목을 결정적으로 평가 (pass / fail / not_applicable)
2. 그룹별 pass rate 산출 → 종합 점수 계산
3. Critical blocker 위반 시 점수 cap 적용 + 강한 경고
4. 각 failed check에 대한 1:1 fix action 생성
5. 시뮬레이션으로 expected_delta 검증 후 top-3 제안 채택
6. LLM은 **숫자/사실을 자연어로 포장**하는 역할만 수행

## 2. 비-책임 (명시적 금지)

| 금지 항목 | 이유 |
|---|---|
| 점수를 LLM에게 직접 산출시키기 | 재현성 파괴 |
| 연속값 sub-score (예: "color_contrast 78점") 출력 | 본 spec은 이분법 체크리스트로 일원화 |
| 차원별 가중치 튜닝 | 모든 체크는 그룹 안에서 동등 가중 (단순함이 미덕) |
| "이 옷이 매력적입니다" 류 출력 | 주관적 평가 |
| "이성에게 호감", "신뢰감" 등 인상 평가 | 본 프로젝트 명시적 제외 영역 |
| 구매 추천 / 가격 정보 | MVP 범위 외 |
| 사용자 외모 평가 | 윤리 위험 |

## 3. 입력

```python
class RecommendationRequest(BaseModel):
    session_id: str
    outfit: VisionResponse
    context: ContextResponse
```

## 4. 출력

```json
{
  "session_id": "sess_xxx",
  "score": {
    "overall": 67,
    "method": "group_weighted_with_blocker_cap",
    "group_scores": {
      "dresscode": 0.50,
      "consistency": 1.00,
      "color": 0.66,
      "environment": 0.66,
      "confidence": 1.00
    },
    "blocker_failed": false,
    "cap_applied": null
  },
  "checks": [
    {
      "id": "A3",
      "group": "dresscode",
      "label": "신발 카테고리가 기대 범위에 포함",
      "result": "fail",
      "applicable": true,
      "evidence_facts": [
        "event_type=interview expects shoes in [dress_shoes, loafers]",
        "current shoes category=sneakers"
      ],
      "is_blocker": false
    },
    {
      "id": "A5",
      "group": "dresscode",
      "label": "평균 포멀니스가 기대 범위 안에 위치",
      "result": "fail",
      "applicable": true,
      "evidence_facts": [
        "expected_formality_range=[70, 95]",
        "outfit_formality_avg=58"
      ],
      "is_blocker": true
    }
  ],
  "blockers_failed": ["A5"],
  "suggestions": [
    {
      "id": "sg_1",
      "fixes_check_ids": ["A3", "A5"],
      "action": {
        "type": "swap",
        "target_slot": "shoes",
        "from": "sneakers (formality=20)",
        "to": "loafers (formality≥65)"
      },
      "rationale_facts": [
        "event_type=interview expects shoes in [dress_shoes, loafers]",
        "current shoes formality=20, swapping to loafers raises avg formality from 58 to 73"
      ],
      "expected_overall_delta": 18,
      "removes_blocker": true
    }
  ],
  "explanation": "면접 기대 포멀니스(70~95) 대비 평균이 58점이라 핵심 미스 1건이 있습니다. 신발만 로퍼로 교체하면 평균 73점으로 올라가 핵심 미스가 해소됩니다."
}
```

## 5. 체크 항목 정의 (총 17개, 5 그룹)

> **모든 체크는 결정적 함수 (`backend/app/scoring/checks/`)와 1:1 대응**한다.

### Group A: Dresscode 충족 (6 checks)
| ID | 라벨 | Pass 조건 | Blocker |
|---|---|---|---|
| A1 | top_in_expected_categories | `outfit.top.category ∈ context.dress_code.expected_categories.top` | no |
| A2 | bottom_in_expected_categories | bottom 카테고리 ∈ expected.bottom | no |
| A3 | shoes_in_expected_categories | shoes 카테고리 ∈ expected.shoes | no |
| A4 | outer_present_when_required | thermal_band ∈ {very_cold, cold} → outer 슬롯 존재 (else N/A) | **yes** |
| A5 | formality_avg_in_expected_range | 평균 포멀니스 ∈ expected_formality_range | **yes** |
| A6 | no_avoid_tones | 의류 색상 중 avoid_tones 매칭 0개 | no |

### Group B: 일관성 (3 checks)
| ID | 라벨 | Pass 조건 | Blocker |
|---|---|---|---|
| B1 | formality_spread_under_threshold | top/bottom/shoes 포멀니스 표준편차 ≤ 15 | no |
| B2 | no_duplicate_top_categories | top 슬롯 1개 (Vision verifier와 중복이지만 안전장치) | no |
| B3 | required_slots_complete | top, bottom, shoes 모두 존재 | **yes** |

### Group C: 색상 (3 checks)
| ID | 라벨 | Pass 조건 | Blocker |
|---|---|---|---|
| C1 | top_bottom_contrast_adequate | ΔE2000(top.rgb, bottom.rgb) ∈ [10, 50] | no |
| C2 | not_too_many_strong_colors | HSV 채도 > 0.7인 의류 ≤ 1개 | no |
| C3 | tone_diversity_acceptable | HSV 명도 표준편차 ∈ [10, 60] | no |

### Group D: 환경 적합성 (3 checks)
| ID | 라벨 | Pass 조건 | Blocker |
|---|---|---|---|
| D1 | warmth_matches_thermal_band | `|outfit_warmth - expected_warmth(thermal_band)| ≤ 2` (룩업 테이블) | no |
| D2 | precipitation_protected_when_needed | precip_prob ≥ 0.3 → outer 존재 AND 소재 ≠ pure cotton (else N/A) | no |
| D3 | no_overheat_risk | thermal_band=hot일 때 outer 미착용 또는 보온지수 ≤ 2 (else N/A) | no |

### Group E: 신뢰도 메타 (2 checks)
| ID | 라벨 | Pass 조건 | Blocker |
|---|---|---|---|
| E1 | vision_avg_confidence_adequate | `mean(g.confidence for g in garments) ≥ 0.6` | no |
| E2 | dresscode_resolution_confident | tier == tier1 OR (tier2 AND extraction_confidence ≥ 0.7) | no |

### 5.1 N/A (not_applicable) 처리
- A4, D2, D3은 환경 조건에 따라 평가 자체가 무의미할 수 있음 → `applicable: false`
- N/A 체크는 분모/분자 모두에서 제외 (점수에 영향 없음)

### 5.2 보온지수 / 기대 보온 룩업 (D1)
의류별 보온지수 (`backend/app/scoring/thermal_index.csv`):
```
t_shirt=1, shirt=2, knit=4, hoodie=3,
jacket=5, blazer=4, coat=7, padding=9,
shorts=1, pants=3, jeans=3, slacks=3
```
thermal_band별 기대 보온:
```
very_cold=14, cold=10, cool=7, mild=5, warm=3, hot=1
```

### 5.3 색상 룩업 (A6, C2, C3)
- avoid_tones 매칭은 RGB → 한글 색상 라벨 룩업 후 `context.dress_code.color_guidance.avoid_tones` 와 set intersection.
- HSV 변환은 OpenCV 표준 (H 0-179, S 0-255, V 0-255)을 [0,1] 정규화.

## 6. 점수 산출

### 6.1 그룹별 pass rate
```
group_pass_rate(g) = passed(g) / applicable(g)
```
applicable(g) = 0 인 그룹은 평균 산출에서 제외.

### 6.2 종합 점수
```
raw_score = mean(group_pass_rate(g) for g in groups) * 100
```

### 6.3 Blocker Cap
```
blockers_failed = [c for c in blocker_checks if c.result == "fail"]
if len(blockers_failed) >= 1:
    overall = min(raw_score, 50)
    cap_applied = "blocker_cap_50"
else:
    overall = raw_score
    cap_applied = null
```

블로커 1개라도 실패하면 종합이 50을 넘을 수 없다. 안전장치.

### 6.4 점수 분포 가이드
| overall | 의미 |
|---|---|
| 90~100 | 거의 모든 체크 통과 |
| 70~89 | 사소한 미스 1~2건 |
| 50~69 | 의미 있는 미스 다수, 또는 비-블로커 미스 많음 |
| ≤ 50 | 블로커 실패 (cap 적용) |

## 7. 제안 생성 (Failed-check 1:1 매핑)

### 7.1 알고리즘
```
failed = [c for c in checks if c.applicable and c.result == "fail"]
candidates = []
for check in failed:
    action = check.fix_template(outfit, context)  # 각 체크가 자기 fix를 정의
    simulated = simulate(outfit, context, action)
    delta = simulated.overall - current.overall
    if delta >= 2:
        candidates.append((check, action, delta))

# blocker fix는 우선순위 boost
candidates.sort(key=lambda x: (x[0].is_blocker, x[2]), reverse=True)
top3 = candidates[:3]
```

### 7.2 액션 어휘 (고정 4종)
| action | 설명 |
|---|---|
| `swap` | 한 슬롯의 의류를 다른 카테고리로 교체 |
| `add` | 누락된 슬롯에 의류 추가 (예: outer 추가) |
| `remove` | 과한 의류 제거 (예: 더운 날 jacket 제거) |
| `recolor` | 색상 톤 변경 |

### 7.3 fix_template 예 (체크가 자기 fix를 들고 있음)
```python
class A3_ShoesInExpectedCategories(Check):
    id = "A3"
    group = "dresscode"
    is_blocker = False

    def is_applicable(self, outfit, context):
        return outfit.shoes is not None and context.dress_code.expected_categories.shoes

    def evaluate(self, outfit, context):
        return outfit.shoes.category in context.dress_code.expected_categories.shoes

    def evidence_facts(self, outfit, context):
        return [
            f"event_type={context.dress_code.event_type} expects shoes in {context.dress_code.expected_categories.shoes}",
            f"current shoes category={outfit.shoes.category}"
        ]

    def fix_template(self, outfit, context):
        target = context.dress_code.expected_categories.shoes[0]
        return Action(type="swap", target_slot="shoes",
                      from_=outfit.shoes.category, to=target)
```

### 7.4 중복 액션 병합
- 같은 슬롯·같은 액션 타입의 후보가 여러 체크에서 나오면 1개로 병합 (`fixes_check_ids`에 다중 ID).
- 예: A3 fail + A5 fail이 모두 "신발 swap"으로 해결되면 1개 제안에 둘 다 포함.

### 7.5 폐기 룰
- `expected_overall_delta < +2` → 폐기
- 시뮬레이션 후 다른 체크를 fail로 만들면 폐기 (역효과 방지)
- 모든 후보 폐기 시 `suggestions: []` + "현재 착장에 큰 미스는 없습니다" 메시지

## 8. 시뮬레이션 (Simulator)

```python
def simulate(outfit, context, action):
    new_outfit = apply_action(outfit, action)
    new_score = compute_score(new_outfit, context)  # 모든 체크 재실행
    return new_score
```

순수 함수, 비용 ≈ 점수 함수 1회분 (< 5ms).

### 8.1 apply_action 룰
- `swap(slot, to_category)` → outfit.{slot}.category = to_category, formality_label = canonical lookup, primary_color = "neutral default"
- `add(slot, category)` → outfit.{slot} = canonical default
- `remove(slot)` → outfit.{slot} = None
- `recolor(slot, target_tone)` → primary_color → target_tone의 대표 RGB

apply_action은 가상 의류를 만들기 때문에 confidence는 0.7로 강제 (실제 입력보다 약간 낮게).

## 9. LLM Narrator (자연어화)

### 9.1 호출
- 입력: `score`, `failed_checks`, `top3_suggestions` (모두 결정적 산출물)
- 출력 schema:
  ```json
  {
    "explanation": "string (≤ 200자)",
    "suggestions_user_text": [
      {"id": "sg_1", "user_facing_text": "..."}
    ]
  }
  ```
- temperature=0, JSON 강제

### 9.2 프롬프트 제약
```
[SYSTEM]
You receive a deterministic outfit evaluation: scores, failed checks
(with evidence facts), and pre-computed suggestions (with actions and
expected deltas).

Your job: phrase explanations and suggestion texts in Korean using ONLY
the provided facts and numbers. Do NOT invent numbers, do NOT add
aesthetic judgments.

FORBIDDEN words: 매력, 호감, 인상, 성격, 어울리는 사람, 멋지, 예쁘,
세련, 촌스러, 신뢰감.

ALLOWED: cite numbers from facts, name actions, mention check IDs.
```

### 9.3 후처리 검증
- 출력 텍스트에 금지 단어 정규식 매칭 → 위반 시 1회 재시도 후 fallback (룰 기반 템플릿)
- 숫자가 facts에 없는 값을 인용했는지 검증 (간단한 숫자 매칭)

## 10. LangGraph Sub-graph 구조

본 Agent는 **결정적 노드 4개 + LLM 노드 1개**로 구성된 직선 그래프다. 분기는 "narrator 안전 필터 실패 시 재시도"의 single back-edge 만 존재.

### 10.1 RecommendationState

```python
class RecommendationState(BaseModel):
    # 입력
    outfit: VisionResponse
    context: ContextResponse

    # 산출물
    checks: list[CheckResult] = []
    score: Optional[Score] = None
    candidates: list[SuggestionCandidate] = []
    top3: list[SuggestionCandidate] = []

    # Narrator
    narration: Optional[Narration] = None
    narrator_retries: int = 0
    narrator_violations: list[str] = []

    # 최종
    response: Optional[RecommendationResponse] = None
```

### 10.2 그래프 정의

```python
from langgraph.graph import StateGraph, END

def build_recommendation_graph():
    g = StateGraph(RecommendationState)

    g.add_node("evaluate_checks", node_evaluate_checks)         # 결정적
    g.add_node("compute_score", node_compute_score)             # 결정적
    g.add_node("generate_candidates", node_generate_candidates) # 결정적
    g.add_node("simulate_and_filter", node_simulate_and_filter) # 결정적
    g.add_node("narrate", node_narrate)                         # LLM
    g.add_node("safety_filter", node_safety_filter)             # 결정적
    g.add_node("pack_response", node_pack_response)             # 결정적

    g.set_entry_point("evaluate_checks")
    g.add_edge("evaluate_checks", "compute_score")
    g.add_edge("compute_score", "generate_candidates")
    g.add_edge("generate_candidates", "simulate_and_filter")
    g.add_edge("simulate_and_filter", "narrate")
    g.add_edge("narrate", "safety_filter")

    # 안전 필터 분기: 위반 시 재시도 1회, 그래도 실패면 fallback 템플릿
    g.add_conditional_edges(
        "safety_filter",
        decide_after_safety,
        {
            "ok": "pack_response",
            "retry": "narrate",        # 1회 재시도
            "fallback": "pack_response",  # rule-template 사용
        }
    )

    g.add_edge("pack_response", END)
    return g.compile()

recommendation_subgraph = build_recommendation_graph()
```

### 10.3 분기 함수

```python
def decide_after_safety(state: RecommendationState) -> str:
    if not state.narrator_violations:
        return "ok"
    if state.narrator_retries < 1:
        state.narrator_retries += 1
        return "retry"
    # fallback: 룰 기반 템플릿으로 narration 생성
    state.narration = rule_template_narration(state.score, state.top3)
    return "fallback"
```

### 10.4 노드 책임

| 노드 | 종류 | 책임 |
|---|---|---|
| `evaluate_checks` | 결정적 | 17개 Check 클래스 실행 → CheckResult[] |
| `compute_score` | 결정적 | 그룹별 pass rate + blocker cap → Score |
| `generate_candidates` | 결정적 | failed check의 fix_template → action 후보 |
| `simulate_and_filter` | 결정적 | apply_action → 재평가 → delta ≥ +2, 역효과 없음 필터 → top3 |
| `narrate` | LLM (t=0) | facts/숫자만 인용해 한국어 자연어 생성 |
| `safety_filter` | 결정적 | 금지 단어 정규식 + 인용 숫자 검증 |
| `pack_response` | 결정적 | RecommendationResponse 패키징 |

### 10.5 Super-graph 노출

```python
# backend/app/agents/recommendation/__init__.py
from .graph import recommendation_subgraph

__all__ = ["recommendation_subgraph"]
```

### 10.6 시뮬레이션 endpoint와의 공유

`POST /v1/sessions/{id}/simulate` 는 그래프 전체가 아니라 다음 3 노드만 재실행:
`evaluate_checks` → `compute_score` → `pack_response_simulate`
LLM 미사용, 결정적, < 100ms.

## 11. 테스트 전략

### 11.1 체크 단위 테스트
- 17개 체크 함수 각각 ≥ 4개 케이스 (pass / fail / N/A / 경계값)
- 골든 입력 → 골든 결과 fixture로 회귀 검증

### 11.2 점수 산출 테스트
- 모든 체크 pass → 100점
- 한 그룹 모두 fail, 나머지 pass → 그룹 평균 ≈ 80
- 블로커 1개 실패 → 종합 ≤ 50 (cap 검증)

### 11.3 제안 생성 테스트
- failed check 1개 → 1개 제안 (단순 케이스)
- failed checks가 같은 fix로 해결 → 병합되어 1개 제안
- 시뮬레이션 후 다른 체크 fail 발생 → 폐기

### 11.4 결정성
- 동일 (outfit, context) 입력 → checks/score 100% 동일

### 11.5 LLM 안전성
- Narrator 출력에서 금지 단어 → 자동 재시도 → 자동 fallback (룰 템플릿)
- 위반 0건 (CI gating)

### 11.6 Agentic 동작
- step 카운트 측정: check eval(N=17) → score → simulate(N=후보 수) → narrate
- 시뮬레이션 정합성: 적용 후 실제 재계산 점수가 expected_delta와 ±1 이내

## 12. 성능 목표

| 지표 | 목표 |
|---|---|
| 점수 계산 latency (체크 17개 + 점수) | ≤ 30ms |
| 시뮬레이션 latency (제안 후보 평균 5개) | ≤ 50ms |
| LLM Narrator latency P95 | ≤ 2.5s |
| 시뮬레이션 정합성 | ≥ 99% (delta 오차 ≤ 1점) |
| 금지 단어 검출률 | 100% |

## 13. 마일스톤

| 주차 | 산출물 |
|---|---|
| 1주차 | Check Registry 골격 + Group A,B 9개 체크 + 점수 산출 + 골든 5케이스 |
| 2주차 | Group C,D,E 8개 체크 + blocker cap + simulator + 제안 생성기 |
| 3주차 | LLM Narrator + 안전 필터 + 통합 테스트 + 시나리오 5개 |

## 14. 다른 역할과의 인터페이스

- **Vision Agent**: garment.confidence, garment.formality_label 직접 사용. 색상 RGB는 OpenCV 측정값(결정적).
- **Context Agent**: dress_code의 expected_categories, expected_formality_range, color_guidance, tier, extraction_confidence 사용.
- **Frontend**: `checks` 배열을 그룹별 헤더로 묶어 체크리스트 UI로 렌더링. failed blocker는 빨간 배지. `suggestions[].fixes_check_ids` 로 체크 → 제안 매핑 표시.
- **Backend**: 시뮬레이션 endpoint(`POST /v1/sessions/{id}/simulate`)는 본 Agent의 simulate 함수를 직접 호출 (LLM 미사용, < 100ms).

## 15. 정직성 노트

- "차원별 0~100 점수"는 본 spec에서 폐기되었다. 모든 평가는 binary check.
- 가중치 튜닝이 사라졌다 — 모든 체크는 그룹 안에서 동등.
- 점수 변동의 모든 원인은 정확히 N개의 failed check로 설명된다.
- 이 단순함이 본 프로젝트의 정량화·재현성·설명력 원칙과 가장 잘 맞다.
