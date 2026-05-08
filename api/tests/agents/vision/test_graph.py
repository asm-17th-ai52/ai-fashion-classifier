"""
Vision Agent LangGraph 워크플로우 통합 테스트.

VLM(Gemini) 호출은 unittest.mock으로 대체해 실제 API 키 없이 실행 가능합니다.

테스트 시나리오:
  A: 해상도 통과 → VLM 추출 성공 → 색상 덮어쓰기 (정상 흐름)
  B: 해상도 미달 → 즉시 종료 (400 에러 흐름)
  C: VLM 호출 실패 → state.error 설정 (502 에러 흐름)
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from app.agents.vision.graph import build_vision_graph
from app.agents.vision.state import VisionState


# ──────────────────────────────────────────────
# 테스트 픽스처
# ──────────────────────────────────────────────

def _make_image_bytes(width: int = 640, height: int = 960, color=(200, 180, 150)) -> bytes:
    """테스트용 단색 JPEG 이미지 바이트를 생성합니다."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# VLM이 반환하는 garments 목 데이터
_MOCK_VLM_GARMENTS = [
    {
        "slot": "top",
        "category": "티셔츠",
        "subcategory": None,
        "pattern": "solid",
        "estimated_material": "cotton",
        "fit": "regular",
        "sleeve_length": "short",
        "formality_label": "casual",
        "confidence": 0.9,
    },
    {
        "slot": "bottom",
        "category": "청바지",
        "subcategory": None,
        "pattern": "solid",
        "estimated_material": "denim",
        "fit": "slim",
        "sleeve_length": "n/a",
        "formality_label": "casual",
        "confidence": 0.85,
    },
]


# ──────────────────────────────────────────────
# 시나리오 A: 정상 흐름
# ──────────────────────────────────────────────

class TestScenarioA_정상흐름:

    def test_해상도_통과_후_garments_추출(self):
        """
        해상도가 충분한 이미지에서 VLM이 garments를 반환하면
        최종 상태에 garments가 채워져야 합니다.
        """
        image = _make_image_bytes(640, 960)

        # VLM 호출을 목으로 대체합니다.
        mock_output = MagicMock()
        mock_output.garments = [MagicMock(**g) for g in _MOCK_VLM_GARMENTS]

        with patch(
            "app.agents.vision.nodes.step1_nodes._build_llm"
        ) as mock_build_llm:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value.invoke.return_value = mock_output
            mock_build_llm.return_value = mock_llm

            graph = build_vision_graph()
            initial = VisionState(session_id="test-001", image=image)
            result = graph.invoke(initial.model_dump())

        assert result["error"] is None
        assert len(result["garments"]) == 2
        assert result["vlm_calls"] == 1

    def test_색상_덮어쓰기_완료(self):
        """
        overwrite_colors 실행 후 모든 garment의 primary_color.name이
        '_pending'이 아닌 실제 색상 이름으로 바뀌어야 합니다.
        """
        image = _make_image_bytes(640, 960)

        mock_output = MagicMock()
        mock_output.garments = [MagicMock(**g) for g in _MOCK_VLM_GARMENTS]

        with patch("app.agents.vision.nodes.step1_nodes._build_llm") as mock_build_llm:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value.invoke.return_value = mock_output
            mock_build_llm.return_value = mock_llm

            graph = build_vision_graph()
            initial = VisionState(session_id="test-002", image=image)
            result = graph.invoke(initial.model_dump())

        for garment in result["garments"]:
            color = garment["primary_color"] if isinstance(garment, dict) else garment.primary_color
            name = color["name"] if isinstance(color, dict) else color.name
            assert name != "_pending", f"색상이 덮어쓰여야 합니다: {garment}"

    def test_tool_call_log_기록(self):
        """validate_image와 vlm_extract_all, overwrite_colors 실행 기록이 모두 남아야 합니다."""
        image = _make_image_bytes(640, 960)

        mock_output = MagicMock()
        mock_output.garments = [MagicMock(**_MOCK_VLM_GARMENTS[0])]

        with patch("app.agents.vision.nodes.step1_nodes._build_llm") as mock_build_llm:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value.invoke.return_value = mock_output
            mock_build_llm.return_value = mock_llm

            graph = build_vision_graph()
            initial = VisionState(session_id="test-003", image=image)
            result = graph.invoke(initial.model_dump())

        tool_names = [log["tool"] for log in result["tool_call_log"]]
        assert "validate_image" in tool_names
        assert "vlm_extract_all" in tool_names
        assert "overwrite_colors" in tool_names


# ──────────────────────────────────────────────
# 시나리오 B: 해상도 미달
# ──────────────────────────────────────────────

class TestScenarioB_해상도미달:

    def test_저해상도_이미지_에러_설정(self):
        """해상도가 480p 미만이면 state.error가 설정되고 garments는 비어야 합니다."""
        # 해상도 미달 이미지 (300×300)
        image = _make_image_bytes(300, 300)

        graph = build_vision_graph()
        initial = VisionState(session_id="test-004", image=image)
        result = graph.invoke(initial.model_dump())

        assert result["error"] is not None
        assert result["garments"] == []

    def test_저해상도_시_vlm_호출_없음(self):
        """해상도 검증 실패 시 VLM이 호출되면 안 됩니다."""
        image = _make_image_bytes(300, 300)

        with patch("app.agents.vision.nodes.step1_nodes._build_llm") as mock_build_llm:
            graph = build_vision_graph()
            initial = VisionState(session_id="test-005", image=image)
            graph.invoke(initial.model_dump())

            # VLM 클라이언트 빌더가 호출되지 않아야 합니다.
            mock_build_llm.assert_not_called()


# ──────────────────────────────────────────────
# 시나리오 C: VLM 호출 실패
# ──────────────────────────────────────────────

class TestScenarioC_VLM실패:

    def test_vlm_실패_시_error_설정(self):
        """VLM 호출이 2회 모두 실패하면 state.error가 설정되어야 합니다."""
        image = _make_image_bytes(640, 960)

        with patch("app.agents.vision.nodes.step1_nodes._build_llm") as mock_build_llm:
            mock_llm = MagicMock()
            # invoke를 호출할 때마다 예외를 발생시킵니다.
            mock_llm.with_structured_output.return_value.invoke.side_effect = Exception("API 오류")
            mock_build_llm.return_value = mock_llm

            graph = build_vision_graph()
            initial = VisionState(session_id="test-006", image=image)
            result = graph.invoke(initial.model_dump())

        assert result["error"] is not None
        assert "VLM" in result["error"]
