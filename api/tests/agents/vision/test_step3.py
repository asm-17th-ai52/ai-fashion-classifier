"""
Step 3 Critic LLM + Targeted Re-extract 테스트.

테스트 범위:
  - clip_image_by_slot: 슬롯별 이미지 크롭
  - node_critic_llm: VLM 목으로 재추출 계획 생성
  - node_vlm_extract_targeted: VLM 목으로 슬롯별 재추출
  - 그래프 라우팅: violations → critic → reextract/give_up 경로
"""
import io
import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from app.agents.vision.tools.clip_image import clip_image_by_slot
from app.agents.vision.state import (
    VisionState, Garment, PrimaryColor, Violation, ReextractPlan,
)
from app.agents.vision.nodes.step3_nodes import node_critic_llm, node_vlm_extract_targeted
from app.agents.vision.graph import build_vision_graph


# ──────────────────────────────────────────────
# 테스트 헬퍼
# ──────────────────────────────────────────────

def _make_image_bytes(width: int = 640, height: int = 960, color=(200, 180, 150)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_garment(slot="top", category="티셔츠", pattern="solid") -> Garment:
    return Garment(
        slot=slot,
        category=category,
        pattern=pattern,
        formality_label="casual",
        confidence=0.9,
        primary_color=PrimaryColor(rgb=[200, 180, 150], name="베이지"),
    )


def _make_state_with_violations(violations: list[Violation], steps_taken=1) -> VisionState:
    return VisionState(
        session_id="test",
        image=_make_image_bytes(),
        garments=[_make_garment("top"), _make_garment("bottom", category="청바지")],
        violations=violations,
        steps_taken=steps_taken,
    )


def _make_mock_client(json_text: str, side_effect=None) -> MagicMock:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json_text
    if side_effect:
        mock_client.models.generate_content.side_effect = side_effect
    else:
        mock_client.models.generate_content.return_value = mock_response
    return mock_client


# ──────────────────────────────────────────────
# clip_image_by_slot 테스트
# ──────────────────────────────────────────────

class TestClipImageBySlot:

    def test_top_슬롯_크롭_높이_감소(self):
        """top 슬롯 크롭 결과는 원본보다 높이가 작아야 합니다."""
        image = _make_image_bytes(640, 960)
        result = clip_image_by_slot(image, "top")
        img = Image.open(io.BytesIO(result))
        assert img.width == 640
        assert img.height < 960

    def test_jpeg_magic_bytes_반환(self):
        """반환된 바이트는 JPEG 형식이어야 합니다."""
        image = _make_image_bytes(640, 960)
        result = clip_image_by_slot(image, "bottom")
        assert isinstance(result, bytes)
        assert result[:2] == b'\xff\xd8'

    def test_알_수_없는_슬롯은_전체_이미지(self):
        """등록되지 않은 슬롯 이름이면 전체 이미지(패딩 포함)를 반환해야 합니다."""
        image = _make_image_bytes(640, 960)
        result = clip_image_by_slot(image, "unknown_slot", padding=0.0)
        img = Image.open(io.BytesIO(result))
        assert img.height == 960

    def test_padding_클수록_더_큰_영역(self):
        """padding이 클수록 크롭 영역이 더 넓어야 합니다."""
        image = _make_image_bytes(640, 960)
        result_no_pad = clip_image_by_slot(image, "top", padding=0.0)
        result_with_pad = clip_image_by_slot(image, "top", padding=0.1)
        img_no_pad = Image.open(io.BytesIO(result_no_pad))
        img_with_pad = Image.open(io.BytesIO(result_with_pad))
        assert img_with_pad.height >= img_no_pad.height

    def test_모든_슬롯_정상_처리(self):
        """모든 정의된 슬롯에서 오류 없이 크롭되어야 합니다."""
        image = _make_image_bytes(640, 960)
        for slot in ["top", "bottom", "outer", "shoes", "bag", "watch"]:
            result = clip_image_by_slot(image, slot)
            assert len(result) > 0


# ──────────────────────────────────────────────
# node_critic_llm 단위 테스트
# ──────────────────────────────────────────────

class TestNodeCriticLlm:

    def test_재추출_계획_반환(self):
        """Critic LLM이 정상 응답하면 ReextractPlan이 state에 설정되어야 합니다."""
        violations = [Violation(type="vocab", slot="top", detail="pattern 위반")]
        state = _make_state_with_violations(violations)
        plan_json = json.dumps({"slots": ["top"], "fields": ["pattern"], "reason": "패턴 오류", "give_up": False})

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(plan_json)
            result = node_critic_llm(state)

        assert "reextract_plan" in result
        assert result["reextract_plan"].slots == ["top"]
        assert result["reextract_plan"].fields == ["pattern"]
        assert result["give_up"] is False

    def test_give_up_true_반환(self):
        """Critic LLM이 give_up=True를 반환하면 warnings에 critic_give_up이 추가되어야 합니다."""
        violations = [Violation(type="duplicate_slot", slot="top", detail="중복")]
        state = _make_state_with_violations(violations)
        plan_json = json.dumps({"slots": [], "fields": [], "reason": "중복 해결 불가", "give_up": True})

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(plan_json)
            result = node_critic_llm(state)

        assert result["give_up"] is True
        assert "critic_give_up" in result["warnings"]

    def test_critic_실패_시_give_up_fallback(self):
        """Critic LLM 호출 예외 발생 시 give_up=True로 fallback해야 합니다."""
        violations = [Violation(type="vocab", slot="top")]
        state = _make_state_with_violations(violations)

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client("", side_effect=Exception("API 오류"))
            result = node_critic_llm(state)

        assert result["give_up"] is True
        assert "critic_failed" in result["warnings"]

    def test_tool_call_log_기록(self):
        """Critic LLM 호출 후 tool_call_log에 critic_llm 항목이 추가되어야 합니다."""
        violations = [Violation(type="vocab", slot="top")]
        state = _make_state_with_violations(violations)
        plan_json = json.dumps({"slots": ["top"], "fields": ["pattern"], "reason": "오류", "give_up": False})

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(plan_json)
            result = node_critic_llm(state)

        tool_names = [log["tool"] for log in result["tool_call_log"]]
        assert "critic_llm" in tool_names

    def test_기존_warnings_유지(self):
        """기존 warnings에 새 경고를 추가해야 합니다 (덮어쓰기 금지)."""
        violations = [Violation(type="vocab", slot="top")]
        state = VisionState(
            session_id="test",
            image=_make_image_bytes(),
            garments=[_make_garment()],
            violations=violations,
            warnings=["missing_slot:shoes"],
            steps_taken=1,
        )
        plan_json = json.dumps({"slots": [], "fields": [], "reason": "포기", "give_up": True})

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(plan_json)
            result = node_critic_llm(state)

        assert "missing_slot:shoes" in result["warnings"]
        assert "critic_give_up" in result["warnings"]


# ──────────────────────────────────────────────
# node_vlm_extract_targeted 단위 테스트
# ──────────────────────────────────────────────

class TestNodeVlmExtractTargeted:

    _VALID_GARMENT = {
        "slot": "top", "category": "셔츠", "subcategory": None,
        "color_hint": None, "pattern": "stripe",
        "estimated_material": "cotton", "fit": "regular",
        "sleeve_length": "long", "formality_label": "smart_casual",
        "confidence": 0.95,
    }

    def _make_state_with_plan(self, slots: list[str]) -> VisionState:
        garments = [_make_garment("top"), _make_garment("bottom", category="청바지")]
        plan = ReextractPlan(slots=slots, fields=["pattern"], reason="테스트", give_up=False)
        return VisionState(
            session_id="test",
            image=_make_image_bytes(),
            garments=garments,
            reextract_plan=plan,
            violations=[Violation(type="vocab", slot="top")],
            steps_taken=1,
        )

    def test_대상_슬롯_garment_교체(self):
        """target 슬롯의 garment가 VLM 재추출 결과로 교체되어야 합니다."""
        state = self._make_state_with_plan(["top"])

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json.dumps(self._VALID_GARMENT))
            result = node_vlm_extract_targeted(state)

        top = next(g for g in result["garments"] if g.slot == "top")
        assert top.category == "셔츠"
        assert top.pattern == "stripe"

    def test_비대상_슬롯_원본_유지(self):
        """target에 포함되지 않은 슬롯은 원본 garment가 유지되어야 합니다."""
        state = self._make_state_with_plan(["top"])

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json.dumps(self._VALID_GARMENT))
            result = node_vlm_extract_targeted(state)

        bottom = next(g for g in result["garments"] if g.slot == "bottom")
        assert bottom.category == "청바지"

    def test_violations_초기화(self):
        """재추출 후 violations가 빈 목록으로 초기화되어야 합니다."""
        state = self._make_state_with_plan(["top"])

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json.dumps(self._VALID_GARMENT))
            result = node_vlm_extract_targeted(state)

        assert result["violations"] == []

    def test_steps_taken_증가(self):
        """재추출 후 steps_taken이 1 증가해야 합니다."""
        state = self._make_state_with_plan(["top"])
        initial_steps = state.steps_taken

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json.dumps(self._VALID_GARMENT))
            result = node_vlm_extract_targeted(state)

        assert result["steps_taken"] == initial_steps + 1

    def test_primary_color_pending_초기화(self):
        """재추출된 garment의 primary_color는 _pending으로 초기화되어야 합니다."""
        state = self._make_state_with_plan(["top"])

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json.dumps(self._VALID_GARMENT))
            result = node_vlm_extract_targeted(state)

        top = next(g for g in result["garments"] if g.slot == "top")
        assert top.primary_color.name == "_pending"

    def test_reextract_plan_없으면_노옵(self):
        """reextract_plan이 없으면 빈 dict를 반환해야 합니다."""
        state = VisionState(
            session_id="test",
            image=_make_image_bytes(),
            garments=[_make_garment()],
        )
        result = node_vlm_extract_targeted(state)
        assert result == {}

    def test_vlm_실패_시_원본_유지(self):
        """VLM 호출이 실패하면 해당 슬롯의 원본 garment를 유지해야 합니다."""
        state = self._make_state_with_plan(["top"])

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client("", side_effect=Exception("API 오류"))
            result = node_vlm_extract_targeted(state)

        top = next(g for g in result["garments"] if g.slot == "top")
        assert top.category == "티셔츠"  # 원본 유지

    def test_garment_순서_유지(self):
        """재추출 후 garments 순서가 원본과 동일해야 합니다."""
        state = self._make_state_with_plan(["top"])

        with patch("app.agents.vision.nodes.step3_nodes._build_client") as mock_build:
            mock_build.return_value = _make_mock_client(json.dumps(self._VALID_GARMENT))
            result = node_vlm_extract_targeted(state)

        slots = [g.slot for g in result["garments"]]
        assert slots == ["top", "bottom"]


