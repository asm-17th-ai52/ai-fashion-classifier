# 04. Recommendation Agent — 사양

> 담당자: AI 개발 #3
> 책임: Vision 출력 + Context 출력 → **정량 점수 + 설명 가능한 개선 제안** 산출

## 1. 책임

1. 8개 정량 차원에 대한 sub-score 계산 (결정적, 순수 함수)
2. 가중합으로 종합 점수 산출
3. 점수가 가장 낮은 차원을 우선으로 1~3개 개선 제안 생성
4. 각 제안은 "적용 시 예상 점수 증가량" 포함
5. LLM은 **숫자 결과를 자연어로 포장**하는 역할만 수행

## 2. 비-책임 (명시적 금지)

| 금지 항목 | 이유 |
|---|---|
| 점수를 LLM에게 직접 산출시키기 | 재현성/검증성 파괴 |
| "이 옷이 매력적입니다" 류 출력 | 주관적 평가 |
| "이성에게 호감", "신뢰감" 등 인상 평가 | 본 프로젝트 명시적 제외 영역 |
| 구매 추천 / 가격 정보 | MVP 범위 외 |
| 사용자 외모 평가 | 윤리 위험 |
| 의류 외 영역(메이크업, 헤어 등) | 범위 외 |

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
  "scores": {
    "overall": 71.4,
    "dimensions": {
      "formality_match": 62.0,
      "formality_consistency": 78.0,
      "thermal_fit": 84.0,
      "precipitation_readiness": 70.0,
      "color_contrast": 88.0,
      "tone_balance": 65.0,
      "dresscode_alignment": 60.0,
      "category_completeness": 90.0
    },
    "weights": {
      "formality_match": 0.20,
      "formality_consistency": 0.10,
      "thermal_fit": 0.15,
      "precipitation_readiness": 0.10,
      "color_contrast": 0.10,
      "tone_balance": 0.10,
      "dresscode_alignment": 0.20,
      "category_completeness": 0.05
    }
  },
  "weak_dimensions": ["dresscode_alignment", "formality_match"],
  "suggestions": [
    {
      "id": "sg_1",
      "target_dimension": "dresscode_alignment",
      "action": "swap",
      "target_slot": "shoes",
      "from": "sneakers (formality=20)",
      "to": "loafers or dress_shoes (formality≥60)",
      "rationale_facts": [
        "event_type=interview expects shoes formality 70-95",
        "current shoes formality_label=casual (20)"
      ],
      "expected_overall_delta": 6.5
    }
  ],
  "explanation": "면접(드레스코드 70~95) 대비 신발 포멀니스가 20점으로 격차가 큽니다. 신발만 로퍼로 교체 시 종합 점수가 약 +6.5점 증가합니다."
}
```

## 5. 점수 산출 — 결정적 룰

> **이 절은 코드(`backend/app/scoring/`)와 1:1 대응한다. LLM은 이 계산에 관여하지 않는다.**

### 5.1 formality_match (0~100)
- formality_label → 점수 매핑:
  ```
  casual=20, smart_casual=45, business_casual=65,
  business_formal=85, formal=95
  ```
- 의류 평균 포멀니스 = `mean(formality_score(g) for g in garments if g.slot in [top, bottom, outer, shoes])`
- `expected = mean(context.dress_code.expected_formality_range)`
- `match = 100 - 1.5 * |outfit_avg - expected|` (clamp 0~100)

### 5.2 formality_consistency (0~100)
- `var = variance(formality_score(g) for g in [top, bottom, shoes])`
- 표준편차 ≤ 5: 100점, ≥ 25: 0점, 선형 보간

### 5.3 thermal_fit (0~100)
- 의류별 보온지수(룩업 테이블 `thermal_index.csv`):
  ```
  t_shirt=1, shirt=2, knit=4, hoodie=3,
  jacket=5, blazer=4, coat=7, padding=9,
  shorts=1, pants=3, jeans=3, slacks=3
  ```
- `outfit_warmth = sum(thermal_index)` (없는 카테고리 0)
- `expected_warmth(thermal_band)`:
  ```
  very_cold=14, cold=10, cool=7, mild=5, warm=3, hot=1
  ```
- `score = 100 - 8 * |outfit_warmth - expected_warmth|` (clamp)

### 5.4 precipitation_readiness (0~100)
- `precip_score`:
  ```
  precip_prob < 0.3: 100 (위험 없음)
  precip_prob ≥ 0.3:
    - outer in {coat, padding, jacket} AND material != "cotton": 90
    - outer 있음 (그 외): 60
    - outer 없음: 30
  ```
- 우산은 입력에 없으므로 의류만으로 평가.

### 5.5 color_contrast (0~100)
- 상의·하의 dominant RGB → CIELAB 변환
- ΔE2000 계산
- 점수 매핑:
  ```
  ΔE < 5: 30 (단조)
  5 ≤ ΔE < 15: 60
  15 ≤ ΔE < 35: 100 (적정 대비)
  35 ≤ ΔE < 55: 75
  ΔE ≥ 55: 50 (과도)
  ```

### 5.6 tone_balance (0~100)
- 모든 의류 dominant RGB → HSV 변환
- 채도(S) 표준편차, 명도(V) 표준편차 계산
- `score = 100 - 1.2 * (S_std + V_std)` (clamp)

### 5.7 dresscode_alignment (0~100)
- context.dress_code.expected_categories와 매칭
- slot별: 의류 카테고리가 expected list에 있으면 100, 아니면 30
- 평균
- 추가 페널티: color_guidance.avoid_tones 위반 시 -20

### 5.8 category_completeness (0~100)
- event_type별 필수 슬롯 정의:
  ```
  interview: [top, bottom, shoes]
  business_meeting: [top, bottom, shoes]
  outdoor_activity (cold/very_cold): [top, bottom, shoes, outer]
  general: [top, bottom, shoes]
  ```
- 모든 필수 슬롯 존재 시 100, 누락 1개당 -25

### 5.9 overall
- `overall = sum(weight_i * score_i)` — 가중치는 출력 JSON에 명시.
- weights는 `event_type` 별로 다르게 적용 (예: interview는 dresscode_alignment 가중치 0.30):

| event_type | formality_match | dresscode_alignment | thermal_fit | 기타 |
|---|---|---|---|---|
| interview | 0.20 | **0.30** | 0.15 | 분배 |
| outdoor_activity | 0.10 | 0.10 | **0.30** | 분배 |
| office_daily | 0.15 | 0.15 | 0.15 | 균등 |

## 6. 제안 생성 (Suggestion Generation)

### 6.1 알고리즘 (결정적 + LLM 자연어)

```
1. weak_dimensions = bottom 2 dimensions by score (단, score ≥ 90인 차원은 제외)
2. for each weak dim:
     candidate_actions = rule_based_actions(dim, outfit, context)
