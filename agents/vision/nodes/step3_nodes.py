"""
Step 3 노드: Critic LLM + Targeted Re-extract.

실행 순서:
  1. node_critic_llm: Verifier 위반 목록을 분석해 재추출 계획(ReextractPlan)을 수립합니다.
  2. node_vlm_extract_targeted: Critic이 지정한 슬롯만 크롭 이미지로 재추출합니다.

node_vlm_extract_targeted 완료 후에는 overwrite_colors → run_verifiers로
다시 라우팅되어 사이클이 형성됩니다.
사이클 종료 조건: violations 없음 또는 state.steps_taken >= 3.
"""
import base64
import json
import time
import structlog
from pydantic import BaseModel

from google.genai import types

from ..state import VisionState, Garment, PrimaryColor, ReextractPlan, Violation
from ..tools.clip_image import clip_image_by_slot
from ..prompts import SYSTEM_PROMPT_CRITIC, build_targeted_user_prompt
from .step1_nodes import (
    _build_client,
    _image_to_base64,
    _GarmentVLMOutput,
    GEMINI_MODEL,
)


# ──────────────────────────────────────────────
# Critic LLM 응답 스키마
# ──────────────────────────────────────────────

log = structlog.get_logger("vision.step3")


class _ReextractPlanOutput(BaseModel):
    """Critic LLM이 반환하는 재추출 계획."""
    slots: list[str]
    fields: list[str]
    reason: str
    give_up: bool = False


# ──────────────────────────────────────────────
# Step 3-A: Critic LLM 노드
# ──────────────────────────────────────────────

def node_critic_llm(state: VisionState) -> dict:
    """
    Verifier가 발견한 violations를 분석해 재추출 계획을 수립합니다.

    - violations 목록과 현재 garments를 Gemini에 전달합니다.
    - 응답으로 ReextractPlan을 받아 state에 저장합니다.
    - Critic 호출 실패 시 give_up=True로 fallback합니다.

    업데이트 필드: reextract_plan, give_up, warnings, tool_call_log
    """
    client = _build_client()

    violations_data = [v.model_dump() for v in state.violations]
    garments_data = [g.model_dump() for g in state.garments]

    user_content = (
        f"Violations found:\n{json.dumps(violations_data, ensure_ascii=False, indent=2)}\n\n"
        f"Current garment extractions:\n{json.dumps(garments_data, ensure_ascii=False, indent=2)}\n\n"
        "Generate a re-extraction plan."
    )

    contents = [types.Content(parts=[types.Part(text=f"{SYSTEM_PROMPT_CRITIC}\n\n{user_content}")])]
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_ReextractPlanOutput,
        temperature=0,
    )

    start = time.time()
    plan: _ReextractPlanOutput | None = None
    error: str | None = None

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=contents, config=config
        )
        plan = _ReextractPlanOutput.model_validate_json(response.text)
    except Exception as e:
        error = f"Critic LLM 호출 실패: {e}"

    elapsed_ms = int((time.time() - start) * 1000)

    if error or plan is None:
        log.warning("vision_critic_done", success=False, latency_ms=elapsed_ms, error=error)
        return {
            "give_up": True,
            "warnings": state.warnings + ["critic_failed"],
            "tool_call_log": state.tool_call_log + [
                {"tool": "critic_llm", "ms": elapsed_ms, "success": False}
            ],
        }

    reextract_plan = ReextractPlan(
        slots=plan.slots,
        fields=plan.fields,
        reason=plan.reason,
        give_up=plan.give_up,
    )

    new_warnings = list(state.warnings)
    if plan.give_up:
        new_warnings.append("critic_give_up")
        log.warning("vision_critic_done", success=True, give_up=True, latency_ms=elapsed_ms)
    else:
        log.info("vision_critic_done", success=True, give_up=False, reextract_slots=plan.slots, reason=plan.reason, latency_ms=elapsed_ms)

    return {
        "reextract_plan": reextract_plan,
        "give_up": plan.give_up,
        "warnings": new_warnings,
        "tool_call_log": state.tool_call_log + [
            {
                "tool": "critic_llm",
                "ms": elapsed_ms,
                "success": True,
                "plan": plan.model_dump(),
            }
        ],
    }


