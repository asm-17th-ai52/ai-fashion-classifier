"""
이미지에서 지배적인(가장 많이 차지하는) 색상을 추출하는 도구입니다.

처리 순서:
  1. rembg로 배경을 제거해 사람(의류) 픽셀만 남깁니다.
  2. 슬롯별 수직 영역(예: 상의는 상단 15~55%)으로 자릅니다.
  3. OpenCV k-means로 해당 영역에서 가장 많은 색상을 찾습니다.

rembg를 사용하는 이유:
  배경 벽, 가구(의자, 스툴 등)가 포함된 직사각형 영역을 그대로 k-means에
  넣으면 배경 픽셀이 의류 픽셀보다 많아 잘못된 색상이 반환됩니다.
  rembg는 딥러닝 세그멘테이션으로 사람 영역만 분리해 이 문제를 해결합니다.
"""
import io
import cv2
import numpy as np
from PIL import Image

from .color_lookup import rgb_to_korean_name

# rembg가 설치되지 않은 환경(CI 등)에서도 임포트 오류 없이 동작하도록 처리합니다.
try:
    from rembg import remove as rembg_remove
    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False


# K-means 클러스터 수: 색상을 K개 그룹으로 분류합니다.
KMEANS_K = 5

# 배경으로 판단하는 밝기 임계값 (rembg 미사용 시 fallback).
# R+G+B 합이 이 값 이상이면 배경으로 간주합니다.
_BG_BRIGHTNESS_THRESHOLD = 520

# 슬롯별 수직 영역 비율 (이미지 높이 기준).
# 튜플: (시작 비율, 끝 비율). 예: (0.22, 0.55)는 상단 22%~55% 구간.
# 얼굴/머리는 일반적으로 이미지 상단 20% 이내이므로
# top/outer는 22%부터 시작해 피부 픽셀이 분석 영역에 섞이지 않도록 합니다.
_SLOT_VERTICAL_HINTS: dict[str, tuple[float, float]] = {
    "top":    (0.22, 0.55),
    "bottom": (0.58, 0.82),  # 코트/자켓 자락 아래 구간만 분석 (허벅지 이하)
    "outer":  (0.22, 0.72),
    "shoes":  (0.78, 1.00),
    "bag":    (0.30, 0.70),
    "watch":  (0.35, 0.65),
}


def _remove_background(image_bytes: bytes) -> Image.Image:
    """
    rembg로 배경을 제거하고 RGBA 이미지를 반환합니다.
    알파(A) 채널이 0인 픽셀은 배경으로 마스킹됩니다.

    rembg를 사용할 수 없으면 원본 이미지(RGB)를 그대로 반환합니다.
    """
    if not _REMBG_AVAILABLE:
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # rembg는 bytes → bytes로 변환합니다 (내부에서 ONNX 모델 실행).
    result_bytes = rembg_remove(image_bytes)
    return Image.open(io.BytesIO(result_bytes)).convert("RGBA")


def _get_slot_crop(img: Image.Image, slot: str) -> Image.Image:
    """
    슬롯에 해당하는 영역을 잘라냅니다.

    - 수직: 슬롯별 힌트 비율 적용
    - 수평: 중앙 60%만 사용 (양쪽 가장자리에 늘어진 손/팔 피부 픽셀 제외)
      rembg가 배경을 제거하더라도 손·팔은 인물 픽셀로 유지되므로 별도로 제한합니다.
    """
    width, height = img.size
    y_start_ratio, y_end_ratio = _SLOT_VERTICAL_HINTS.get(slot, (0.0, 1.0))
    x1 = int(width * 0.20)
    x2 = int(width * 0.80)
    y1 = int(height * y_start_ratio)
    y2 = int(height * y_end_ratio)
    return img.crop((x1, y1, x2, y2))


