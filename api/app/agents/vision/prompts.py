"""
Vision Agent가 VLM(Gemini)에 전달하는 프롬프트를 정의합니다.

설계 원칙 (spec §7 기준):
  - 색상의 주요 수단은 OpenCV 픽셀 분석입니다.
  - 단, 가려진 의류(예: 코트 안의 티셔츠)는 픽셀 분석이 불가능하므로
    VLM이 color_hint를 반환하고, overwrite_colors 노드가 fallback으로 사용합니다.
  - color_hint는 반드시 허용된 한글 색상 이름 중 하나여야 합니다.
  - temperature=0으로 호출하므로 재현성이 보장됩니다.
"""
from .tools.color_lookup import COLOR_NAMES

# 허용된 색상 이름 목록을 문자열로 변환합니다 (프롬프트에 삽입됩니다).
_COLOR_NAMES_STR = " | ".join(COLOR_NAMES)

# VLM이 출력해야 하는 JSON 스키마 설명 (프롬프트에 삽입됩니다)
_SCHEMA_DESCRIPTION = f"""
{{
  "garments": [
    {{
      "slot": "top | bottom | outer | shoes | bag | watch",
      "category": "의류 종류 (예: 티셔츠, 청바지, 스니커즈)",
      "subcategory": "세부 종류 또는 null",
      "color_hint": "아래 허용 목록 중 하나 (의류 색상을 의미론적으로 판단): {_COLOR_NAMES_STR}",
      "pattern": "solid | stripe | check | dot | graphic | other",
      "estimated_material": "cotton | wool | synthetic | denim | leather | knit | unknown 또는 null",
      "fit": "slim | regular | loose | oversized | unknown 또는 null",
      "sleeve_length": "sleeveless | short | long | n/a 또는 null",
      "formality_label": "casual | smart_casual | business_casual | business_formal | formal",
      "confidence": 0.0~1.0 사이의 숫자
    }}
  ]
}}
"""

# 1차 추출 시스템 프롬프트: VLM의 역할과 출력 형식을 지정합니다.
SYSTEM_PROMPT_EXTRACT_ALL = f"""You are a clothing attribute extractor. Output JSON ONLY matching the provided schema. Use ONLY the allowed enum values listed in the schema.

Rules:
- For color_hint, output the Korean color name that best describes the garment's color. Choose ONLY from this list: {_COLOR_NAMES_STR}
- color_hint is a semantic color judgment (what the garment actually is), not a pixel measurement. For partially hidden garments (e.g., a shirt under a coat), estimate based on the visible portion or overall appearance.
- Do NOT infer the wearer's identity, body shape, age, gender, or make aesthetic judgments.
- For each garment slot visible in the image (top, bottom, outer, shoes, bag, watch), extract the attributes.
- If a field is uncertain, use "unknown" and set confidence ≤ 0.5.
- If a slot is not visible, do not include it in the output."""

# 1차 추출 유저 프롬프트: 이미지와 함께 VLM에 전달됩니다.
USER_PROMPT_EXTRACT_ALL = f"""Extract garment attributes from this image.
Return JSON matching this schema exactly:
{_SCHEMA_DESCRIPTION}"""


def build_targeted_user_prompt(slot: str, prev_garment: dict, violations: list[dict]) -> str:
    """
    특정 슬롯을 재추출할 때 사용하는 유저 프롬프트를 생성합니다.

    Args:
      slot: 재추출 대상 슬롯 이름 (예: "top")
      prev_garment: 이전 VLM 추출 결과 (dict 형태)
      violations: 해당 슬롯에서 발견된 위반 목록

    Returns:
      VLM에 전달할 유저 프롬프트 문자열
    """
    return (
        f"You previously extracted for slot '{slot}': {prev_garment}\n"
        f"Verifiers reported these violations: {violations}\n"
        f"Re-examine ONLY the '{slot}' slot in the cropped image and output the corrected garment object.\n"
        f"Return JSON matching this schema:\n{_SCHEMA_DESCRIPTION}"
    )
