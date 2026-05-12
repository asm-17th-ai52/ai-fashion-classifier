"""
Vision Agent에서 사용하는 데이터 구조(스키마)를 정의하는 파일입니다.

Vision Agent는 이미지를 받아서 의류 정보를 추출하는 AI 에이전트입니다.
이 파일은 그 과정에서 사용되는 모든 데이터의 모양(shape)을 정의합니다.

데이터 흐름:
  이미지 입력 → VisionState (에이전트 내부 상태) → VisionResponse (최종 출력)
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ImageQuality(BaseModel):
    """
    이미지 품질 검증 결과를 담는 구조체입니다.

    예시:
      ImageQuality(resolution_ok=True, frontal=True, occlusion_ratio=0.1)
      → 해상도 OK, 정면 촬영, 10% 가려짐
    """
    resolution_ok: bool      # 이미지 해상도가 충분한지 (최소 480p 이상이면 True)
    frontal: bool = True     # 정면에서 촬영된 이미지인지
    occlusion_ratio: float = 0.0  # 신체가 가려진 비율 (0.0 = 전혀 안 가려짐, 1.0 = 완전히 가려짐)


class PrimaryColor(BaseModel):
    """
    의류의 주요 색상을 담는 구조체입니다.

    rgb: 빨강·초록·파랑 값으로 색상을 표현합니다. 각 값은 0~255 사이의 정수입니다.
    name: 색상의 한글 이름입니다. (예: "네이비", "흰색", "베이지")

    초기값이 [0,0,0] / "_pending"인 이유:
      VLM(AI 모델)이 색상을 추정하는 대신, OpenCV로 실제 픽셀을 분석해서
      덮어쓰기 때문에 처음에는 빈값(placeholder)으로 시작합니다.
    """
    rgb: list[int] = Field(default=[0, 0, 0], min_length=3, max_length=3)
    name: str = "_pending"


class Garment(BaseModel):
    """
    이미지에서 감지된 단일 의류 아이템의 속성 전체를 담는 구조체입니다.

    slot: 의류가 몸의 어느 부위에 착용되는지를 나타냅니다.
      - "top": 상의 (티셔츠, 셔츠 등)
      - "bottom": 하의 (바지, 치마 등)
      - "outer": 아우터 (코트, 자켓 등)
      - "shoes": 신발
      - "bag": 가방
      - "watch": 시계

    confidence: VLM이 이 의류를 얼마나 확신하는지 (0.0~1.0, 높을수록 확실)
    """
    slot: Literal["top", "bottom", "outer", "shoes", "bag", "watch"]
    category: str           # 의류 종류 (예: "티셔츠", "청바지", "스니커즈")
    subcategory: Optional[str] = None  # 세부 종류 (예: "크루넥", "스키니")
    color_hint: Optional[str] = None  # VLM이 추정한 색상 이름 (픽셀 분석 불가 시 fallback으로 사용)
    primary_color: PrimaryColor = Field(default_factory=PrimaryColor)
    secondary_colors: list[PrimaryColor] = []  # 부수적인 색상 목록 (예: 줄무늬의 다른 색)
    pattern: Literal["solid", "stripe", "check", "dot", "graphic", "other"]  # 패턴 종류
    estimated_material: Optional[
        Literal["cotton", "wool", "synthetic", "denim", "leather", "knit", "unknown"]
    ] = None  # 소재 추정값
    fit: Optional[Literal["slim", "regular", "loose", "oversized", "unknown"]] = None  # 핏
    sleeve_length: Optional[Literal["sleeveless", "short", "long", "n/a"]] = None  # 소매 길이
    formality_label: Literal[
        "casual", "smart_casual", "business_casual", "business_formal", "formal"
    ]  # 격식 수준 (casual이 가장 캐주얼, formal이 가장 격식)
    confidence: float = Field(ge=0.0, le=1.0)


class Violation(BaseModel):
    """
    Verifier(검증기)가 발견한 문제를 담는 구조체입니다.

    예시:
      Violation(type="vocab", slot="top", detail="category 값이 허용 목록에 없음")
      Violation(type="duplicate_slot", slot="bottom", detail="bottom 슬롯이 2개 감지됨")
    """
    type: str             # 위반 종류 (예: "vocab", "duplicate_slot", "color_mismatch")
    slot: Optional[str] = None    # 위반이 발생한 슬롯 (예: "top", "shoes")
    detail: Optional[str] = None  # 위반 상세 설명


class ReextractPlan(BaseModel):
    """
    Critic LLM이 생성하는 재추출 계획입니다.
    Verifier가 문제를 발견했을 때, 어떤 슬롯의 어떤 필드를 다시 추출할지 결정합니다.

    give_up=True이면 재추출 없이 현재 결과를 그대로 반환합니다.
    """
    slots: list[str]   # 재추출할 슬롯 목록 (예: ["top", "shoes"])
    fields: list[str]  # 재추출할 필드 목록 (예: ["category", "pattern"])
    reason: str        # 재추출이 필요한 이유 설명
    give_up: bool = False  # True면 재추출 포기, 부분 결과 + warnings 반환


class VisionState(BaseModel):
    """
    LangGraph의 StateGraph가 공유하는 전체 상태(State)입니다.

    Vision Agent의 각 노드(node)는 이 상태를 입력으로 받고,
    변경된 필드만 dict로 반환하면 LangGraph가 자동으로 상태를 업데이트합니다.

    상태 변화 흐름 예시:
      초기 상태: {session_id, image}
      validate_image 실행 후: {quality 추가}
      vlm_extract_all 실행 후: {garments 추가, vlm_calls 증가}
      overwrite_colors 실행 후: {garments의 primary_color 업데이트}
    """
    # 필수 입력값
    session_id: str   # 세션 고유 ID (Backend에서 전달)
    image: bytes      # 전처리된 이미지 바이트 (JPEG/PNG)

    # Step 0: validate_image 노드 결과
    quality: Optional[ImageQuality] = None
    slot_bboxes: dict = {}  # 슬롯별 이미지 영역 좌표 {slot: (x1, y1, x2, y2)}

    # Step 1+: VLM 추출 및 검증 결과
    garments: list[Garment] = []       # 감지된 의류 목록
    violations: list[Violation] = []   # Verifier가 발견한 위반 목록

    # Critic LLM 결과
    reextract_plan: Optional[ReextractPlan] = None
    give_up: bool = False  # True면 현재 garments를 그대로 최종 결과로 사용

    # 관측성(Observability) 메타데이터
    steps_taken: int = 0          # 현재까지 실행된 총 step 수 (최대 3)
    vlm_calls: int = 0            # VLM 호출 횟수 (비용 추적용)
    tool_call_log: list[dict] = []  # 각 도구 호출 기록 (ms, 결과 포함)
    warnings: list[str] = []      # 비치명적 경고 목록 (예: "low_confidence:top")
    error: Optional[str] = None   # 치명적 에러 메시지 (설정 시 Backend로 400 전파)


class VisionResponse(BaseModel):
    """
    Vision Agent가 Backend super-graph에 반환하는 최종 응답입니다.
    07-data-contracts.md §2의 VisionResponse 스키마를 따릅니다.

    agent_meta는 Recommendation Agent가 사용하지 않는 관측성 전용 필드입니다.
    Frontend에서 "정밀 분석 적용" 배지 표시 등에 활용할 수 있습니다.
    """
    session_id: str
    person_detected: bool        # 이미지에서 사람이 감지되었는지
    image_quality: ImageQuality  # 이미지 품질 정보
    garments: list[Garment]      # 감지된 의류 목록
    warnings: list[str]          # 경고 메시지 목록
    agent_meta: dict = {}        # 내부 동작 통계 (steps_taken, vlm_calls 등)
