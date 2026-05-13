"""Context Agent — Tier-1 정적 RAG + Tier-2 ReAct 라이브 리서치 sub-graph.

본 모듈이 ``context_subgraph`` 를 제공하면 backend selector
(``api/app/agents_stub/__init__.py::get_subgraphs``) 가 stub fallback 대신 본
어댑터를 super-graph 노드로 등록한다 — 즉 이 ``__init__.py`` 의 ``context_subgraph``
export 가 **Context Agent 활성화 게이트**다.

활성화 방식: PEP 562 lazy attribute access.
- ``from agents.context import context_subgraph`` 호출 시점에 ``adapter`` 가 import 된다.
- 단순히 ``agents.context.tier1`` 같은 하위 모듈만 import 할 때는 ``adapter`` 가 import
  되지 않아 ``from app.schemas...`` 등의 의존성이 평가되지 않는다.
- pytest 가 ``agents/context/tests/conftest.py`` 를 로드하기 위해 ``agents.context``
  package 를 import 할 때 본 ``__init__.py`` 가 실행되지만, lazy 덕분에 adapter 의
  ``app.schemas`` import 가 conftest 의 ``sys.path`` 조정 이전에 평가되지 않는다.

자세한 sub-graph 구조는 ``docs/specs/03-agent-context-spec.md`` §10.2 참고.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any


__all__ = ["context_subgraph"]


if TYPE_CHECKING:  # type checker 도움용 — 런타임 import 는 lazy.
    from .adapter import context_subgraph as context_subgraph


def __getattr__(name: str) -> Any:
    """``from agents.context import context_subgraph`` 호출 시점에만 adapter 를 import."""
    if name == "context_subgraph":
        from .adapter import context_subgraph as _cs

        return _cs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
