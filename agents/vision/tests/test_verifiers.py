"""
Step 2 Verifier 단위 테스트.

각 verifier 함수를 직접 호출해 정상 케이스와 위반 케이스를 검증합니다.
VLM 호출 없이 순수하게 결정적 로직만 테스트합니다.
"""
import pytest
from agents.vision.state import VisionState, Garment, PrimaryColor
from agents.vision.nodes.step2_nodes import (
    verify_vocabulary,
    verify_no_duplicate_slot,
    verify_color_label_consistency,
    verify_schema,
    verify_required_slots,
)


# ──────────────────────────────────────────────
# 테스트 픽스처
# ──────────────────────────────────────────────

def _make_garment(
    slot="top",
    category="티셔츠",
    pattern="solid",
    formality_label="casual",
    estimated_material="cotton",
    fit="regular",
    sleeve_length="short",
    rgb=(255, 255, 255),
    color_name="흰색",
) -> Garment:
    """유효한 값으로 테스트용 Garment 객체를 생성합니다."""
    return Garment(
        slot=slot,
        category=category,
        pattern=pattern,
        formality_label=formality_label,
        estimated_material=estimated_material,
        fit=fit,
        sleeve_length=sleeve_length,
        confidence=0.9,
        primary_color=PrimaryColor(rgb=list(rgb), name=color_name),
    )


def _make_invalid_garment(slot="top", **overrides) -> Garment:
    """
    허용되지 않는 값으로 Garment 객체를 생성합니다.

    model_construct는 Pydantic 유효성 검사를 건너뛰므로
    verify_vocabulary가 잡아야 할 잘못된 값을 주입할 수 있습니다.
    """
    defaults = dict(
        slot=slot,
        category="티셔츠",
        pattern="solid",
        formality_label="casual",
        estimated_material="cotton",
        fit="regular",
        sleeve_length="short",
        confidence=0.9,
        primary_color=PrimaryColor(rgb=[255, 255, 255], name="흰색"),
    )
    defaults.update(overrides)
    return Garment.model_construct(**defaults)


def _make_state(garments: list[Garment]) -> VisionState:
    """테스트용 VisionState를 생성합니다."""
    return VisionState(session_id="test", image=b"fake", garments=garments)


# ──────────────────────────────────────────────
# verify_vocabulary
# ──────────────────────────────────────────────

class TestVerifyVocabulary:

    def test_정상_케이스_위반없음(self):
        """모든 enum 필드가 허용 값이면 위반이 없어야 합니다."""
        state = _make_state([_make_garment()])
        assert verify_vocabulary(state) == []

    def test_pattern_위반(self):
        """허용되지 않은 pattern 값은 위반을 반환해야 합니다."""
        garment = _make_invalid_garment(pattern="floral")
        state = _make_state([garment])
        violations = verify_vocabulary(state)
        assert len(violations) == 1
        assert violations[0].type == "vocab"
        assert violations[0].slot == "top"
        assert "pattern" in violations[0].detail

    def test_formality_label_위반(self):
        """허용되지 않은 formality_label 값은 위반을 반환해야 합니다."""
        garment = _make_invalid_garment(formality_label="semi_formal")
        state = _make_state([garment])
        violations = verify_vocabulary(state)
        assert any(v.type == "vocab" and "formality_label" in v.detail for v in violations)

    def test_estimated_material_위반(self):
        """허용되지 않은 estimated_material 값은 위반을 반환해야 합니다."""
        garment = _make_invalid_garment(estimated_material="silk")
        state = _make_state([garment])
        violations = verify_vocabulary(state)
        assert any(v.type == "vocab" and "estimated_material" in v.detail for v in violations)

    def test_여러_garment_복수_위반(self):
        """여러 garment에 위반이 있으면 모두 수집해야 합니다."""
        garments = [
            _make_invalid_garment(slot="top", pattern="invalid1"),
            _make_invalid_garment(slot="bottom", pattern="invalid2"),
        ]
        state = _make_state(garments)
        violations = verify_vocabulary(state)
        assert len(violations) == 2

    def test_garment_없으면_위반없음(self):
        """garments가 비어있으면 위반이 없어야 합니다."""
        state = _make_state([])
        assert verify_vocabulary(state) == []

    def test_None_허용_필드는_스킵(self):
        """estimated_material이 None이면 검사를 건너뛰어야 합니다."""
        garment = Garment(
            slot="top",
            category="티셔츠",
            pattern="solid",
            formality_label="casual",
            estimated_material=None,
            confidence=0.9,
            primary_color=PrimaryColor(rgb=[255, 255, 255], name="흰색"),
        )
        state = _make_state([garment])
        assert verify_vocabulary(state) == []


# ──────────────────────────────────────────────
# verify_no_duplicate_slot
# ──────────────────────────────────────────────

