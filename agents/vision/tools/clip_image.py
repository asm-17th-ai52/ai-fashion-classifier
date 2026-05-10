"""
슬롯별 이미지 크롭 유틸리티.

Targeted Re-extract(Step 3)에서 특정 슬롯 영역만 VLM에 전달할 때 사용합니다.
dominant_rgb.py의 _SLOT_VERTICAL_HINTS와 같은 기준을 공유합니다.
"""
import io
from PIL import Image
from .dominant_rgb import _SLOT_VERTICAL_HINTS


def clip_image_by_slot(
    image_bytes: bytes,
    slot: str,
    padding: float = 0.05,
) -> bytes:
    """
    슬롯에 해당하는 수직 영역을 잘라 JPEG 바이트로 반환합니다.

    수평은 전체 너비를 유지하고, 수직만 슬롯 힌트 비율로 자릅니다.
    padding을 추가해 슬롯 경계 근처의 의류가 잘리지 않도록 합니다.

    Args:
      image_bytes: 원본 이미지 바이트 (JPEG/PNG)
      slot: 슬롯 이름 ("top", "bottom", "outer", "shoes", "bag", "watch")
      padding: 수직 영역 상하에 추가할 여유 비율 (기본 5%)

    Returns:
      크롭된 JPEG 바이트. 알 수 없는 슬롯이면 전체 이미지를 반환합니다.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    y_start_ratio, y_end_ratio = _SLOT_VERTICAL_HINTS.get(slot, (0.0, 1.0))

    y1 = max(0, int(height * max(0.0, y_start_ratio - padding)))
    y2 = min(height, int(height * min(1.0, y_end_ratio + padding)))

    cropped = img.crop((0, y1, width, y2))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
