"""
Vision Agent 공개 인터페이스.

Backend super-graph는 vision_subgraph와 analyze_outfit만 사용합니다.
내부 노드·도구는 이 파일을 통해 노출되지 않습니다.
"""
from .graph import vision_subgraph
from .state import VisionState, VisionResponse


async def analyze_outfit(session_id: str, image_bytes: bytes) -> VisionResponse:
    """
    이미지를 받아 의류 속성을 분석하고 VisionResponse를 반환합니다.

    Backend super-graph의 vision 노드에서 호출하는 단일 진입점입니다.

    Args:
      session_id: 세션 고유 ID
      image_bytes: 전처리된 이미지 바이트 (JPEG/PNG)

    Returns:
      VisionResponse. garments에 슬롯별 의류 속성이 담겨 있습니다.

    Raises:
      ValueError: 이미지 해상도 미달 등 400 전파 대상 에러
      RuntimeError: VLM 호출 실패 등 502 전파 대상 에러
    """
    initial_state = VisionState(session_id=session_id, image=image_bytes)

    # LangGraph 그래프를 비동기로 실행합니다.
    final_state: dict = await vision_subgraph.ainvoke(initial_state.model_dump())

    # 치명적 에러가 있으면 예외를 발생시켜 Backend로 전파합니다.
    if final_state.get("error"):
        raise ValueError(final_state["error"])

    quality = final_state.get("quality") or {"resolution_ok": True, "frontal": True, "occlusion_ratio": 0.0}

    return VisionResponse(
        session_id=session_id,
        person_detected=True,  # Backend 전처리 단계에서 이미 검증됨
        image_quality=quality,
        garments=final_state.get("garments", []),
        warnings=final_state.get("warnings", []),
        agent_meta={
            "steps_taken": final_state.get("steps_taken", 0),
            "vlm_calls": final_state.get("vlm_calls", 0),
            "tool_call_log": final_state.get("tool_call_log", []),
        },
    )


__all__ = ["vision_subgraph", "analyze_outfit"]
