"""Vision Agent 결정적 도구 모음. 순수 함수로 구성되어 동일 입력에 동일 결과를 보장합니다."""
from .validate_image import validate_image
from .dominant_rgb import extract_dominant_rgb
from .color_lookup import rgb_to_korean_name

__all__ = ["validate_image", "extract_dominant_rgb", "rgb_to_korean_name"]
