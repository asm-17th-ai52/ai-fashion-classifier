"""Context Agent Tier-2 도구 레이어.

스펙 ``docs/specs/03-agent-context-spec.md`` §6.2~§6.8 의 ReAct 도구 화이트리스트
(web_search / fetch_page / youtube_transcript) + 도메인 화이트리스트 + 비용/속도 카운터.

본 패키지는 **순수 도구 함수**만 제공한다. LangGraph 노드 래핑은 PR-D 에서.
모든 도구는 예외를 raise 하지 않고 ``(result, warning)`` 튜플로 결과를 반환한다
(LangGraph state 에 warning 을 축적하기 위해서).
"""
