"""
Context Agent 테스트 공용 fixture.

``slow`` 마커가 없는 테스트는 모킹된 임베더만 사용해야 하며, 모델 다운로드
(~440MB) / 디스크 인덱스 로드 / 네트워크 호출 전부 차단된다.

`pytest agents/context/tests/test_tier1.py` (default) — fast unit only.
`pytest agents/context/tests/test_tier1.py -m slow` — integration only.
`pytest agents/context/tests/test_tier1.py -m "not slow"` — fast unit only (명시).
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

# ``agents/context/state.py`` 와 어댑터/노드들이 ``from app.schemas...`` 로 import.
# pytest 를 ``PYTHONPATH`` 없이 (예: 단일 명령 ``pytest agents/context/tests/``) 돌렸을 때도
# 그 import 가 성공하도록 ``api/`` 디렉토리를 sys.path 에 보강한다.
# 본 파일 경로: ``agents/context/tests/conftest.py`` → parents[2] = repo root → / "api".
_API_ROOT = pathlib.Path(__file__).resolve().parents[2] / "api"
if _API_ROOT.is_dir():
    api_str = str(_API_ROOT)
    if api_str not in sys.path:
        sys.path.insert(0, api_str)

import pytest
from langchain_core.embeddings import Embeddings


def pytest_configure(config: pytest.Config) -> None:
    """`slow` 마커 등록 (CI에서 unknown-mark 경고 방지)."""
    config.addinivalue_line(
        "markers",
        "slow: integration tests requiring real model + on-disk FAISS index",
    )


@pytest.fixture(scope="session")
def corpus_dir() -> pathlib.Path:
    """`agents/context/data/dresscode/static/` 절대 경로."""
    return pathlib.Path(__file__).resolve().parents[1] / "data" / "dresscode" / "static"


@pytest.fixture(scope="session")
def corpus_paths(corpus_dir: pathlib.Path) -> list[pathlib.Path]:
    """README 를 제외한 9 개 코퍼스 마크다운 경로."""
    return sorted(p for p in corpus_dir.glob("*.md") if p.name != "README.md")


class _DummyEmbeddings(Embeddings):
    """결정적 더미 임베더: event_type 슬러그 9 개 + 커스텀 토큰을 차원으로 갖는
    frequency 기반 정규화 벡터.

    각 슬러그는 해당 코퍼스의 ``_build_page_content`` 결과(타이틀 2 회 + 슬러그 1 회 +
    aliases) 에 frontmatter 슬러그가 들어가 있으므로 ‘자기 문서’만 강하게 활성화한다.
    한국어 일반 키워드(예: "면접") 는 여러 코퍼스 본문에 등장해 collision 위험이 있어
    포함하지 않는다. 따라서 단위 테스트는 슬러그/명시적 alias 토큰 위주로 쿼리한다.
    """

    # 9 슬러그 + custom 케이스용 토큰. 모두 코퍼스 한 곳에서만 등장한다.
    _VOCAB = [
        "interview",
        "business_meeting",
        "presentation",
        "wedding_guest",
        "office_daily",
        "casual_date",
        "school_daily",
        "outdoor_activity",
        "general",
        "송년회",  # 커스텀 케이스 (어떤 코퍼스에도 없음)
    ]

    def __init__(self) -> None:
        self._index = {token: i for i, token in enumerate(self._VOCAB)}
        self._dim = len(self._VOCAB)

    def _vector(self, text: str) -> list[float]:
        import math

        vec = [0.0] * self._dim
        for token in self._VOCAB:
            count = text.count(token)
            if count:
                vec[self._index[token]] = float(count)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def dummy_embedder() -> _DummyEmbeddings:
    """다운로드/네트워크 없는 결정적 임베더."""
    return _DummyEmbeddings()


@pytest.fixture
def mock_faiss_store(dummy_embedder: _DummyEmbeddings, corpus_paths: list[pathlib.Path]):
    """더미 임베더 + 실제 코퍼스 9 건으로 in-memory FAISS 인덱스를 빌드한다.

    on-disk 인덱스 / 모델 다운로드 없이 ``tier1_retrieve`` 의 검색 로직을 검증한다.
    """
    import frontmatter
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document

    from agents.context.tier1 import _build_page_content

    docs = []
    for p in corpus_paths:
        post = frontmatter.load(p)
        meta = dict(post.metadata)
        if "curated_at" in meta and not isinstance(meta["curated_at"], str):
            meta["curated_at"] = str(meta["curated_at"])
        page_content = _build_page_content(meta, post.content)
        docs.append(Document(page_content=page_content, metadata=meta))
    return FAISS.from_documents(docs, dummy_embedder)


@pytest.fixture
def patched_store(monkeypatch: pytest.MonkeyPatch, mock_faiss_store: Any):
    """``tier1._store`` lru_cache 를 통째로 대체해 ``tier1_retrieve`` 가 mock 인덱스를 사용하게 한다.

    monkeypatch teardown 이 원본 함수로 복원해 주므로 별도 ``cache_clear`` 호출은 필요 없다.
    원본 ``_store`` 가 캐싱되어 있다면 미리 비워서 mock 이 새 호출에 적용되게 한다.
    """
    from agents.context import tier1

    if hasattr(tier1._store, "cache_clear"):
        tier1._store.cache_clear()
    monkeypatch.setattr(tier1, "_store", lambda: mock_faiss_store)
    yield mock_faiss_store
