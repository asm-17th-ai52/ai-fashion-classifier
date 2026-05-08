"""
이미지에서 지배적인(가장 많이 차지하는) 색상을 추출하는 도구입니다.

OpenCV의 k-means 클러스터링 알고리즘을 사용합니다.
k-means는 비슷한 색상의 픽셀들을 K개의 그룹으로 묶고,
그 중 픽셀 수가 가장 많은 그룹의 평균 색상을 반환합니다.

슬롯별 이미지 영역 추정:
  포즈 감지 없이 이미지 높이를 기준으로 각 슬롯의 대략적인 영역을 잘라냅니다.
  (예: 신발은 하단 25%, 상의는 상단 15~55% 구간)
"""
import cv2
import numpy as np
from PIL import Image
import io
from .color_lookup import rgb_to_korean_name


# K-means 클러스터 수: 색상을 K개 그룹으로 분류합니다.
# 값이 클수록 세밀하지만 느립니다. 3이 속도·정확도 균형에 적합합니다.
KMEANS_K = 3

# 슬롯별 수직 영역 비율 (이미지 높이 기준).
# 튜플: (시작 비율, 끝 비율). 예: (0.15, 0.55)는 상단 15%~55% 구간.
_SLOT_VERTICAL_HINTS: dict[str, tuple[float, float]] = {
    "top":    (0.15, 0.55),
    "bottom": (0.45, 0.80),
    "outer":  (0.10, 0.70),
    "shoes":  (0.75, 1.00),
    "bag":    (0.30, 0.70),
    "watch":  (0.25, 0.65),
}


def _get_slot_bbox(image_size: tuple[int, int], slot: str) -> tuple[int, int, int, int]:
    """
    슬롯 이름과 이미지 크기를 받아 해당 슬롯의 예상 영역(bbox)을 반환합니다.

    Args:
      image_size: (가로, 세로) 픽셀 크기
      slot: "top", "bottom", "outer", "shoes", "bag", "watch" 중 하나

    Returns:
      (x1, y1, x2, y2) 형태의 픽셀 좌표. x는 이미지 전체 너비를 사용합니다.
    """
    width, height = image_size
    y_start_ratio, y_end_ratio = _SLOT_VERTICAL_HINTS.get(slot, (0.0, 1.0))
    y1 = int(height * y_start_ratio)
    y2 = int(height * y_end_ratio)
    return (0, y1, width, y2)


def extract_dominant_rgb(
    image_bytes: bytes,
    slot: str | None = None,
    bbox: tuple[int, int, int, int] | None = None,
) -> tuple[tuple[int, int, int], str]:
    """
    이미지에서 가장 지배적인 색상의 RGB 값과 한글 이름을 반환합니다.

    우선순위:
      1. bbox가 직접 주어지면 그 영역만 분석합니다.
      2. slot이 주어지면 슬롯별 휴리스틱 영역을 잘라 분석합니다.
      3. 둘 다 없으면 이미지 전체를 분석합니다.

    Args:
      image_bytes: JPEG 또는 PNG 형식의 이미지 바이트
      slot: 슬롯 이름 (선택). bbox가 없을 때 영역 추정에 사용됩니다.
      bbox: (x1, y1, x2, y2) 픽셀 좌표 (선택). 직접 지정 시 slot보다 우선합니다.

    Returns:
      ((R, G, B), "한글색상이름") 형태의 튜플.

    예시:
      rgb, name = extract_dominant_rgb(image_bytes, slot="top")
      # → ((28, 34, 89), "네이비")
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 분석할 영역 결정: bbox 직접 지정 > 슬롯 휴리스틱 > 전체 이미지
    if bbox:
        x1, y1, x2, y2 = bbox
        img = img.crop((x1, y1, x2, y2))
    elif slot:
        x1, y1, x2, y2 = _get_slot_bbox(img.size, slot)
        img = img.crop((x1, y1, x2, y2))

    # 이미지를 (픽셀 수 × 3) 형태의 2D 배열로 변환합니다.
    # k-means는 각 픽셀을 3차원 공간(R, G, B)의 점으로 처리합니다.
    pixel_array = np.array(img).reshape(-1, 3).astype(np.float32)

    # k-means 실행: 픽셀들을 KMEANS_K개의 색상 그룹으로 묶습니다.
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(
        pixel_array, KMEANS_K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )

    # 픽셀 수가 가장 많은 클러스터의 중심 색상을 선택합니다.
    counts = np.bincount(labels.flatten())
    dominant_center = centers[np.argmax(counts)].astype(int)

    rgb = (int(dominant_center[0]), int(dominant_center[1]), int(dominant_center[2]))
    name = rgb_to_korean_name(rgb)

    return rgb, name
