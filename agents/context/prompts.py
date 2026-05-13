"""
Tier-2 ReAct 루프의 LLM 프롬프트 텍스트 모음.

본 파일은 ``nodes/plan_query.py`` 와 ``nodes/extract_facts.py`` 가 사용하는
시스템 / 유저 프롬프트 템플릿을 한 곳에서 관리한다. spec §6.4 (검색 쿼리 템플릿
강제) + spec §6.5 (extract_facts schema 강제 + 금지 단어 명시).
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Planner (search query generator)
# ---------------------------------------------------------------------------

# 자유 작문은 환각 + 무관 쿼리 위험. spec §6.4 의 4 템플릿 슬롯 채우기로 강제.
PLANNER_SYSTEM = """당신은 한국 드레스코드 정보를 찾기 위한 웹 검색 쿼리 생성기입니다.

사용 가능한 쿼리 템플릿은 정확히 4 개이며, 그 중 하나의 인덱스를 골라 슬롯을
채워야 합니다. 자유 작문 / 새로운 템플릿 생성 / 영어 키워드 단독 사용은 금지됩니다.

템플릿 (인덱스 0~3):
0. "한국 {event_type} 드레스코드"
1. "{event_type} 복장 가이드 한국"
2. "{event_type} {season} 옷차림"
3. "{event_type} 추천 복장"

규칙:
- ``event_type`` 은 입력으로 받은 한국어 자연어 문구 (예: "회사 송년회", "결혼식 하객") 그대로 사용.
- ``season`` 은 템플릿 2 를 선택했을 때만 한국어로 "봄"/"여름"/"가을"/"겨울" 중 하나를 채우고,
  나머지 템플릿에서는 **빈 문자열 ``""``**. (schema 가 ``str`` 이라 ``null`` 은 허용되지 않음 —
  ``Optional[str]`` 가 일부 google-genai SDK 버전에서 비호환이라 단순 ``str`` 로 통일.)
- ``reasoning`` 은 1~2 문장 한국어로 짧게.
- 이전 라운드에서 이미 사용된 쿼리를 반복하지 말 것 (입력 ``used_queries`` 확인).
- JSON 으로만 응답하며 schema 를 정확히 따른다."""


def build_planner_user(
    event_type: str,
    used_queries: list[str],
    fetched_summaries: list[str],
) -> str:
    """현재 라운드 입력을 planner LLM 메시지로 직렬화."""
    used = "\n".join(f"- {q}" for q in used_queries) or "- (없음)"
    summaries = "\n".join(f"- {s}" for s in fetched_summaries) or "- (없음)"
    return (
        f"event_type: {event_type}\n\n"
        f"이미 사용된 쿼리:\n{used}\n\n"
        f"지금까지 fetch 한 페이지 요약 (제목/도메인만):\n{summaries}\n\n"
        f"위 정보를 참고해 다음 검색 쿼리 1 개를 생성하세요."
    )


# ---------------------------------------------------------------------------
# Extractor (page → ExtractedFacts schema)
# ---------------------------------------------------------------------------

# 본문에서 정량 지표만 추출하도록 강하게 제약. spec §6.5 + §4.1 금지어.
EXTRACTOR_SYSTEM = """당신은 한국 드레스코드 관련 글에서 정량 지표를 추출하는 추출기입니다.

응답은 반드시 주어진 JSON schema 를 따르며, 모든 필드를 채워야 합니다.

추출 규칙:
- ``expected_formality_range`` : 0~100 정수 2 개 [min, max], min ≤ max.
  격식 표현 (예: "정장", "비즈니스 캐주얼", "캐주얼") 을 다음 매핑으로 정량화:
    formal ≈ 90-100, business_formal ≈ 80-95, business_casual ≈ 60-80,
    smart_casual ≈ 40-65, casual ≈ 10-45.
- ``expected_categories`` : top/bottom/outer/shoes 각 슬롯에 한국어 카테고리만.
  허용 vocab: 셔츠, 블라우스, 니트, 티셔츠, 후드티, 드레스, 슬랙스, 치마, 치노,
  청바지, 반바지, 블레이저, 자켓, 가디건, 구두, 로퍼, 스니커즈.
- ``color_guidance.preferred_tones`` / ``avoid_tones`` : 한국어 색상명만.
  (예: 흰색, 검정, 네이비, 베이지, 회색, 진회색, 빨강, 노랑, 핑크 등.)
- ``evidence_quotes`` : 본문에서 실제로 등장한 한국어 인용 1~3 개. 각 인용은 500자
  이내, ``url`` 과 ``fetched_at`` 를 함께 제공 (입력에 주어진 값 그대로).
- ``extraction_confidence`` : 0.0~1.0. 본문이 모호하거나 드레스코드 정보가
  적으면 낮게, 명확하면 높게. 0.5 미만이면 결과가 폐기되니 솔직하게 표기.

금지어 (인용/주관 표현 모두 사용 금지):
매력, 매력적, 호감, 호감도, 인상, 성격, 신뢰감, 어울리는 사람,
잘생, 예쁘, 멋지, 세련, 촌스러, 평범, 체형, 몸매.

본문에 위 단어가 포함돼 있어도 ``evidence_quotes`` 에서는 그 문장을 제외하고
다른 사실 기반 문장을 인용하세요. 추출하지 못하면 ``extraction_confidence`` 를
낮추어 보고하세요."""


def build_extractor_user(
    event_type: str,
    url: str,
    fetched_at_iso: str,
    body: str,
) -> str:
    """추출기 LLM 유저 메시지 — page body 와 메타데이터를 함께 전달."""
    return (
        f"event_type: {event_type}\n"
        f"source_url: {url}\n"
        f"fetched_at: {fetched_at_iso}\n\n"
        f"본문:\n{body}\n\n"
        f"위 본문에서 schema 에 정확히 맞는 ExtractedFacts JSON 을 생성하세요."
    )