class TestVerifyNoDuplicateSlot:

    def test_정상_케이스_위반없음(self):
        """슬롯이 모두 다르면 위반이 없어야 합니다."""
        garments = [
            _make_garment(slot="top"),
            _make_garment(slot="bottom"),
        ]
        state = _make_state(garments)
        assert verify_no_duplicate_slot(state) == []

    def test_슬롯_중복_위반(self):
        """같은 슬롯이 2개이면 위반을 반환해야 합니다."""
        garments = [
            _make_garment(slot="top"),
            _make_garment(slot="top"),
        ]
        state = _make_state(garments)
        violations = verify_no_duplicate_slot(state)
        assert len(violations) == 1
        assert violations[0].type == "duplicate_slot"
        assert violations[0].slot == "top"

    def test_슬롯_3중복_위반(self):
        """같은 슬롯이 3개여도 위반 1건으로 처리해야 합니다."""
        garments = [_make_garment(slot="outer")] * 3
        state = _make_state(garments)
        violations = verify_no_duplicate_slot(state)
        assert len(violations) == 1
        assert "3개" in violations[0].detail

    def test_복수_슬롯_중복(self):
        """2개 슬롯이 각각 중복이면 위반이 2건이어야 합니다."""
        garments = [
            _make_garment(slot="top"),
            _make_garment(slot="top"),
            _make_garment(slot="shoes"),
            _make_garment(slot="shoes"),
        ]
        state = _make_state(garments)
        violations = verify_no_duplicate_slot(state)
        assert len(violations) == 2

    def test_garment_없으면_위반없음(self):
        state = _make_state([])
        assert verify_no_duplicate_slot(state) == []


# ──────────────────────────────────────────────
# verify_color_label_consistency
# ──────────────────────────────────────────────

class TestVerifyColorLabelConsistency:

    def test_정상_케이스_위반없음(self):
        """RGB와 color name이 일치하면 위반이 없어야 합니다."""
        # (255, 255, 255) → "흰색"
        garment = _make_garment(rgb=(255, 255, 255), color_name="흰색")
        state = _make_state([garment])
        assert verify_color_label_consistency(state) == []

    def test_색상_이름_불일치_위반(self):
        """RGB가 '흰색'인데 '검정'으로 기록되면 위반이어야 합니다."""
        garment = _make_garment(rgb=(255, 255, 255), color_name="검정")
        state = _make_state([garment])
        violations = verify_color_label_consistency(state)
        assert len(violations) == 1
        assert violations[0].type == "color_label_mismatch"
        assert violations[0].slot == "top"

    def test_여러_garment_중_일부_불일치(self):
        """일부 garment만 불일치하면 해당 건만 위반이어야 합니다."""
        garments = [
            _make_garment(slot="top", rgb=(255, 255, 255), color_name="흰색"),   # 정상
            _make_garment(slot="bottom", rgb=(0, 0, 0), color_name="흰색"),      # 위반
        ]
        state = _make_state(garments)
        violations = verify_color_label_consistency(state)
        assert len(violations) == 1
        assert violations[0].slot == "bottom"

    def test_pending_색상은_위반(self):
        """overwrite_colors가 실행되지 않아 _pending 상태이면 위반이어야 합니다."""
        garment = Garment(
            slot="top",
            category="티셔츠",
            pattern="solid",
            formality_label="casual",
            confidence=0.9,
            primary_color=PrimaryColor(rgb=[0, 0, 0], name="_pending"),
        )
        state = _make_state([garment])
        violations = verify_color_label_consistency(state)
        # (0, 0, 0) → "검정" ≠ "_pending" 이므로 위반
        assert len(violations) == 1


# ──────────────────────────────────────────────
# verify_schema
# ──────────────────────────────────────────────

class TestVerifySchema:

    def test_정상_케이스_위반없음(self):
        """유효한 Garment는 스키마 위반이 없어야 합니다."""
        state = _make_state([_make_garment()])
        assert verify_schema(state) == []

    def test_여러_garment_모두_정상(self):
        garments = [_make_garment(slot="top"), _make_garment(slot="bottom")]
        state = _make_state(garments)
        assert verify_schema(state) == []


# ──────────────────────────────────────────────
# verify_required_slots
# ──────────────────────────────────────────────

class TestVerifyRequiredSlots:

    def test_모든_필수_슬롯_있음_경고없음(self):
        """top, bottom, shoes가 모두 있으면 경고가 없어야 합니다."""
        garments = [
            _make_garment(slot="top"),
            _make_garment(slot="bottom"),
            _make_garment(slot="shoes"),
        ]
        state = _make_state(garments)
        assert verify_required_slots(state) == []

    def test_shoes_없으면_경고(self):
        """shoes가 없으면 'missing_slot:shoes' 경고가 있어야 합니다."""
        garments = [_make_garment(slot="top"), _make_garment(slot="bottom")]
        state = _make_state(garments)
        warnings = verify_required_slots(state)
        assert "missing_slot:shoes" in warnings

    def test_전체_필수_슬롯_누락(self):
        """필수 슬롯이 모두 없으면 경고 3개가 있어야 합니다."""
        garments = [_make_garment(slot="bag")]
        state = _make_state(garments)
        warnings = verify_required_slots(state)
        assert len(warnings) == 3

    def test_결과가_violations_아닌_warnings(self):
        """verify_required_slots는 Violation이 아닌 str 목록을 반환해야 합니다."""
        garments = [_make_garment(slot="outer")]
        state = _make_state(garments)
        warnings = verify_required_slots(state)
        assert all(isinstance(w, str) for w in warnings)

    def test_garment_없으면_모든_필수_슬롯_누락(self):
        state = _make_state([])
        warnings = verify_required_slots(state)
        assert len(warnings) == 3
