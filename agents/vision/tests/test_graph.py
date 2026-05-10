"""
Vision Agent LangGraph 워크플로우 통합 테스트.

VLM(Gemini) 호출은 unittest.mock으로 대체해 실제 API 키 없이 실행 가능합니다.

테스트 시나리오:
  A: 해상도 통과 → VLM 추출 성공 → 색상 덮어쓰기 (정상 흐름)
  B: 해상도 미달 → 즉시 종료 (400 에러 흐름)
  C: VLM 호출 실패 → state.error 설정 (502 에러 흐름)
"""
import io
import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from agents.vision.graph import build_vision_graph
from agents.vision.state import VisionState


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

# google.genai SDK는 client.models.generate_content().text로 JSON 문자열을 반환합니다.
_MOCK_VLM_JSON = json.dumps({"garments": _MOCK_VLM_GARMENTS})


def _make_mock_client(json_text: str = _MOCK_VLM_JSON, side_effect=None) -> MagicMock:
    """
    google.genai Client mock을 생성합니다.
    client.models.generate_content(...)  →  response.text = json_text
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json_text
    if side_effect:
        mock_client.models.generate_content.side_effect = side_effect
    else:
        mock_client.models.generate_content.return_value = mock_response
    return mock_client


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

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client()
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-001", image=image).model_dump())

        assert result["error"] is None
        assert len(result["garments"]) == 2
        assert result["vlm_calls"] == 1

    def test_색상_덮어쓰기_완료(self):
        """
        overwrite_colors 실행 후 모든 garment의 primary_color.name이
        '_pending'이 아닌 실제 색상 이름으로 바뀌어야 합니다.
        """
        image = _make_image_bytes(640, 960)

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client()
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-002", image=image).model_dump())

        for garment in result["garments"]:
            color = garment["primary_color"] if isinstance(garment, dict) else garment.primary_color
            name = color["name"] if isinstance(color, dict) else color.name
            assert name != "_pending", f"색상이 덮어쓰여야 합니다: {garment}"

    def test_tool_call_log_기록(self):
        """validate_image와 vlm_extract_all, overwrite_colors 실행 기록이 모두 남아야 합니다."""
        image = _make_image_bytes(640, 960)
        single_garment_json = json.dumps({"garments": [_MOCK_VLM_GARMENTS[0]]})

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json_text=single_garment_json)
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-003", image=image).model_dump())

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

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            graph = build_vision_graph()
            graph.invoke(VisionState(session_id="test-005", image=image).model_dump())
            mock_build.assert_not_called()


# ──────────────────────────────────────────────
# 시나리오 C: VLM 호출 실패
# ──────────────────────────────────────────────

class TestScenarioC_VLM실패:

    def test_vlm_실패_시_error_설정(self):
        """VLM 호출이 2회 모두 실패하면 state.error가 설정되어야 합니다."""
        image = _make_image_bytes(640, 960)

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(side_effect=Exception("API 오류"))
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-006", image=image).model_dump())

        assert result["error"] is not None
        assert "VLM" in result["error"]


# ──────────────────────────────────────────────
# 시나리오 D: Step 2 Verifier 통합
# ──────────────────────────────────────────────

class TestScenarioD_Verifier통합:

    def test_정상_흐름에서_violations_없음(self):
        """정상 흐름에서 Verifier를 통과하면 violations가 비어야 합니다."""
        image = _make_image_bytes(640, 960)

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client()
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-007", image=image).model_dump())

        assert result["violations"] == []

    def test_verifier_tool_call_log_기록(self):
        """run_verifiers 실행 기록이 tool_call_log에 남아야 합니다."""
        image = _make_image_bytes(640, 960)

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client()
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-008", image=image).model_dump())

        tool_names = [log["tool"] for log in result["tool_call_log"]]
        assert "verify_vocabulary" in tool_names
        assert "verify_no_duplicate_slot" in tool_names
        assert "verify_color_label_consistency" in tool_names
        assert "verify_schema" in tool_names
        assert "verify_required_slots" in tool_names

    def test_missing_slot_경고_추가(self):
        """필수 슬롯이 누락되면 warnings에 'missing_slot:*'이 추가되어야 합니다."""
        image = _make_image_bytes(640, 960)
        # top 슬롯만 있는 단일 garment 응답
        single_garment_json = json.dumps({"garments": [_MOCK_VLM_GARMENTS[0]]})

        with patch("agents.vision.nodes.step1_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json_text=single_garment_json)
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-009", image=image).model_dump())

        # top만 있으므로 bottom, shoes 누락 경고가 있어야 합니다.
        missing_warnings = [w for w in result["warnings"] if w.startswith("missing_slot:")]
        assert len(missing_warnings) >= 1
