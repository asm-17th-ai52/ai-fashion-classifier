# 07. Data Contracts — 단일 진실 소스

> 이 문서는 모든 역할이 공유하는 **JSON 스키마 / API 계약** 단일 진실 소스다.
> 변경 시 모든 역할 담당자에게 PR 리뷰가 강제된다 (CODEOWNERS).

## 1. 공통 enum

### 1.1 event_type
```typescript
// Tier-1 (사전 구축 RAG가 커버하는 표준 카테고리)
type StandardEventType =
  | "business_meeting"
  | "interview"
  | "presentation"
  | "casual_date"
  | "wedding_guest"
  | "office_daily"
  | "school_daily"
  | "outdoor_activity"
  | "general";

// 입력은 StandardEventType OR 자유 입력 문자열
// 자유 입력일 경우 event_type_is_custom = true 가 강제됨 → Tier-2 자동 트리거
type EventTypeInput = StandardEventType | string;
```

### 1.2 garment_slot
```typescript
type GarmentSlot = "top" | "bottom" | "outer" | "shoes" | "bag" | "watch";
```

### 1.3 formality_label
```typescript
type FormalityLabel =
  | "casual"          // 20
  | "smart_casual"    // 45
  | "business_casual" // 65
  | "business_formal" // 85
  | "formal";         // 95
```

### 1.4 thermal_band
```typescript
type ThermalBand = "very_cold" | "cold" | "cool" | "mild" | "warm" | "hot";
```

### 1.5 dimension
```typescript
type Dimension =
  | "formality_match"
  | "formality_consistency"
  | "thermal_fit"
  | "precipitation_readiness"
  | "color_contrast"
  | "tone_balance"
  | "dresscode_alignment"
  | "category_completeness";
```

### 1.6 action_type
```typescript
type SuggestionAction = "swap" | "add" | "remove" | "recolor";
```

### 1.7 dress_code_tier
```typescript
type DressCodeTier =
  | "tier1"             // 사전 구축 RAG 매칭 성공
  | "tier2_live"        // 실시간 웹 리서치 + 동적 RAG (ReAct)
  | "fallback_general"; // Tier-1, Tier-2 모두 실패 → general 카테고리
```