3. for each action:
     simulate new outfit → recompute overall → expected_delta
4. top-3 actions by expected_delta → LLM 자연어화 호출
```

### 6.2 LLM 호출 (자연어화 only)
- 입력: 차원별 점수 + 룰 기반 action 리스트 + facts
- 출력 schema:
  ```json
  {
    "suggestions": [
      {"id": "...", "target_dimension": "...",
       "rationale_facts": ["...", "..."],
       "user_facing_text": "..."}
    ]
  }
  ```
- 프롬프트 제약:
  - "주어진 facts와 숫자만 사용"
  - "사용자 외모, 매력, 인상에 대한 언급 금지"
  - "숫자 점수는 facts에 있는 값만 인용"

### 6.3 Action Vocabulary (고정)
| action | 설명 |
|---|---|
| `swap` | 한 슬롯의 의류를 다른 카테고리로 교체 |
| `add` | 누락된 슬롯에 의류 추가 (예: outer 추가) |
| `remove` | 과한 의류 제거 (예: 더운 날 jacket 제거) |
| `recolor` | 색상 톤 변경 |

LLM은 이 4개 외 action을 만들 수 없다.

## 7. 검증 (Self-Consistency Check)

- 각 제안은 시뮬레이션을 거쳐 `expected_overall_delta ≥ +2.0` 인 것만 채택.
- 시뮬레이션 결과가 음수이면 제안 자동 폐기.
- 모든 제안이 폐기되면 `suggestions: []` 반환 + "현재 착장이 적정 범위입니다" 메시지.

## 8. 외부 인터페이스

```python
# backend/app/agents/recommendation/agent.py
async def score_and_suggest(
    outfit: VisionResponse,
    context: ContextResponse,
) -> RecommendationResponse:
    scores = compute_scores(outfit, context)         # 결정적
    weak = pick_weak_dims(scores)                    # 결정적
    actions = generate_actions(outfit, context, weak)# 결정적
    actions = simulate_and_filter(actions, outfit, context)  # 결정적
    suggestions = await llm_narrate(scores, actions) # LLM (자연어화)
    return RecommendationResponse(scores=scores, suggestions=suggestions, ...)
```

## 9. 테스트 전략

### 9.1 점수 함수 단위 테스트
- 8개 차원 함수 각각 ≥ 5개 케이스 (경계값 + 정상)
- 골든 input → 골든 score 검증

### 9.2 결정성
- 동일 (outfit, context) 입력 → scores 100% 동일 (LLM 미관여)

### 9.3 시뮬레이션 검증
- 제안 적용 후 재계산 점수 ≥ 원본 점수 + expected_delta - 1.0 (오차 1점 허용)

### 9.4 LLM 안전성
- 제안 텍스트에서 금지 단어 필터: "매력", "호감", "예쁘", "잘생", "성격", "인상"
- 위반 시 자동 재시도

## 10. 성능 목표

| 지표 | 목표 |
|---|---|
| 점수 계산 latency | ≤ 50ms (LLM 제외) |
| LLM narrate latency P95 | ≤ 2.5s |
| 제안 시뮬레이션 정합성 | ≥ 95% (delta 오차 ≤ 1점) |
| 금지 단어 검출률 | 100% (자동 필터) |

## 11. 마일스톤

| 주차 | 산출물 |
|---|---|
| 1주차 | thermal_index 테이블 + formality 매핑 + 6개 차원 점수 함수 |
| 2주차 | 가중치 테이블 + action 생성기 + 시뮬레이터 |
| 3주차 | LLM 자연어화 + 안전성 필터 + 통합 테스트 |
