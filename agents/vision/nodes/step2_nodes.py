"""
Step 2 노드: 결정적 Verifier 5종.

VLM이 추출한 garments를 결정적 규칙으로 검증합니다.
LLM과 달리 같은 입력에 항상 같은 결과를 반환합니다.

Verifier 목록:
  1. verify_vocabulary       — enum 필드 값이 허용 목록 안에 있는지 확인
  2. verify_no_duplicate_slot — 같은 슬롯이 2개 이상 감지되지 않았는지 확인
  3. verify_color_label_consistency — RGB 값과 한글 색상 이름이 일치하는지 확인
  4. verify_schema           — Pydantic 스키마 검증 (VisionState 전체)
  5. verify_required_slots   — 필수 슬롯(top, bottom, shoes)이 있는지 확인
                               (위반 시 violations가 아닌 warnings에 추가)
"""
from collections import Counter
import structlog

from ..state import VisionState, Violation
from ..tools.color_lookup import rgb_to_korean_name

log = structlog.get_logger("vision.step2")


# ──────────────────────────────────────────────
# 어휘(vocab) 화이트리스트
# Garment 스키마의 Literal 값과 동기화해야 합니다.
# ──────────────────────────────────────────────

_ALLOWED_PATTERNS = {"solid", "stripe", "check", "dot", "graphic", "other"}
_ALLOWED_MATERIALS = {"cotton", "wool", "synthetic", "denim", "leather", "knit", "unknown"}
_ALLOWED_FITS = {"slim", "regular", "loose", "oversized", "unknown"}
_ALLOWED_SLEEVE_LENGTHS = {"sleeveless", "short", "long", "n/a"}
_ALLOWED_FORMALITY = {"casual", "smart_casual", "business_casual", "business_formal", "formal"}

# 기본 필수 슬롯: 누락 시 warning을 추가합니다 (violation이 아님).
_REQUIRED_SLOTS = {"top", "bottom", "shoes"}


# ──────────────────────────────────────────────
# Verifier 1: 어휘 검증
# ──────────────────────────────────────────────

def verify_vocabulary(state: VisionState) -> list[Violation]:
    """
    각 garment의 enum 필드 값이 허용 목록 안에 있는지 확인합니다.

    Pydantic이 VLM 응답 파싱 시 이미 검증하지만,
    이후 코드에서 garment가 직접 수정될 경우를 대비한 방어 레이어입니다.

    Returns:
      위반 목록. 정상이면 빈 리스트.
    """
    violations = []

    for garment in state.garments:
        slot = garment.slot

        if garment.pattern not in _ALLOWED_PATTERNS:
            violations.append(Violation(
                type="vocab",
                slot=slot,
                detail=f"pattern='{garment.pattern}'은 허용 값이 아닙니다: {_ALLOWED_PATTERNS}",
            ))

        if garment.estimated_material and garment.estimated_material not in _ALLOWED_MATERIALS:
            violations.append(Violation(
                type="vocab",
                slot=slot,
                detail=f"estimated_material='{garment.estimated_material}'은 허용 값이 아닙니다: {_ALLOWED_MATERIALS}",
            ))

        if garment.fit and garment.fit not in _ALLOWED_FITS:
            violations.append(Violation(
                type="vocab",
                slot=slot,
                detail=f"fit='{garment.fit}'은 허용 값이 아닙니다: {_ALLOWED_FITS}",
            ))

        if garment.sleeve_length and garment.sleeve_length not in _ALLOWED_SLEEVE_LENGTHS:
            violations.append(Violation(
                type="vocab",
                slot=slot,
                detail=f"sleeve_length='{garment.sleeve_length}'은 허용 값이 아닙니다: {_ALLOWED_SLEEVE_LENGTHS}",
            ))

        if garment.formality_label not in _ALLOWED_FORMALITY:
            violations.append(Violation(
                type="vocab",
                slot=slot,
                detail=f"formality_label='{garment.formality_label}'은 허용 값이 아닙니다: {_ALLOWED_FORMALITY}",
            ))

    return violations


# ──────────────────────────────────────────────
# Verifier 2: 슬롯 중복 검증
# ──────────────────────────────────────────────

def verify_no_duplicate_slot(state: VisionState) -> list[Violation]:
    """
    같은 슬롯에 2개 이상의 garment가 감지되었는지 확인합니다.

    예시: "top" 슬롯이 2개이면 → violation.

    Returns:
      위반 목록. 정상이면 빈 리스트.
    """
    slot_counts = Counter(g.slot for g in state.garments)
    violations = []

    for slot, count in slot_counts.items():
        if count > 1:
            violations.append(Violation(
                type="duplicate_slot",
                slot=slot,
                detail=f"'{slot}' 슬롯이 {count}개 감지되었습니다. 1개만 허용됩니다.",
            ))

    return violations


