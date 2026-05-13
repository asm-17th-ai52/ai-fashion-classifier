# 정적 드레스코드 코퍼스

Context Agent Tier-1 정적 RAG 의 원천 문서들. 각 파일은 1개 `event_type` 에 대응한다.

## 파일 목록

| 파일 | event_type | 격식 범위 |
|---|---|---|
| `interview.md` | interview | 70–95 |
| `business_meeting.md` | business_meeting | 65–90 |
| `presentation.md` | presentation | 65–90 |
| `wedding_guest.md` | wedding_guest | 70–95 |
| `office_daily.md` | office_daily | 55–80 |
| `casual_date.md` | casual_date | 40–70 |
| `school_daily.md` | school_daily | 20–55 |
| `outdoor_activity.md` | outdoor_activity | 10–45 |
| `general.md` | general (fallback) | 30–80 |

`event_type` 값은 `api/app/schemas/enums.py::StandardEventType` 의 enum 과 1:1 대응한다.

## 스키마

각 파일은 YAML frontmatter + Korean 본문(200~400자) 으로 구성된다.

```yaml
---
event_type: <slug>                            # 위 표의 9개 슬러그 중 하나
expected_formality_range: [<min>, <max>]      # 0-100, 정확히 길이 2, min ≤ max
expected_categories:
  top:    [<한글 카테고리>]                   # 셔츠 / 블라우스 / 니트 / 티셔츠 / 후드티 / 드레스
  bottom: [<한글 카테고리>]                   # 슬랙스 / 치마 / 치노 / 청바지 / 반바지
  outer:  [<한글 카테고리>]                   # 블레이저 / 자켓 / 가디건
  shoes:  [<한글 카테고리>]                   # 구두 / 로퍼 / 스니커즈
color_guidance:
  preferred_tones: [<한글 색상>]              # color_lookup.py 의 _COLOR_TABLE 한글명
  avoid_tones:     [<한글 색상>]              # 같은 vocab
source: hand_curated                          # 'hand_curated' | 'tier2_promoted'
curated_at: 2026-05-12                        # ISO 날짜
aliases: [<한국어/영어 동의어>]               # 사용자 입력 정규화 / 검색 매칭 용
---

# <한글 제목> (<English>) 드레스코드

<본문 — 200~400자 한국어, 격식·표준 조합·금기·신발·색상·업종/상황별 변형 등을 키워드 위주로 서술>
```

## Vocab 출처

- **색상**: `agents/vision/tools/color_lookup.py::_COLOR_TABLE` 의 한글 색상명만 사용.
  Vision Agent 가 픽셀 RGB → 한글 색상명으로 정규화한 결과와 정확히 일치해야
  Recommendation Agent 가 `color_guidance.preferred_tones ∩ garment.primary_color.name` 을
  결정적으로 비교할 수 있다.
- **카테고리**: 위 스키마 표의 한글 카테고리 (Vision Agent 출력 기준, 2026-05-10 확인).
  영어 카테고리 (`shirt`, `slacks`, …) 를 섞어 쓰지 않는다.

## 업데이트 정책

| source | 절차 |
|---|---|
| `hand_curated` | 사람이 직접 작성. spec §5.1 의 schema 만 만족하면 됨. |
| `tier2_promoted` | Tier-2 ReAct 가 생성한 임시 문서가 `data/dresscode/promotion_queue.jsonl` 에 적재됨. 팀원 검수(주 1회) 후 PR 로 본 디렉터리에 편입. spec §8 참조. |

자동 승격은 금지된다 (LLM 환각이 정적 RAG 에 누적되면 모든 후속 사용자에게 영향). 큐 → 본 디렉터리 이동은 항상 사람 PR 을 거친다.

## FAISS 인덱싱

본 디렉터리의 모든 `*.md` 본문 + frontmatter 의 `aliases` 가 임베딩 대상이 된다.

```bash
python -m agents.context.tier1 build
```

빌드된 인덱스는 `../faiss_index/{index.faiss, index.pkl}` 에 저장된다.
