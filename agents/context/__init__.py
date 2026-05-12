"""Context Agent — 일정/상황 → 드레스코드 컨텍스트 sub-graph.

PR-A에서는 데이터 모델과 정적 RAG 코퍼스만 추가한다.
``context_subgraph`` export는 PR-E에서 추가되므로, 그 전까지
``api/app/agents_stub/__init__.py``의 selector는 stub으로 폴백한다.
(``docs/specs/03-agent-context-spec.md`` §10.5 참고.)
"""
