"""
Tier-1 정적 RAG: 사전 빌드된 FAISS 인덱스에서 드레스코드 문서를 검색한다.

설계 요점:
- 임베딩: ``embedder.build_embedder()`` (ko-sroberta-multitask, normalize=True)
- 인덱스: ``data/dresscode/faiss_index/`` 에 사전 빌드 + repo 커밋
- 거리: 기본 L2 (FAISS ``IndexFlatL2``).
  FAISS ``IndexFlatL2.search()`` 는 이미 **squared** L2 distance 를 반환하므로
  단위 정규화 임베딩에서 ``cos = 1 - L²/2`` 를 직접 적용한다 (``_l2_to_cosine``).
  반환 score 는 [-1, 1] (일반적으로 [0, 1]) cosine relevance.
  ※ langchain-community ``DistanceStrategy.MAX_INNER_PRODUCT`` + ``with_relevance_scores``
  는 본 모델/인덱스 조합에서 점수가 사실상 반전되어 나오는 known issue 가 있어 사용하지 않음.
- 임계값: 0.6 — spec ``docs/specs/03-agent-context-spec.md`` §5.2 / §6.1 그대로.

본 파일은 **순수 검색 함수**만 제공한다. LangGraph 노드 래핑(``node_tier1_retrieve``)은
PR-E 의 graph 조립 단계에서 ``ContextState`` 를 다루며 본 모듈을 호출한다.

사용:

.. code-block:: python

   from agents.context.tier1 import tier1_retrieve, is_tier1_match

   hits = tier1_retrieve("면접", k=3)
   if is_tier1_match([h["score"] for h in hits], event_type_is_custom=False):
       top = hits[0]
       # top["event_type"], top["score"], top["metadata"], top["doc"]

인덱스 재빌드:

.. code-block:: bash

   python -m agents.context.tier1 build
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS

from .embedder import build_embedder


# 정적 RAG 인덱스 + 코퍼스 위치는 본 패키지 내부에 고정.
_PACKAGE_DIR = Path(__file__).parent
INDEX_PATH = _PACKAGE_DIR / "data" / "dresscode" / "faiss_index"
STATIC_DIR = _PACKAGE_DIR / "data" / "dresscode" / "static"

# spec §5.2 / §6.1: match score 0.6 이상이면 Tier-1, 미만이면 Tier-2 폴백 검토.
THRESHOLD: float = 0.6


def _l2_to_cosine(faiss_l2_squared: float) -> float:
    """FAISS ``IndexFlatL2.search()`` 반환값을 cosine relevance score 로 환산.

    Important: FAISS ``IndexFlatL2.search()`` 는 이미 **squared** L2 distance 를 반환한다
    (`langchain_community.vectorstores.FAISS.similarity_search_with_score` 도 그 값을
    그대로 score 로 노출). 따라서 인자는 ``‖a-b‖²`` 라는 가정 하에 환산한다.

    수학:
        단위 정규화 임베딩에서 ``‖a-b‖² = 2 - 2·cos(a, b)`` 이므로
        ``cos = 1 - ‖a-b‖²/2``.

    경계값: 동일 벡터 시 cos=1, 직교 시 cos=0, 반대 방향 시 cos=-1.

    History: 초기 구현에서 ``** 2`` 를 한 번 더 적용하는 버그가 있었고 (사실상
    ``cos = 1 - L⁴/2``), 점수가 과대 평가되었다. 본 수정으로 manual IP 계산 결과와
    소수 4자리까지 일치한다.
    """
    return 1.0 - faiss_l2_squared / 2.0


@lru_cache(maxsize=1)
def _store() -> FAISS:
    """FAISS 인덱스를 lazy 로드 + 프로세스당 1회 캐싱한다.

    ``allow_dangerous_deserialization=True`` 는 langchain 의 pickle 기반 메타데이터
    역직렬화를 허용하는 플래그다. 인덱스는 본 repo 가 직접 빌드/커밋하므로 신뢰 OK.

    인덱스 파일이 없을 때 (예: 신규 환경, 인덱스 파일 누락) 는 즉시 actionable
    error 를 raise — pickle 디시리얼라이저의 모호한 stack trace 보다 빌드 명령
    안내가 훨씬 유용하다.
    """
    if not (INDEX_PATH / "index.faiss").exists() or not (INDEX_PATH / "index.pkl").exists():
        raise RuntimeError(
            f"FAISS index not found at {INDEX_PATH}. "
            f"Run: python -m agents.context.tier1 build"
        )
    emb = build_embedder()
    return FAISS.load_local(
        str(INDEX_PATH),
        emb,
        allow_dangerous_deserialization=True,
    )


def tier1_retrieve(query: str, k: int = 3) -> list[dict[str, Any]]:
    """쿼리에 대해 정적 RAG top-k 결과를 점수순으로 반환한다.

    Returns:
        list of dict with keys:
            - ``event_type``: frontmatter 의 슬러그 (예: ``"interview"``)
            - ``score``: cosine relevance ([-1, 1], 일반적으로 [0, 1]).
              값이 클수록 유사도가 높다.
            - ``metadata``: frontmatter dict 사본 (formality range, categories 등 포함)
            - ``doc``: 원본 langchain ``Document``
    """
    # similarity_search_with_score 는 FAISS IndexFlatL2 의 SQUARED L2 distance 를
    # 그대로 반환한다 (작을수록 유사). 정규화 임베딩에서 cos = 1 - L²/2 로 환산.
    hits = _store().similarity_search_with_score(query, k=k)
    return [
        {
            "event_type": doc.metadata["event_type"],
            "score": _l2_to_cosine(float(l2_squared)),
            "metadata": dict(doc.metadata),
            "doc": doc,
        }
        for doc, l2_squared in hits
    ]


def is_tier1_match(
    scores: list[float],
    event_type_is_custom: bool,
    threshold: float = THRESHOLD,
) -> bool:
    """Tier-1 결과 채택 가능 여부 판정 (순수 함수, state 없음).

    PR-E 의 ``decide_dresscode_tier`` 분기에서 본 헬퍼를 호출한다.

    Rules (spec §6.1):
    1. 사용자 정의 event_type 이면 무조건 Tier-2 검토 (False).
    2. scores 가 비어있으면 False.
    3. 최고 점수 ≥ threshold 면 True.
    """
    if event_type_is_custom:
        return False
    if not scores:
        return False
    return max(scores) >= threshold


# ---------------------------------------------------------------------------
# 인덱스 빌드 (CLI: ``python -m agents.context.tier1 build``)
# ---------------------------------------------------------------------------


def _build_page_content(meta: dict[str, Any], body: str) -> str:
    """임베딩 대상 텍스트를 구성.

    제목과 aliases (한국어 + 영문) 를 본문 앞에 prepend 해서 짧은 키워드 쿼리
    ("면접", "interview" 등) 도 강하게 매칭되게 한다. 빈도 가중을 위해 제목을 2회 반복.
    빈도 가중치는 ko-sroberta 토큰 분포 실험 결과 (Phase 2 캘리브레이션) 의 단순 적용.
    """
    title = body.strip().splitlines()[0].lstrip("# ").strip()
    aliases = meta.get("aliases", []) or []
    slug = meta.get("event_type", "")
    head = f"{title}\n{title}\n{slug} {' '.join(aliases)}\n"
    return f"{head}\n{body}"


def _load_corpus_documents() -> list:
    """``static/*.md`` 9 건을 langchain Document 리스트로 로드한다.

    빌드 타임 검증: ``event_type`` 키는 retrieve 결과 dict 의 식별자이므로
    누락 시 즉시 raise — pickle 시점에 묻혀버리지 않도록 명시적으로 막는다.
    """
    import frontmatter  # type: ignore[import-untyped]
    from langchain_core.documents import Document

    docs = []
    for path in sorted(STATIC_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        post = frontmatter.load(path)
        meta = dict(post.metadata)
        if "event_type" not in meta:
            raise ValueError(
                f"Corpus document {path.name} is missing required 'event_type' "
                f"frontmatter key — Tier-1 retrieve depends on this slug."
            )
        # `curated_at` 가 date 객체로 로드되어 FAISS 저장 시 직렬화 문제를 일으킬 수
        # 있어 ISO 문자열로 평탄화한다.
        if "curated_at" in meta and not isinstance(meta["curated_at"], str):
            meta["curated_at"] = str(meta["curated_at"])
        meta["source_path"] = path.name
        page_content = _build_page_content(meta, post.content)
        docs.append(Document(page_content=page_content, metadata=meta))
    return docs


def _build_index() -> None:
    """전체 코퍼스를 임베딩 → FAISS 인덱스로 직렬화 (in-place 갱신)."""
    docs = _load_corpus_documents()
    if not docs:
        raise RuntimeError(
            f"No markdown corpus found under {STATIC_DIR}. PR-A 코퍼스가 누락된 상태입니다."
        )
    emb = build_embedder()
    # 기본 L2 거리 사용 (``_l2_to_cosine`` 로 cosine 환산).
    vs = FAISS.from_documents(docs, emb)
    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(INDEX_PATH))
    print(f"Built FAISS index at {INDEX_PATH} with {len(docs)} docs")


def _usage_and_exit(code: int = 1) -> None:
    print("Usage: python -m agents.context.tier1 build")
    raise SystemExit(code)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        _build_index()
    else:
        _usage_and_exit()
