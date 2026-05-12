"""
Vision Agent LangGraph StateGraph 정의.

그래프 구조 (Step 0 + Step 1 + Step 2 + Step 3):
  validate_image
    ├── 해상도 실패 → END (state.error 설정됨)
    └── 통과 → vlm_extract_all → overwrite_colors → run_verifiers
                                       ↑                   ├── violations 없음 → END
                                       │                   ├── steps 초과 → END
                                       │                   └── violations 있음 → critic_llm
                                       │                                           ├── give_up → END
                                       └───────────────── vlm_extract_targeted ←── reextract

TODO: 7초 타임아웃 초과 시 부분 결과 반환 처리 (spec §6.1)
"""
from langgraph.graph import StateGraph, END

from .state import VisionState
from .nodes.step0_nodes import node_validate_image
from .nodes.step1_nodes import node_vlm_extract_all, node_overwrite_colors
from .nodes.step2_nodes import node_run_verifiers
from .nodes.step3_nodes import node_critic_llm, node_vlm_extract_targeted


def _route_after_validate(state: VisionState) -> str:
    """
    validate_image 실행 후 다음 노드를 결정하는 라우팅 함수입니다.

    state.error가 설정되어 있으면 그래프를 즉시 종료합니다.
    Backend는 state.error 값을 보고 클라이언트에 400을 반환합니다.
    """
    if state.error:
        return "fail"
    return "ok"


def _route_after_verify(state: VisionState) -> str:
    """
    run_verifiers 실행 후 다음 노드를 결정하는 라우팅 함수입니다.

    - violations 없음: 정상 종료
    - steps_taken >= 3: 최대 재시도 횟수 초과, 현재 결과 반환
    - violations 있음: Critic LLM으로 라우팅 (재추출 계획 수립)
    """
    if not state.violations:
        return "done"
    if state.steps_taken >= 3:
        return "exhausted"
    return "critic"


def _route_after_critic(state: VisionState) -> str:
    """
    critic_llm 실행 후 다음 노드를 결정하는 라우팅 함수입니다.

    - give_up=True: 재추출 포기, 현재 결과 반환
    - give_up=False: vlm_extract_targeted로 라우팅
    """
    if state.give_up or not state.reextract_plan:
        return "give_up"
    return "reextract"


def build_vision_graph() -> StateGraph:
    """
    Vision Agent 그래프를 생성하고 컴파일합니다.

    Returns:
      컴파일된 LangGraph CompiledGraph. vision_subgraph로 노출됩니다.
    """
    g = StateGraph(VisionState)

    # 노드 등록
    g.add_node("validate_image",         node_validate_image)
    g.add_node("vlm_extract_all",        node_vlm_extract_all)
    g.add_node("overwrite_colors",       node_overwrite_colors)
    g.add_node("run_verifiers",          node_run_verifiers)
    g.add_node("critic_llm",             node_critic_llm)
    g.add_node("vlm_extract_targeted",   node_vlm_extract_targeted)

    # 진입점 설정
    g.set_entry_point("validate_image")

    # Step 0: 이미지 검증 결과에 따라 분기
    g.add_conditional_edges(
        "validate_image",
        _route_after_validate,
        {"ok": "vlm_extract_all", "fail": END},
    )

    # Step 1: VLM 추출 → 색상 덮어쓰기 → Verifier
    g.add_edge("vlm_extract_all",  "overwrite_colors")
    g.add_edge("overwrite_colors", "run_verifiers")

    # Step 2: Verifier 결과에 따라 분기
    g.add_conditional_edges(
        "run_verifiers",
        _route_after_verify,
        {
            "done":      END,          # violations 없음: 정상 종료
            "exhausted": END,          # step 초과: 경고 후 종료
            "critic":    "critic_llm", # violations 있음: Critic LLM으로 라우팅
        },
    )

    # Step 3: Critic LLM → give_up 또는 재추출
    g.add_conditional_edges(
        "critic_llm",
        _route_after_critic,
        {
            "give_up":   END,                    # 재추출 포기: 현재 결과 반환
            "reextract": "vlm_extract_targeted", # 재추출 실행
        },
    )

    # Step 3 → Step 1 사이클: 재추출 후 색상 덮어쓰기 → 재검증
    g.add_edge("vlm_extract_targeted", "overwrite_colors")

    return g.compile()


# Backend super-graph가 import해서 사용하는 단일 진입점입니다.
vision_subgraph = build_vision_graph()