# ──────────────────────────────────────────────
# 그래프 라우팅 통합 테스트
# ──────────────────────────────────────────────

_MOCK_VLM_TOP = {
    "slot": "top", "category": "티셔츠", "subcategory": None,
    "color_hint": None, "pattern": "solid",
    "estimated_material": "cotton", "fit": "regular",
    "sleeve_length": "short", "formality_label": "casual", "confidence": 0.9,
}
_MOCK_VLM_JSON = json.dumps({"garments": [_MOCK_VLM_TOP]})


class TestScenarioE_CriticGiveUp통합:

    def test_critic_give_up_경고_포함(self):
        """
        violations 존재 → critic_llm 호출 → give_up=True 반환 시
        최종 결과의 warnings에 'critic_give_up'이 포함되어야 합니다.
        """
        image = _make_image_bytes()
        give_up_plan_json = json.dumps(
            {"slots": [], "fields": [], "reason": "해결 불가", "give_up": True}
        )

        mock_vlm_client = _make_mock_client(_MOCK_VLM_JSON)
        mock_critic_client = _make_mock_client(give_up_plan_json)

        # verify_vocabulary가 첫 번째 실행에서만 violation을 반환하도록 패치합니다.
        call_index = [0]
        original_verify = __import__(
            "app.agents.vision.nodes.step2_nodes", fromlist=["verify_vocabulary"]
        ).verify_vocabulary

        def patched_verify_vocabulary(state):
            call_index[0] += 1
            if call_index[0] == 1:
                return [Violation(type="vocab", slot="top", detail="테스트 위반")]
            return []

        with patch("app.agents.vision.nodes.step1_nodes._build_client", return_value=mock_vlm_client), \
             patch("app.agents.vision.nodes.step3_nodes._build_client", return_value=mock_critic_client), \
             patch("app.agents.vision.nodes.step2_nodes.verify_vocabulary", patched_verify_vocabulary):
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-e01", image=image).model_dump())

        assert "critic_give_up" in result["warnings"]

    def test_critic_호출_시_tool_call_log_기록(self):
        """critic_llm 노드가 실행되면 tool_call_log에 기록되어야 합니다."""
        image = _make_image_bytes()
        give_up_plan_json = json.dumps(
            {"slots": [], "fields": [], "reason": "포기", "give_up": True}
        )

        call_index = [0]

        def patched_verify_vocabulary(state):
            call_index[0] += 1
            if call_index[0] == 1:
                return [Violation(type="vocab", slot="top", detail="테스트")]
            return []

        with patch("app.agents.vision.nodes.step1_nodes._build_client",
                   return_value=_make_mock_client(_MOCK_VLM_JSON)), \
             patch("app.agents.vision.nodes.step3_nodes._build_client",
                   return_value=_make_mock_client(give_up_plan_json)), \
             patch("app.agents.vision.nodes.step2_nodes.verify_vocabulary", patched_verify_vocabulary):
            graph = build_vision_graph()
            result = graph.invoke(VisionState(session_id="test-e02", image=image).model_dump())

        tool_names = [log["tool"] for log in result["tool_call_log"]]
        assert "critic_llm" in tool_names