# ──────────────────────────────────────────────
# Verifier 3: 색상 라벨 일치 검증
# ──────────────────────────────────────────────

def verify_color_label_consistency(state: VisionState) -> list[Violation]:
    """
    primary_color.rgb 값을 color_lookup 테이블로 변환했을 때
    primary_color.name과 일치하는지 확인합니다.

    일치하지 않으면 overwrite_colors 단계의 버그를 시사합니다.

    Returns:
      위반 목록. 정상이면 빈 리스트.
    """
    violations = []

    for garment in state.garments:
        rgb = tuple(garment.primary_color.rgb)
        expected_name = rgb_to_korean_name(rgb)  # type: ignore[arg-type]

        if expected_name != garment.primary_color.name:
            violations.append(Violation(
                type="color_label_mismatch",
                slot=garment.slot,
                detail=(
                    f"RGB{rgb} → '{expected_name}'이어야 하나 "
                    f"'{garment.primary_color.name}'으로 기록됨"
                ),
            ))

    return violations


# ──────────────────────────────────────────────
# Verifier 4: 스키마 검증
# ──────────────────────────────────────────────

def verify_schema(state: VisionState) -> list[Violation]:
    """
    garments 전체가 Pydantic 스키마를 준수하는지 검증합니다.

    VLM 파싱 시점에 이미 검증되지만, Targeted Re-extract 이후
    garments가 재조립될 때 발생할 수 있는 스키마 이탈을 잡습니다.

    Returns:
      위반 목록. 정상이면 빈 리스트.
    """
    from pydantic import ValidationError
    from ..state import Garment

    violations = []
    for garment in state.garments:
        try:
            # model_validate를 이용해 현재 garment 값을 재검증합니다.
            Garment.model_validate(garment.model_dump())
        except ValidationError as e:
            violations.append(Violation(
                type="schema",
                slot=garment.slot,
                detail=str(e),
            ))

    return violations


# ──────────────────────────────────────────────
# Verifier 5: 필수 슬롯 확인 (→ warning, violation 아님)
# ──────────────────────────────────────────────

def verify_required_slots(state: VisionState) -> list[str]:
    """
    기본 필수 슬롯(top, bottom, shoes)이 모두 감지되었는지 확인합니다.

    누락 시 violation이 아닌 warning 문자열을 반환합니다.
    (재촬영 권장 안내용 — 강제 재추출 대상이 아님)

    Returns:
      경고 문자열 목록. 예: ["missing_slot:shoes"]
    """
    detected_slots = {g.slot for g in state.garments}
    warnings = []

    for slot in _REQUIRED_SLOTS:
        if slot not in detected_slots:
            warnings.append(f"missing_slot:{slot}")

    return warnings


# ──────────────────────────────────────────────
# Step 2 노드: 모든 Verifier 일괄 실행
# ──────────────────────────────────────────────

def node_run_verifiers(state: VisionState) -> dict:
    """
    5종 Verifier를 순서대로 실행하고 violations와 warnings를 수집합니다.

    violations가 비어있으면 그래프가 END로 라우팅됩니다.
    violations가 있으면 Step 3 Critic LLM으로 라우팅됩니다. (TODO: Step 3)

    업데이트 필드: violations, warnings, tool_call_log
    """
    all_violations: list = []
    new_warnings: list[str] = []
    log_entries = []

    # 각 verifier를 실행하고 결과를 수집합니다.
    for fn, label in [
        (verify_vocabulary,            "verify_vocabulary"),
        (verify_no_duplicate_slot,     "verify_no_duplicate_slot"),
        (verify_color_label_consistency, "verify_color_label_consistency"),
        (verify_schema,                "verify_schema"),
    ]:
        result = fn(state)
        passed = len(result) == 0
        log_entries.append({
            "tool": label,
            "passed": passed,
            "violation_count": len(result),
        })
        all_violations.extend(result)

    # verify_required_slots는 violations가 아닌 warnings를 반환합니다.
    slot_warnings = verify_required_slots(state)
    new_warnings.extend(slot_warnings)
    log_entries.append({
        "tool": "verify_required_slots",
        "passed": len(slot_warnings) == 0,
        "warnings": slot_warnings,
    })

    if all_violations:
        log.warning(
            "vision_verify_done",
            passed=False,
            violation_count=len(all_violations),
            violation_types=list({v.type for v in all_violations}),
            violation_slots=list({v.slot for v in all_violations}),
            warning_count=len(new_warnings),
        )
    else:
        log.info("vision_verify_done", passed=True, violation_count=0, warning_count=len(new_warnings))

    return {
        "violations": all_violations,
        "warnings": state.warnings + new_warnings,
        "tool_call_log": state.tool_call_log + log_entries,
    }
