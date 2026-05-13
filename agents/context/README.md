# Context Agent

`asm-17th-ai52/ai-fashion-classifier` 의 **Context Agent** 구현 디렉터리.

## 역할

사용자가 입력한 일정(event_type, datetime)을 받아 **드레스코드 컨텍스트**를 생성한다.
Tier-1(사전 구축 정적 RAG, ~50ms)을 우선 시도하고, RAG match score 가 0.6 미만이거나
사용자 정의 event_type 인 경우 Tier-2(ReAct 기반 실시간 웹 리서치 + 동적 RAG)로 폴백한다.
출력은 정량 지표(formality range, expected_categories, color guidance) 로 정규화되어
Recommendation Agent 가 의류 평가 시 사용한다.

자세한 사양은 [`docs/specs/03-agent-context-spec.md`](../../docs/specs/03-agent-context-spec.md)
및 [`docs/specs/07-data-contracts.md`](../../docs/specs/07-data-contracts.md) §3 참조.

## PR 단계

본 디렉터리는 다음과 같이 점진적으로 채워진다.

| PR | 산출물 |
|---|---|
| PR-A | `state.py` (Pydantic 모델), `data/dresscode/static/*.md × 9` (정적 코퍼스) |
| PR-B | `embedder.py` + `tier1.py` (`tier1_retrieve` / `is_tier1_match` + 인라인 build CLI) + 사전 빌드 FAISS 인덱스 |
| PR-C | Tier-2 ReAct 도구 (`web_search`, `fetch_page`, `extract_facts`) |
| PR-D | Tier-2 합의(consensus) + 승격 큐 노드 |
| PR-E | LangGraph 조립 + `context_subgraph` export → backend selector 연결 |

> **참고**: `__init__.py` 는 PR-A 시점에 의도적으로 비어있다.
> `context_subgraph` 가 export 되지 않으므로,
> `api/app/agents_stub/__init__.py` 의 selector 는 PR-E 머지 전까지
> 기존 stub 으로 폴백한다 (회귀 위험 0).

## 설치

```bash
pip install -r agents/context/requirements.txt
```

PR-B 기준 의존성: `python-frontmatter`, `pydantic`, `sentence-transformers`,
`faiss-cpu`, `langchain-huggingface`, `langchain-community`. PR-C 에서 Tier-2 도구
관련 (`tavily-python`, `httpx`, `trafilatura` 등) 가 추가될 예정이다.

> 프로덕션 배포 시에는 backend 담당자가 동일 의존성을 `api/requirements.txt` 에도
> 반영해야 한다 (현 PR 범위 밖, PR-E 검토 시점에 합의 예정).

## 환경 변수

`.env.example` 참조. 본 Agent 는 다음 키를 사용한다.

| 키 | 용도 | 비고 |
|---|---|---|
| `TAVILY_API_KEY` | Tier-2 web search | PR-C 부터 사용 |
| `GOOGLE_API_KEY` | Tier-2 extract_facts (LLM structured output) | Vision Agent 가 이미 사용 중인 키 재사용. 루트 `.env.example` 에 정의됨. |

## 데이터

- 정적 RAG 코퍼스: `data/dresscode/static/*.md` (9개 event_type, YAML frontmatter + Korean body).
  - vocab 은 `agents/vision/tools/color_lookup.py` 의 `_COLOR_TABLE` 기준.
  - schema 는 `data/dresscode/static/README.md` 참조.
- 사전 빌드 FAISS 인덱스: `data/dresscode/faiss_index/` (PR-B 부터 repo 에 커밋)
- 인덱스 재빌드: `python -m agents.context.tier1 build` (인라인 CLI, `_build_index` 호출)

> FAISS 인덱스 빌드/로드 코드는 PR-B (`tier1.py`) 에서 추가됨.
