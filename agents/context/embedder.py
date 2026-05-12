"""
한국어 SentenceTransformer 임베더 래퍼.

Tier-1 정적 RAG / 향후 Tier-2 임시 RAG 모두 동일 임베더 인스턴스를 사용한다.
``langchain_huggingface`` 가 권장 import 경로 (community 쪽은 deprecated).

핵심 옵션:
- ``normalize_embeddings=True``: cosine 유사도가 곧 inner product 가 되도록 L2 정규화.
  FAISS 인덱스 빌드 시 ``DistanceStrategy.MAX_INNER_PRODUCT`` 와 조합해야 점수 [0, 1] 로 해석 가능.
- ``device='cpu'``: 배포 환경(CPU only) 가정. GPU 가용 환경에서도 결정성/재현성 우선.
"""
from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings


# ko-sroberta-multitask: 한국어 의미 유사도 모델 (약 440MB).
# 면접/결혼식 하객 등 한국어 도메인 쿼리에 강함. 영문 alias 도 합리적으로 처리한다.
_MODEL_NAME = "jhgan/ko-sroberta-multitask"


def build_embedder() -> HuggingFaceEmbeddings:
    """기본 임베더 인스턴스를 반환한다.

    호출 측에서 캐싱한다 (``tier1._store`` 가 lru_cache 로 1회만 인스턴스화).
    """
    return HuggingFaceEmbeddings(
        model_name=_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