class TestScenarioF_MaxSteps통합:

    def test_steps_초과_시_exhausted_종료(self):
        """
        violations가 지속되더라도 steps_taken >= 3이면 그래프가 종료되어야 합니다.
        무한 루프가 발생하지 않아야 합니다.
        """
        image = _make_image_bytes()

        # Critic은 항상 reextract를 반환합니다 (give_up=False).
        reextract_plan_json = json.dumps(
            {"slots": ["top"], "fields": ["pattern"], "reason": "계속 재추출", "give_up": False}
        )
        targeted_garment_json = json.dumps(_MOCK_VLM_TOP)

        # verify_vocabulary는 항상 violation을 반환합니다.
        def always_violations(state):
            return [Violation(type="vocab", slot="top", detail="지속 위반")]

        with patch("app.agents.vision.nodes.step1_nodes._build_client",
                   return_value=_make_mock_client(_MOCK_VLM_JSON)), \
             patch("app.agents.vision.nodes.step3_nodes._build_client",
                   return_value=_make_mock_client(reextract_plan_json if True else targeted_garment_json)), \
             patch("app.agents.vision.nodes.step2_nodes.verify_vocabulary", always_violations):

            # 모의 클라이언트가 critic과 targeted 모두 처리하도록 side_effect 구성
            call_count = [0]
            mock_step3_client = MagicMock()

            def step3_generate(model, contents, config):
                call_count[0] += 1
                mock_response = MagicMock()
                has_image = any(
                    hasattr(p, "inline_data") and p.inline_data is not None
                    for c in contents for p in c.parts
                )
                mock_response.text = targeted_garment_json if has_image else reextract_plan_json
                return mock_response

            mock_step3_client.models.generate_content.side_effect = step3_generate

            with patch("app.agents.vision.nodes.step3_nodes._build_client",
                       return_value=mock_step3_client):
                graph = build_vision_graph()
                result = graph.invoke(VisionState(session_id="test-f01", image=image).model_dump())

        # 그래프가 무한 루프 없이 종료되어야 합니다.
        assert result is not None
        # steps_taken이 3 이하로 종료되어야 합니다.
        assert result["steps_taken"] <= 3
