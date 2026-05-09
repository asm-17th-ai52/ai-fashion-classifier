"""
Step 0 노드: 이미지 품질 검증.

이 단계는 VLM을 호출하기 전에 이미지가 분석 가능한 상태인지 확인합니다.
검증 실패 시 state.error를 설정하고 이후 노드 실행을 중단합니다.
"""
import time
from ..state import VisionState
from ..tools.validate_image import validate_image


def node_validate_image(state: VisionState) -> dict:
    """
    이미지 해상도를 검증하고 품질 정보를 상태에 저장합니다.

    실행 결과는 VisionState의 다음 필드를 업데이트합니다:
      - quality: 검증 결과 (resolution_ok 등)
      - error: 해상도 미달 시 에러 메시지 설정
      - tool_call_log: 실행 시간(ms) 기록 추가

    Args:
      state: 현재 VisionState. image 필드가 반드시 있어야 합니다.

    Returns:
      변경된 필드만 담은 dict. LangGraph가 자동으로 상태에 병합합니다.
    """
    start = time.time()
    quality = validate_image(state.image)
    elapsed_ms = int((time.time() - start) * 1000)

    # 실행 기록을 tool_call_log에 추가합니다.
    log_entry = {
        "tool": "validate_image",
        "ms": elapsed_ms,
        "resolution_ok": quality.resolution_ok,
    }

    # 해상도가 기준 미달이면 에러 메시지를 설정합니다.
    # graph.py의 라우팅 함수가 이 값을 보고 즉시 종료 여부를 결정합니다.
    error = None if quality.resolution_ok else "이미지 해상도가 너무 낮습니다 (최소 480p 필요)"

    return {
        "quality": quality,
        "error": error,
        "tool_call_log": state.tool_call_log + [log_entry],
    }
