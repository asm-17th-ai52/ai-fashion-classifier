"""
Vision Agent가 VLM(Gemini)에 전달하는 프롬프트를 정의합니다.

설계 원칙 (spec §7 기준):
  - 색상(RGB) 추출은 VLM이 담당하지 않습니다. OpenCV 도구가 덮어씁니다.
  - VLM은 카테고리·패턴·소재·핏·격식도만 담당합니다.
  - temperature=0으로 호출하므로 재현성이 보장됩니다.
"""

# VLM이 출력해야 하는 JSON 스키마 설명 (프롬프트에 삽입됩니다)
_SCHEMA_DESCRIPTION = """
{
  "garments": [
    {
      "slot": "top | bottom | outer | shoes | bag | watch",
      "category": "의류 종류 (예: 티셔츠, 청바지, 스니커즈)",
      "subcategory": "세부 종류 또는 null",
      "pattern": "solid | stripe | check | dot | graphic | other",
      "estimated_material": "cotton | wool | synthetic | denim | leather | knit | unknown 또는 null",
      "fit": "slim | regular | loose | oversized | unknown 또는 null",
      "sleeve_length": "sleeveless | short | long | n/a 또는 null",
      "formality_label": "casual | smart_casual | business_casual | business_formal | formal",
      "confidence": 0.0~1.0 사이의 숫자
    }
  ]
}
"""

# 1차 추출 시스템 프롬프트: VLM의 역할과 출력 형식을 지정합니다.
SYSTEM_PROMPT_EXTRACT_ALL = """You are a clothing attribute extractor. Output JSON ONLY matching the provided schema. Use ONLY the allowed enum values listed in the schema.

Rules:
- Do NOT output color information (rgb, color name). Color will be measured separately by deterministic tools.
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
