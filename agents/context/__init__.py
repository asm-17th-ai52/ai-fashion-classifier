"""Context Agent — Tier-1 정적 RAG + Tier-2 ReAct 라이브 리서치 sub-graph.

본 모듈이 import 가능하면 backend selector
(``api/app/agents_stub/__init__.py::get_subgraphs``) 가 stub fallback 대신 본
어댑터를 super-graph 노드로 등록한다 — 즉 이 ``__init__.py`` 의 ``context_subgraph``
export 가 **Context Agent 활성화 게이트**다.

PR-A ~ PR-D 까지는 본 파일이 docstring 만 보유해 import 자체는 성공하지만 selector
의 ``from agents.context import context_subgraph`` 가 실패하여 stub 으로 폴백.
PR-E 부터 본 export 가 추가되어 real Context Agent 가 활성화된다.

자세한 sub-graph 구조는 ``docs/specs/03-agent-context-spec.md`` §10.2 참고.
"""
from .adapter import context_subgraph

__all__ = ["context_subgraph"]
