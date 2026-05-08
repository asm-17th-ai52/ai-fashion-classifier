"""
Vision Agent LangGraph StateGraph 정의.

현재 구현된 그래프 구조 (Step 0 + Step 1):
  validate_image
    ├── 해상도 실패 → END (state.error 설정됨)
    └── 통과 → vlm_extract_all → overwrite_colors → END

TODO: Step 2 Verifier 노드 추가 (spec §6 Step 2)
TODO: Step 3 Critic LLM 및 Targeted Re-extract 노드 추가 (spec §6 Step 3~4)
TODO: 7초 타임아웃 초과 시 부분 결과 반환 처리 (spec §6.1)
"""
from langgraph.graph import StateGraph, END

from .state import VisionState
from .nodes.step0_nodes import node_validate_image
from .nodes.step1_nodes import node_vlm_extract_all, node_overwrite_colors


def _route_after_validate(state: VisionState) -> str:
    """
    validate_image 실행 후 다음 노드를 결정하는 라우팅 함수입니다.

    state.error가 설정되어 있으면 그래프를 즉시 종료합니다.
    Backend는 state.error 값을 보고 클라이언트에 400을 반환합니다.
    """
    if state.error:
        return "fail"
    return "ok"


def build_vision_graph() -> StateGraph:
    """
    Vision Agent 그래프를 생성하고 컴파일합니다.

    Returns:
      컴파일된 LangGraph CompiledGraph. vision_subgraph로 노출됩니다.
    """
    g = StateGraph(VisionState)

    # 노드 등록
    g.add_node("validate_image", node_validate_image)
    g.add_node("vlm_extract_all", node_vlm_extract_all)
    g.add_node("overwrite_colors", node_overwrite_colors)

    # 진입점 설정
    g.set_entry_point("validate_image")

    # validate_image 결과에 따라 분기
    g.add_conditional_edges(
        "validate_image",
        _route_after_validate,
        {"ok": "vlm_extract_all", "fail": END},
    )

    # Step 1 직선 연결
    g.add_edge("vlm_extract_all", "overwrite_colors")
    g.add_edge("overwrite_colors", END)

    return g.compile()


# Backend super-graph가 import해서 사용하는 단일 진입점입니다.
vision_subgraph = build_vision_graph()
