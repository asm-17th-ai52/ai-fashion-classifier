"""
Step 1 노드: VLM 1차 추출 및 색상 덮어쓰기.

실행 순서:
  1. node_vlm_extract_all: Gemini에 이미지를 전달해 의류 속성을 추출합니다.
  2. node_overwrite_colors: OpenCV k-means로 실제 픽셀 색상을 측정해 VLM 결과를 덮어씁니다.

색상을 VLM이 아닌 OpenCV로 측정하는 이유:
  VLM(LLM)은 색상을 언어적으로 추론하므로 오차가 큽니다.
  OpenCV는 실제 픽셀값을 직접 계산하므로 정량적이고 재현 가능합니다.
"""
import os
import time
import base64
from typing import Literal
from PIL import Image
import io
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일을 자동으로 로드합니다.
load_dotenv()

from google import genai
from google.genai import types
from pydantic import BaseModel

from ..state import VisionState, Garment, PrimaryColor
from ..tools.dominant_rgb import extract_dominant_rgb
from ..prompts import SYSTEM_PROMPT_EXTRACT_ALL, USER_PROMPT_EXTRACT_ALL


# ──────────────────────────────────────────────
# VLM 구조화 출력 스키마
# VLM이 반환해야 하는 JSON의 모양을 Pydantic으로 정의합니다.
# 색상 필드는 포함되지 않습니다 (overwrite_colors 노드에서 채웁니다).
# ──────────────────────────────────────────────

class _GarmentVLMOutput(BaseModel):
    """VLM이 반환하는 단일 의류 속성. 색상 필드는 제외됩니다."""
    slot: Literal["top", "bottom", "outer", "shoes", "bag", "watch"]
    category: str
    subcategory: str | None = None
    pattern: Literal["solid", "stripe", "check", "dot", "graphic", "other"]
    estimated_material: (
        Literal["cotton", "wool", "synthetic", "denim", "leather", "knit", "unknown"] | None
    ) = None
    fit: Literal["slim", "regular", "loose", "oversized", "unknown"] | None = None
    sleeve_length: Literal["sleeveless", "short", "long", "n/a"] | None = None
    formality_label: Literal[
        "casual", "smart_casual", "business_casual", "business_formal", "formal"
    ]
    confidence: float


class _VLMExtractionOutput(BaseModel):
    """VLM 전체 응답: 감지된 의류 목록을 담습니다."""
    garments: list[_GarmentVLMOutput]


GEMINI_MODEL = "gemini-2.5-flash"


def _build_client() -> genai.Client:
    """google.genai 클라이언트를 생성합니다."""
    # TODO: GOOGLE_API_KEY를 .env 파일 또는 시스템 환경변수에 설정해야 합니다.
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


def _image_to_base64(image_bytes: bytes) -> tuple[str, str]:
    """
    이미지 바이트를 base64 문자열로 변환하고 MIME 타입을 반환합니다.

    Returns:
      (base64 문자열, MIME 타입) 튜플. 예: ("...", "image/jpeg")
    """
    img = Image.open(io.BytesIO(image_bytes))
    mime_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    mime = mime_map.get(img.format or "", "image/jpeg")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return b64, mime


# ──────────────────────────────────────────────
# Step 1-A: VLM 1차 추출 노드
# ──────────────────────────────────────────────