# ──────────────────────────────────────────────
# Step 3-B: Targeted Re-extract 노드
# ──────────────────────────────────────────────

def node_vlm_extract_targeted(state: VisionState) -> dict:
    """
    Critic이 지정한 슬롯을 크롭 이미지로 재추출합니다.

    - reextract_plan.slots에 있는 슬롯만 처리합니다.
    - 각 슬롯을 clip_image_by_slot으로 크롭한 뒤 VLM에 단일 garment로 추출합니다.
    - VLM 실패 시 해당 슬롯은 원본 garment를 유지합니다.
    - 완료 후 violations를 초기화합니다 (run_verifiers가 새로 실행되므로).

    업데이트 필드: garments, violations, vlm_calls, steps_taken, tool_call_log
    """
    if not state.reextract_plan:
        return {}

    client = _build_client()
    target_slots = set(state.reextract_plan.slots)

    garment_map: dict[str, Garment] = {g.slot: g for g in state.garments}

    log_entries = []
    vlm_calls_delta = 0

    for slot in target_slots:
        if slot not in garment_map:
            continue

        prev_garment = garment_map[slot]
        violations_for_slot = [
            v.model_dump() for v in state.violations if v.slot == slot
        ]

        cropped_bytes = clip_image_by_slot(state.image, slot)
        b64, mime = _image_to_base64(cropped_bytes)

        user_prompt = build_targeted_user_prompt(
            slot=slot,
            prev_garment=prev_garment.model_dump(),
            violations=violations_for_slot,
        )

        contents = [types.Content(parts=[
            types.Part(inline_data=types.Blob(mime_type=mime, data=base64.b64decode(b64))),
            types.Part(text=user_prompt),
        ])]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_GarmentVLMOutput,
            temperature=0,
        )

        start = time.time()
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config
            )
            new_output: _GarmentVLMOutput = _GarmentVLMOutput.model_validate_json(response.text)

            # VLM이 다른 slot을 반환할 수 있으므로 slot을 강제 고정합니다.
            updated = Garment(
                slot=slot,
                category=new_output.category,
                subcategory=new_output.subcategory,
                color_hint=new_output.color_hint,
                pattern=new_output.pattern,
                estimated_material=new_output.estimated_material,
                fit=new_output.fit,
                sleeve_length=new_output.sleeve_length,
                formality_label=new_output.formality_label,
                confidence=new_output.confidence,
                primary_color=PrimaryColor(rgb=[0, 0, 0], name="_pending"),
            )
            garment_map[slot] = updated
            vlm_calls_delta += 1

            log_entries.append({
                "tool": "vlm_extract_targeted",
                "slot": slot,
                "ms": int((time.time() - start) * 1000),
                "success": True,
            })
        except Exception as e:
            log_entries.append({
                "tool": "vlm_extract_targeted",
                "slot": slot,
                "ms": int((time.time() - start) * 1000),
                "success": False,
                "error": str(e),
            })

    # 원본 순서를 유지하면서 garments를 재조립합니다.
    updated_garments = [garment_map[g.slot] for g in state.garments]

    success_slots = [e["slot"] for e in log_entries if e.get("success")]
    failed_slots = [e["slot"] for e in log_entries if not e.get("success")]
    log.info("vision_reextract_done", success_slots=success_slots, failed_slots=failed_slots, vlm_calls=vlm_calls_delta)

    return {
        "garments": updated_garments,
        "violations": [],  # run_verifiers가 새로 실행되므로 초기화합니다.
        "vlm_calls": state.vlm_calls + vlm_calls_delta,
        "steps_taken": state.steps_taken + 1,
        "tool_call_log": state.tool_call_log + log_entries,
    }