def _dominant_rgb_from_image(img: Image.Image) -> tuple[int, int, int]:
    """
    PIL 이미지(RGB 또는 RGBA)에서 k-means로 지배적 색상을 반환합니다.

    RGBA 이미지의 경우 알파가 0인 픽셀(배경)을 분석에서 제외합니다.
    모든 픽셀이 배경이면 (0, 0, 0)을 반환합니다.
    """
    arr = np.array(img)

    if arr.shape[2] == 4:
        # 알파 채널이 있으면 불투명 픽셀(알파 > 10)만 추출합니다.
        alpha = arr[:, :, 3]
        mask = alpha > 10
        pixels = arr[:, :, :3][mask].astype(np.float32)
    else:
        pixels = arr.reshape(-1, 3).astype(np.float32)

    # 유효한 픽셀이 너무 적으면 k-means를 실행할 수 없습니다.
    if len(pixels) < KMEANS_K:
        return (0, 0, 0)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(
        pixels, KMEANS_K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )

    # 픽셀 수 기준으로 가장 큰 클러스터를 선택합니다.
    counts = np.bincount(labels.flatten())
    dominant = centers[np.argmax(counts)].astype(int)
    return (int(dominant[0]), int(dominant[1]), int(dominant[2]))


def _dominant_rgb_fallback(image_bytes: bytes, slot: str | None) -> tuple[int, int, int]:
    """
    rembg 없이 밝기 임계값으로 배경을 제거하는 fallback 로직.
    배경(벽, 하늘 등 밝은 영역)을 통계적으로 제외합니다.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if slot:
        img = _get_slot_crop(img, slot)

    pixel_array = np.array(img).reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(
        pixel_array, KMEANS_K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )

    counts = np.bincount(labels.flatten())
    sorted_idx = np.argsort(counts)[::-1]

    # 배경으로 추정되는 밝은 클러스터를 건너뜁니다.
    dominant = centers[sorted_idx[0]].astype(int)
    for idx in sorted_idx:
        c = centers[idx].astype(int)
        if int(c[0]) + int(c[1]) + int(c[2]) < _BG_BRIGHTNESS_THRESHOLD:
            dominant = c
            break

    return (int(dominant[0]), int(dominant[1]), int(dominant[2]))


def extract_dominant_rgb(
    image_bytes: bytes,
    slot: str | None = None,
    bbox: tuple[int, int, int, int] | None = None,
) -> tuple[tuple[int, int, int], str]:
    """
    이미지에서 가장 지배적인 색상의 RGB 값과 한글 이름을 반환합니다.

    처리 순서:
      1. rembg로 배경 제거 (사람 픽셀만 남김)
      2. bbox 또는 slot 영역으로 자르기
      3. k-means로 지배적 색상 추출

    rembg를 사용할 수 없으면 밝기 임계값 기반 fallback을 사용합니다.

    Args:
      image_bytes: JPEG 또는 PNG 형식의 이미지 바이트
      slot: 슬롯 이름 (선택). 수직 영역 추정에 사용됩니다.
      bbox: (x1, y1, x2, y2) 픽셀 좌표 (선택). 직접 지정 시 slot보다 우선합니다.

    Returns:
      ((R, G, B), "한글색상이름") 형태의 튜플.
    """
    if not _REMBG_AVAILABLE:
        rgb = _dominant_rgb_fallback(image_bytes, slot)
        return rgb, rgb_to_korean_name(rgb)

    # 1단계: rembg로 배경 제거 → RGBA 이미지 (배경 픽셀의 알파=0)
    img_rgba = _remove_background(image_bytes)

    # 2단계: bbox 또는 slot 영역으로 자르기
    if bbox:
        x1, y1, x2, y2 = bbox
        img_rgba = img_rgba.crop((x1, y1, x2, y2))
    elif slot:
        img_rgba = _get_slot_crop(img_rgba, slot)

    # 3단계: k-means로 지배적 색상 추출 (배경 픽셀 제외)
    rgb = _dominant_rgb_from_image(img_rgba)

    # k-means 결과가 (0,0,0)이면 fallback 사용
    if rgb == (0, 0, 0):
        rgb = _dominant_rgb_fallback(image_bytes, slot)

    return rgb, rgb_to_korean_name(rgb)
