"""
Vision Agent 결정적 도구(tools) 단위 테스트.

테스트 대상:
  - validate_image: 이미지 해상도 검증
  - extract_dominant_rgb: OpenCV k-means 색상 추출
  - rgb_to_korean_name: RGB → 한글 색상 이름 변환

실제 이미지 파일 없이도 실행 가능하도록
Pillow로 테스트용 이미지를 프로그래밍 방식으로 생성합니다.
"""
import io
import pytest
from PIL import Image

from app.agents.vision.tools.validate_image import validate_image, MIN_SHORT_SIDE
from app.agents.vision.tools.dominant_rgb import extract_dominant_rgb
from app.agents.vision.tools.color_lookup import rgb_to_korean_name


# ──────────────────────────────────────────────
# 테스트 헬퍼: 프로그래밍 방식으로 이미지 생성
# ──────────────────────────────────────────────

def _make_image_bytes(width: int, height: int, color: tuple = (255, 255, 255)) -> bytes:
    """
    지정한 크기와 단색으로 채워진 JPEG 이미지 바이트를 생성합니다.

    Args:
      width: 이미지 너비 (픽셀)
      height: 이미지 높이 (픽셀)
      color: (R, G, B) 단색 채우기 색상

    Returns:
      JPEG 형식의 이미지 바이트
    """
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ──────────────────────────────────────────────
# validate_image 테스트
# ──────────────────────────────────────────────

class TestValidateImage:

    def test_충분한_해상도_통과(self):
        """짧은 쪽이 MIN_SHORT_SIDE 이상이면 resolution_ok=True를 반환해야 합니다."""
        image = _make_image_bytes(MIN_SHORT_SIDE, MIN_SHORT_SIDE)
        result = validate_image(image)
        assert result.resolution_ok is True

    def test_해상도_미달_실패(self):
        """짧은 쪽이 MIN_SHORT_SIDE 미만이면 resolution_ok=False를 반환해야 합니다."""
        image = _make_image_bytes(MIN_SHORT_SIDE - 1, MIN_SHORT_SIDE - 1)
        result = validate_image(image)
        assert result.resolution_ok is False

    def test_가로_세로_중_짧은_쪽_기준(self):
        """가로가 크더라도 세로(짧은 쪽)가 기준 미달이면 실패해야 합니다."""
        image = _make_image_bytes(width=1920, height=MIN_SHORT_SIDE - 1)
        result = validate_image(image)
        assert result.resolution_ok is False

    def test_정확히_기준값_통과(self):
        """짧은 쪽이 정확히 MIN_SHORT_SIDE이면 통과해야 합니다."""
        image = _make_image_bytes(MIN_SHORT_SIDE, 1000)
        result = validate_image(image)
        assert result.resolution_ok is True

    def test_기본값_frontal_true(self):
        """frontal과 occlusion_ratio는 현재 항상 기본값을 반환해야 합니다."""
        image = _make_image_bytes(640, 480)
        result = validate_image(image)
        assert result.frontal is True
        assert result.occlusion_ratio == 0.0


# ──────────────────────────────────────────────
# extract_dominant_rgb 테스트
# ──────────────────────────────────────────────

class TestExtractDominantRgb:

    def test_단색_이미지_정확한_색상_추출(self):
        """단색 이미지에서 해당 색상의 RGB가 가까운 값으로 추출되어야 합니다."""
        # 순수 빨간색 이미지
        image = _make_image_bytes(640, 640, color=(255, 0, 0))
        rgb, name = extract_dominant_rgb(image)
        # k-means 압축 과정에서 약간의 오차가 있을 수 있으므로 범위로 검증합니다.
        assert rgb[0] > 200, "R 채널이 충분히 커야 합니다"
        assert rgb[1] < 50,  "G 채널이 충분히 작아야 합니다"
        assert rgb[2] < 50,  "B 채널이 충분히 작아야 합니다"

    def test_검정_이미지_색상명_반환(self):
        """검정 이미지에서 '검정' 또는 유사한 색상명이 반환되어야 합니다."""
        image = _make_image_bytes(640, 640, color=(0, 0, 0))
        rgb, name = extract_dominant_rgb(image)
        assert name == "검정"

    def test_흰색_이미지_색상명_반환(self):
        """흰색 이미지에서 '흰색' 또는 유사한 색상명이 반환되어야 합니다."""
        image = _make_image_bytes(640, 640, color=(255, 255, 255))
        rgb, name = extract_dominant_rgb(image)
        assert name == "흰색"

    def test_슬롯_지정_시_정상_동작(self):
        """slot을 지정해도 결과가 반환되어야 합니다."""
        image = _make_image_bytes(640, 1200, color=(0, 0, 128))
        rgb, name = extract_dominant_rgb(image, slot="top")
        assert len(rgb) == 3
        assert isinstance(name, str)

    def test_반환_타입_확인(self):
        """반환값이 ((int, int, int), str) 형식이어야 합니다."""
        image = _make_image_bytes(640, 640, color=(128, 64, 32))
        rgb, name = extract_dominant_rgb(image)
        assert len(rgb) == 3
        assert all(isinstance(v, int) for v in rgb)
        assert isinstance(name, str)


# ──────────────────────────────────────────────
# rgb_to_korean_name 테스트
# ──────────────────────────────────────────────

class TestRgbToKoreanName:

    def test_순수_흰색(self):
        assert rgb_to_korean_name((255, 255, 255)) == "흰색"

    def test_순수_검정(self):
        assert rgb_to_korean_name((0, 0, 0)) == "검정"

    def test_순수_빨강(self):
        assert rgb_to_korean_name((255, 0, 0)) == "빨강"

    def test_네이비(self):
        assert rgb_to_korean_name((0, 0, 139)) == "네이비"

    def test_근사값_매핑(self):
        """정확히 일치하지 않아도 가장 가까운 색상 이름을 반환해야 합니다."""
        # (5, 5, 5)는 검정에 가장 가깝습니다.
        result = rgb_to_korean_name((5, 5, 5))
        assert result == "검정"

    def test_반환값_문자열(self):
        """항상 문자열을 반환해야 합니다."""
        result = rgb_to_korean_name((100, 150, 200))
        assert isinstance(result, str)
        assert len(result) > 0