## 2. Vision Agent 출력 (VisionResponse)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["session_id", "person_detected", "image_quality", "garments", "warnings"],
  "properties": {
    "session_id": {"type": "string"},
    "person_detected": {"type": "boolean"},
    "image_quality": {
      "type": "object",
      "required": ["resolution_ok", "frontal", "occlusion_ratio"],
      "properties": {
        "resolution_ok": {"type": "boolean"},
        "frontal": {"type": "boolean"},
        "occlusion_ratio": {"type": "number", "minimum": 0, "maximum": 1}
      }
    },
    "garments": {
      "type": "array",
      "items": {"$ref": "#/$defs/Garment"}
    },
    "warnings": {"type": "array", "items": {"type": "string"}}
  },
  "$defs": {
    "Garment": {
      "type": "object",
      "required": ["slot", "category", "primary_color", "pattern", "formality_label", "confidence"],
      "properties": {
        "slot": {"enum": ["top", "bottom", "outer", "shoes", "bag", "watch"]},
        "category": {"type": "string"},
        "subcategory": {"type": "string"},
        "primary_color": {
          "type": "object",
          "required": ["rgb", "name"],
          "properties": {
            "rgb": {
              "type": "array",
              "items": {"type": "integer", "minimum": 0, "maximum": 255},
              "minItems": 3, "maxItems": 3
            },
            "name": {"type": "string"}
          }
        },
        "secondary_colors": {"type": "array"},
        "pattern": {"enum": ["solid", "stripe", "check", "dot", "graphic", "other"]},
        "estimated_material": {
          "enum": ["cotton", "wool", "synthetic", "denim", "leather", "knit", "unknown"]
        },
        "fit": {"enum": ["slim", "regular", "loose", "oversized", "unknown"]},
        "sleeve_length": {"enum": ["sleeveless", "short", "long", "n/a"]},
        "formality_label": {
          "enum": ["casual", "smart_casual", "business_casual", "business_formal", "formal"]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
      }
    }
  }
}
```

## 3. Context Agent 출력 (ContextResponse)

```json
{
  "type": "object",
  "required": ["session_id", "weather", "dress_code", "thermal_band", "warnings"],
  "properties": {
    "session_id": {"type": "string"},
    "weather": {
      "type": "object",
      "required": ["available"],
      "properties": {
        "available": {"type": "boolean"},
        "temperature_celsius": {"type": "number"},
        "feels_like_celsius": {"type": "number"},
        "precipitation_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "precipitation_intensity_mm_h": {"type": "number", "minimum": 0},
        "wind_speed_mps": {"type": "number", "minimum": 0},
        "humidity": {"type": "number", "minimum": 0, "maximum": 1},
        "is_outdoor_relevant": {"type": "boolean"}
      }
    },
    "dress_code": {
      "type": "object",
      "required": ["event_type", "tier", "rag_match_score", "expected_formality_range",
                   "expected_categories", "color_guidance", "extraction_confidence"],
      "properties": {
        "event_type": {"type": "string"},
        "tier": {
          "enum": ["tier1", "tier2_live", "fallback_general"]
        },
        "rag_match_score": {"type": "number", "minimum": 0, "maximum": 1},
        "expected_formality_range": {
          "type": "array",
          "items": {"type": "integer", "minimum": 0, "maximum": 100},
          "minItems": 2, "maxItems": 2
        },
        "expected_categories": {
          "type": "object",
          "properties": {
            "top": {"type": "array", "items": {"type": "string"}},
            "bottom": {"type": "array", "items": {"type": "string"}},
            "outer": {"type": "array", "items": {"type": "string"}},
            "shoes": {"type": "array", "items": {"type": "string"}}
          }
        },
        "color_guidance": {
          "type": "object",
          "properties": {
            "preferred_tones": {"type": "array"},
            "avoid_tones": {"type": "array"}
          }
        },
        "source_doc_ids": {"type": "array", "items": {"type": "string"}},
        "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence_quotes": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["url", "quote", "fetched_at"],
            "properties": {
              "url": {"type": "string", "format": "uri"},
              "quote": {"type": "string", "maxLength": 500},
              "fetched_at": {"type": "string", "format": "date-time"}
            }
          }
        },
        "live_research_meta": {
          "type": "object",
          "description": "tier == tier2_live 일 때만 포함",
          "properties": {
            "search_queries_used": {"type": "array", "items": {"type": "string"}},
            "sources_count": {"type": "integer", "minimum": 0},
            "react_steps": {"type": "integer", "minimum": 0, "maximum": 5},
            "latency_ms": {"type": "integer", "minimum": 0}
          }
        }
      }
    },
    "thermal_band": {
      "enum": ["very_cold", "cold", "cool", "mild", "warm", "hot"]
    },
    "warnings": {"type": "array"}
  }
}
```

## 4. Recommendation Agent 출력 (RecommendationResponse)

```json
{
  "type": "object",
  "required": ["session_id", "scores", "weak_dimensions", "suggestions", "explanation"],
  "properties": {
    "session_id": {"type": "string"},
    "scores": {
      "type": "object",
      "required": ["overall", "dimensions", "weights"],
      "properties": {
        "overall": {"type": "number", "minimum": 0, "maximum": 100},
        "dimensions": {
          "type": "object",
          "patternProperties": {
            "^(formality_match|formality_consistency|thermal_fit|precipitation_readiness|color_contrast|tone_balance|dresscode_alignment|category_completeness)$": {
              "type": "number", "minimum": 0, "maximum": 100
            }
          }
        },
        "weights": {
          "type": "object",
          "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    },
    "weak_dimensions": {"type": "array", "items": {"type": "string"}},
    "suggestions": {
      "type": "array",
      "maxItems": 3,
      "items": {"$ref": "#/$defs/Suggestion"}
    },
    "explanation": {"type": "string", "maxLength": 400}
  },
  "$defs": {
    "Suggestion": {
      "type": "object",
      "required": ["id", "target_dimension", "action", "rationale_facts", "expected_overall_delta"],
      "properties": {
        "id": {"type": "string"},
        "target_dimension": {"type": "string"},
        "action": {"enum": ["swap", "add", "remove", "recolor"]},
        "target_slot": {"enum": ["top", "bottom", "outer", "shoes"]},
        "from": {"type": "string"},
        "to": {"type": "string"},
        "rationale_facts": {
          "type": "array",
          "items": {"type": "string"},
          "minItems": 1
        },
        "expected_overall_delta": {"type": "number"}
      }
    }
  }
}
```

## 5. Backend API 계약

### 5.1 `POST /v1/sessions`

**Request (multipart/form-data):**
| 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|
| image | file | yes | jpeg/png, ≤ 10MB |
| event_type | string | yes | StandardEventType 또는 자유 입력 |
| event_type_is_custom | boolean | no (default false) | true 면 Tier-2 강제. 자유 입력 시 서버가 자동 true 처리 |
| event_datetime | string (ISO 8601) | yes | |
| city_code | string | yes | KR-SEOUL 등 |
| is_indoor | boolean | no (default false) | |
| allow_live_research | boolean | no (default true) | false 면 Tier-2 비활성, fallback_general 사용 |

**Response 200 — SessionResponse:**
```json
{
  "session_id": "string",
  "outfit": "VisionResponse",
  "context": "ContextResponse",
  "recommendation": "RecommendationResponse",
  "meta": {
    "latency_ms": "integer",
    "agent_latencies_ms": {
      "vision": "integer",
      "context": "integer",
      "context_tier2": "integer (optional, Tier-2 트리거 시에만)",
      "recommendation": "integer"
    },
    "cache_hits": ["string"],
    "tier2_triggered": "boolean"
  }
}
```

### 5.2 `GET /v1/sessions/{session_id}`
- Response: SessionResponse (캐시)
- 404 if expired (>24h) or not found

### 5.3 `POST /v1/sessions/{session_id}/simulate`

**Request:**
```json
{ "applied_suggestion_ids": ["sg_1", "sg_3"] }
```

**Response 200:**
```json
{
  "session_id": "string",
  "original_overall": 71.4,
  "simulated_overall": 78.9,
  "delta": 7.5,
  "applied": [
    {"id": "sg_1", "individual_delta": 5.5},
    {"id": "sg_3", "individual_delta": 2.0}
  ],
  "simulated_dimensions": { ... }
}
```

### 5.4 에러 응답 (공통)
```json
{
  "error": {
    "code": "string",
    "message": "string (사용자 친화적, 한국어)",
    "details": { /* 선택 */ }
  }
}
```

| code | HTTP | 의미 |
|---|---|---|
| `image_too_large` | 413 | 이미지 크기 초과 |
| `image_invalid` | 400 | 이미지 디코드 실패 |
| `person_not_detected` | 400 | 사람 미검출 |
| `validation_error` | 422 | 입력 검증 실패 |
| `rate_limited` | 429 | 레이트 리밋 |
| `agent_failed` | 502 | Vision/Recommendation 실패 |
| `weather_unavailable` | 200 | (에러 아님, 정상 응답에 플래그) |

## 6. 변경 관리 규칙

1. 본 문서가 schema 단일 진실 소스다.
2. Backend는 Pydantic 모델, Frontend는 Zod 스키마로 본 문서 기반 자동 생성을 유지한다 (수기 동기화 금지).
3. 필드 추가는 backward-compatible 하게 (선택 필드).
4. enum 변경은 모든 담당자에게 PR 리뷰 강제.
5. 차원 추가/제거는 Recommendation Agent + Frontend 라벨 + 가중치 테이블이 동일 PR에 포함되어야 머지 가능.
