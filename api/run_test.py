"""
Vision Agent end-to-end 테스트 스크립트.

사용법:
  python3 run_test.py                                     # 기본 로컬 이미지
  python3 run_test.py ../data/test_cases/다른이미지.jpg   # 로컬 파일 경로
  python3 run_test.py https://example.com/outfit.jpg     # 웹 이미지 URL
"""
import asyncio
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env", override=True)

import httpx
from app.agents.vision import analyze_outfit

DEFAULT_IMAGE = "../data/test_cases/test_casual.jpg"
SOURCE = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAGE


def _load_image(source: str) -> tuple[bytes, str]:
    """
    로컬 경로 또는 URL에서 이미지 바이트를 불러옵니다.
    Returns: (image_bytes, label) - label은 로그 출력용 식별자
    """
    if source.startswith("http://") or source.startswith("https://"):
        response = httpx.get(source, follow_redirects=True, timeout=15)
        response.raise_for_status()
        return response.content, source
    else:
        with open(source, "rb") as f:
            return f.read(), source


async def main():
    image_bytes, label = _load_image(SOURCE)

    print(f"이미지: {label} ({len(image_bytes) / 1024:.1f} KB)")
    print("분석 중...\n")

    result = await analyze_outfit(session_id="test-001", image_bytes=image_bytes)

    print(f"=== 결과 ===")
    print(f"image_quality: {result.image_quality}")
    print(f"vlm_calls: {result.agent_meta['vlm_calls']}, steps_taken: {result.agent_meta['steps_taken']}")
    print(f"warnings: {result.warnings}\n")

    print(f"감지된 의류 ({len(result.garments)}개):")
    for g in result.garments:
        print(f"  [{g.slot}] {g.category} | 패턴: {g.pattern} | 격식: {g.formality_label} | 색상: {g.primary_color.name} {g.primary_color.rgb} | confidence: {g.confidence:.2f}")


asyncio.run(main())
