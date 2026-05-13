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

## 구성

| 파일/디렉터리 | 역할 |
|---|---|
| `state.py` | Pydantic 모델 (`ContextState`, `FetchedPage`, `ExtractedFacts`) |
| `data/dresscode/static/*.md` (9건) | 정적 코퍼스 (event_type 별 드레스코드 YAML + 본문) |
| `embedder.py` + `tier1.py` | Tier-1 FAISS RAG (`tier1_retrieve`, `is_tier1_match`, 인라인 build CLI) |
| `data/dresscode/faiss_index/` | 사전 빌드 FAISS 인덱스 (repo 에 커밋) |
| `tools/{web_search,fetch,youtube,whitelist,budget}.py` | Tier-2 ReAct 도구 (Tavily / httpx / trafilatura / youtube-transcript) + 도메인 화이트리스트 + 비용 카운터 |
| `nodes/{plan_query,extract_facts,consensus,tier1_retrieve_node,decide_tier,tier2_web_search,tier2_fetch_pages,pack_context,promotion}.py` | LangGraph 노드 + 분기 함수 |
| `prompts.py` | LLM 시스템/유저 프롬프트 (한국어) |
| `forbidden_terms.py` | §4.1 금지어 리스트 + NFC 정규화 헬퍼 |
| `graph.py` | LangGraph sub-graph 조립 (`build_context_graph`) |
| `adapter.py` | `context_subgraph` 어댑터 (super-graph 연결, 12s + 3s hard timeout) |
| `latency.py` | Tier-2 latency 상한 + start-marker 헬퍼 |

`__init__.py` 가 `context_subgraph` 를 lazy export (PEP 562) → backend selector 가 본
모듈 import 성공 시 stub 대신 실 Context Agent 로 라우팅한다.

## 설치

```bash
pip install -r agents/context/requirements.txt
```

의존성: `python-frontmatter`, `pydantic`, `sentence-transformers`, `faiss-cpu`,
`langchain-huggingface`, `langchain-community`, `google-genai`, `tavily-python`,
`httpx`, `trafilatura[all]`, `youtube-transcript-api`.

> 프로덕션 배포 시에는 backend 담당자가 동일 의존성을 `api/requirements.txt` 에도
> 반영해야 한다.

## 환경 변수

`.env.example` 참조. 본 Agent 는 다음 키를 사용한다.

| 키 | 용도 | 비고 |
|---|---|---|
| `TAVILY_API_KEY` | Tier-2 web search | Tavily 무료 1,000 credit/월 한도 보호 카운터 내장 |
| `GOOGLE_API_KEY` | Tier-2 extract_facts (LLM structured output) | Vision Agent 가 이미 사용 중인 키 재사용. 루트 `.env.example` 에 정의됨. |

## 데이터

- 정적 RAG 코퍼스: `data/dresscode/static/*.md` (9개 event_type, YAML frontmatter + Korean body).
  - vocab 은 `agents/vision/tools/color_lookup.py` 의 `_COLOR_TABLE` 기준.
  - schema 는 `data/dresscode/static/README.md` 참조.
- 사전 빌드 FAISS 인덱스: `data/dresscode/faiss_index/`
- 인덱스 재빌드: `python -m agents.context.tier1 build`
