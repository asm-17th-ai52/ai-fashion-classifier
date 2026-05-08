"""
이미지 품질을 검증하는 도구입니다.

현재 검증 항목:
  - 해상도: 짧은 쪽(가로 또는 세로)이 MIN_SHORT_SIDE 픽셀 이상이어야 합니다.

검증 실패 시 Vision Agent는 즉시 에러를 반환하고 VLM 호출을 생략합니다.
"""
from PIL import Image
import io
from ..state import ImageQuality


# 최소 해상도 기준: 짧은 쪽이 이 픽셀 이상이어야 분석 가능합니다.
MIN_SHORT_SIDE = 480


def validate_image(image_bytes: bytes) -> ImageQuality:
    """
    이미지 바이트를 받아 품질 검증 결과를 반환합니다.

    Args:
      image_bytes: JPEG 또는 PNG 형식의 이미지 바이트

    Returns:
      ImageQuality 객체.
      resolution_ok=False이면 Vision Agent가 400 에러를 반환합니다.

    예시:
      결과 = validate_image(image_bytes)
      if not 결과.resolution_ok:
          raise ValueError("이미지 해상도가 너무 낮습니다")
    """
    # Pillow로 이미지를 열어 가로·세로 픽셀 수를 확인합니다.
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    # 가로·세로 중 짧은 쪽이 기준값 이상인지 확인합니다.
    short_side = min(width, height)
    resolution_ok = short_side >= MIN_SHORT_SIDE

    return ImageQuality(resolution_ok=resolution_ok)
