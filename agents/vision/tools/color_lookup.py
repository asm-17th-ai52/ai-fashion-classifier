"""
RGB 색상값을 한글 색상 이름으로 변환하는 도구입니다.

사용 방법:
  rgb_to_korean_name((255, 255, 255))  →  "흰색"
  rgb_to_korean_name((0, 0, 128))      →  "진파랑"
  korean_name_to_rgb("네이비")         →  (0, 0, 139)

변환 원리:
  미리 정의된 기준 색상 목록과의 유클리드 거리를 계산해서
  가장 가까운 색상의 한글 이름을 반환합니다.
"""
import math


# 기준 색상 테이블: (R, G, B) → 한글 이름
# 실제 의류에서 자주 등장하는 색상 위주로 구성했습니다.
_COLOR_TABLE: list[tuple[tuple[int, int, int], str]] = [
    ((255, 255, 255), "흰색"),
    ((245, 245, 245), "오프화이트"),
    ((245, 245, 220), "베이지"),
    ((210, 180, 140), "탄"),
    ((196, 155, 115), "카멜"),
    ((0, 0, 0), "검정"),
    ((64, 64, 64), "진회색"),
    ((128, 128, 128), "회색"),
    ((192, 192, 192), "연회색"),
    ((255, 0, 0), "빨강"),
    ((128, 0, 0), "진빨강"),
    ((255, 182, 193), "연분홍"),
    ((255, 105, 180), "핑크"),
    ((255, 165, 0), "주황"),
    ((255, 255, 0), "노랑"),
    ((0, 128, 0), "초록"),
    ((34, 139, 34), "포레스트그린"),
    ((0, 255, 0), "연두"),
    ((0, 0, 255), "파랑"),
    ((0, 0, 128), "진파랑"),
    ((0, 128, 128), "청록"),
    ((135, 206, 235), "하늘"),
    ((0, 0, 139), "네이비"),
    ((128, 0, 128), "보라"),
    ((75, 0, 130), "남색"),
    ((165, 42, 42), "갈색"),
    ((101, 67, 33), "진갈색"),
    ((255, 215, 0), "금색"),
    ((192, 192, 192), "은색"),
    ((255, 127, 80), "코랄"),
    ((95, 158, 160), "카데트블루"),
    ((106, 90, 205), "슬레이트블루"),
    ((188, 143, 143), "로즈우드"),
    ((112, 128, 144), "슬레이트그레이"),
    ((47, 79, 79), "다크슬레이트그레이"),
    ((240, 230, 140), "카키"),
    ((128, 128, 0), "올리브"),
]

# VLM이 반환할 수 있는 색상 이름 목록.
# step1_nodes.py의 Literal 타입과 prompts.py의 스키마 설명에서 공통으로 참조합니다.
COLOR_NAMES: tuple[str, ...] = tuple(name for _, name in _COLOR_TABLE)

# 색상 이름 → RGB 역방향 조회 딕셔너리 (O(1) 탐색).
_NAME_TO_RGB: dict[str, tuple[int, int, int]] = {name: rgb for rgb, name in _COLOR_TABLE}


def korean_name_to_rgb(name: str) -> tuple[int, int, int]:
    """
    한글 색상 이름을 받아 대응하는 참조 RGB 값을 반환합니다.
    VLM color_hint → PrimaryColor 변환 시 사용합니다.

    color_hint는 Pydantic Literal로 테이블 내 이름만 허용하므로
    KeyError가 발생하면 데이터 흐름 버그입니다.
    """
    return _NAME_TO_RGB[name]


def _euclidean_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """두 RGB 색상 간의 유클리드 거리를 계산합니다. 거리가 작을수록 색상이 비슷합니다."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def rgb_to_korean_name(rgb: tuple[int, int, int]) -> str:
    """
    RGB 값을 받아 가장 가까운 한글 색상 이름을 반환합니다.

    Args:
      rgb: (R, G, B) 형태의 튜플. 각 값은 0~255 사이 정수.

    Returns:
      한글 색상 이름 문자열. (예: "네이비", "베이지", "검정")

    예시:
      rgb_to_korean_name((0, 0, 100))  →  "네이비"
      rgb_to_korean_name((200, 200, 200))  →  "연회색"
    """
    closest_name = _COLOR_TABLE[0][1]
    min_distance = float("inf")

    for ref_rgb, name in _COLOR_TABLE:
        dist = _euclidean_distance(rgb, ref_rgb)
        if dist < min_distance:
            min_distance = dist
            closest_name = name

    return closest_name