def node_vlm_extract_all(state: VisionState) -> dict:
    """
    Gemini에 전체 이미지를 전달해 모든 슬롯의 의류 속성을 한 번에 추출합니다.

    - 네트워크 오류 시 1회 재시도합니다.
    - 재시도 후에도 실패하면 state.error를 설정하고 즉시 종료합니다.
    - VLM이 반환한 색상은 이 단계에서 무시하고 _pending으로 설정합니다.

    업데이트 필드: garments, vlm_calls, steps_taken, tool_call_log, error
    """
    client = _build_client()
    b64, mime = _image_to_base64(state.image)

    # Gemini Vision API에 전달할 콘텐츠를 구성합니다.
    contents = [
        types.Content(parts=[
            types.Part(inline_data=types.Blob(mime_type=mime, data=base64.b64decode(b64))),
            types.Part(text=f"{SYSTEM_PROMPT_EXTRACT_ALL}\n\n{USER_PROMPT_EXTRACT_ALL}"),
        ])
    ]

    # response_schema로 Pydantic 모델을 지정하면 구조화된 JSON을 반환합니다.
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_VLMExtractionOutput,
        temperature=0,  # 재현성을 위해 항상 0으로 고정
    )

    # VLM 호출 (실패 시 1회 재시도)
    start = time.time()
    result: _VLMExtractionOutput | None = None
    error: str | None = None

    for attempt in range(2):  # 최대 2회 시도 (0: 첫 시도, 1: 재시도)
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config
            )
            result = _VLMExtractionOutput.model_validate_json(response.text)
            break
        except Exception as e:
            if attempt == 1:
                error = f"VLM 호출 실패: {e}"

    elapsed_ms = int((time.time() - start) * 1000)

    if error or result is None:
        return {
            "error": error or "VLM이 결과를 반환하지 않았습니다.",
            "tool_call_log": state.tool_call_log + [
                {"tool": "vlm_extract_all", "ms": elapsed_ms, "success": False}
            ],
        }

    # VLM 출력(_GarmentVLMOutput)을 상태에서 사용하는 Garment 모델로 변환합니다.
    # 이 시점에서 primary_color는 _pending 상태입니다.
    garments = [
        Garment(
            slot=g.slot,
            category=g.category,
            subcategory=g.subcategory,
            pattern=g.pattern,
            estimated_material=g.estimated_material,
            fit=g.fit,
            sleeve_length=g.sleeve_length,
            formality_label=g.formality_label,
            confidence=g.confidence,
            primary_color=PrimaryColor(rgb=[0, 0, 0], name="_pending"),
        )
        for g in result.garments
    ]

    # TODO: confidence 평균이 0.6 미만이면 warnings에 "low_avg_confidence" 추가 (spec §9)
    # TODO: schema 위반 시 Critic 없이 자동 재추출 트리거 (spec §10)

    return {
        "garments": garments,
        "vlm_calls": state.vlm_calls + 1,
        "steps_taken": state.steps_taken + 1,
        "tool_call_log": state.tool_call_log + [
            {"tool": "vlm_extract_all", "ms": elapsed_ms, "success": True, "garment_count": len(garments)}
        ],
    }


# ──────────────────────────────────────────────
# Step 1-B: 색상 덮어쓰기 노드
# ──────────────────────────────────────────────

def node_overwrite_colors(state: VisionState) -> dict:
    """
    각 의류 슬롯의 실제 픽셀 색상을 OpenCV k-means로 측정해 garments에 덮어씁니다.

    VLM이 추정한 색상은 신뢰도가 낮으므로 이 단계에서 반드시 교체합니다.
    슬롯별 이미지 영역은 이미지 높이 비율 휴리스틱으로 추정합니다.

    업데이트 필드: garments, tool_call_log
    """
    # TODO: slot_bboxes가 있으면 휴리스틱 대신 정확한 bbox를 사용하도록 개선 (spec §5.1)

    updated_garments = []
    log_entries = []

    for garment in state.garments:
        start = time.time()

        # 슬롯에 해당하는 이미지 영역에서 지배적 색상을 추출합니다.
        rgb_tuple, color_name = extract_dominant_rgb(state.image, slot=garment.slot)
        elapsed_ms = int((time.time() - start) * 1000)

        # 측정한 실제 RGB로 garment의 primary_color를 교체합니다.
        updated = garment.model_copy(
            update={"primary_color": PrimaryColor(rgb=list(rgb_tuple), name=color_name)}
        )
        updated_garments.append(updated)

        log_entries.append({
            "tool": "overwrite_colors",
            "slot": garment.slot,
            "ms": elapsed_ms,
            "rgb": list(rgb_tuple),
            "name": color_name,
        })

    return {
        "garments": updated_garments,
        "tool_call_log": state.tool_call_log + log_entries,
    }
