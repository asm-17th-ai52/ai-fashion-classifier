"""
한국어 SentenceTransformer 임베더 래퍼.

Tier-1 정적 RAG / 향후 Tier-2 임시 RAG 모두 동일 임베더 인스턴스를 사용한다.
``langchain_huggingface`` 가 권장 import 경로 (community 쪽은 deprecated).

본 모듈은 **raw 임베딩만 제공**한다. distance strategy / score 환산은 호출 측
(``tier1.py``) 의 책임이며, 본 PR-B 에서는 L2 + 수동 cosine 변환을 사용한다
(자세한 사유는 ``tier1.py`` 모듈 docstring 참조).

핵심 옵션:
- ``normalize_embeddings=True``: cosine 유사도 계산을 위한 L2 정규화.
  정규화된 벡터끼리는 ``IP(a, b) == cos(a, b)`` 이며, ``‖a-b‖² == 2 - 2·cos`` 이
  성립해 ``tier1.py`` 의 ``_l2_to_cosine`` 환산이 정확하다.
- ``device='cpu'``: 배포 환경(CPU only) 가정. GPU 가용 환경에서도 결정성/재현성 우선.
- ``revision``: HuggingFace Hub commit SHA 핀. 모델 가중치가 무성하게 갱신되더라도
  본 repo 의 캘리브레이션 결과 (``tier1.py`` 의 ``SELF_MATCH_FLOOR`` 등) 가 유지되도록.
"""
from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings


# ko-sroberta-multitask: 한국어 의미 유사도 모델 (약 440MB).
# 면접/결혼식 하객 등 한국어 도메인 쿼리에 강함. 영문 alias 도 합리적으로 처리한다.
_MODEL_NAME = "jhgan/ko-sroberta-multitask"
# HuggingFace Hub commit SHA — 2026-05-12 조회 기준.
# 모델 가중치 갱신 시 캘리브레이션 (self-match floor 등) 영향 회피.
_MODEL_REVISION = "ab957ae6a91e99c4cad36d52063a2a9cf1bf4419"


def build_embedder() -> HuggingFaceEmbeddings:
    """기본 임베더 인스턴스를 반환한다.

    호출 측에서 캐싱한다 (``tier1._store`` 가 lru_cache 로 1회만 인스턴스화).
    """
    return HuggingFaceEmbeddings(
        model_name=_MODEL_NAME,
        model_kwargs={"device": "cpu", "revision": _MODEL_REVISION},
        encode_kwargs={"normalize_embeddings": True},
    )
