"""
Vision Agent end-to-end 테스트 스크립트.

사용법:
  python3 run_test.py
  python3 run_test.py ../data/test_cases/다른이미지.jpg
"""
import asyncio
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env", override=True)

from app.agents.vision import analyze_outfit

# 인자로 이미지 경로를 받거나, 기본값 사용
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else "../data/test_cases/test_casual.jpg"


async def main():
    with open(IMAGE_PATH, "rb") as f:
        image_bytes = f.read()

    print(f"이미지: {IMAGE_PATH} ({len(image_bytes) / 1024:.1f} KB)")
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
