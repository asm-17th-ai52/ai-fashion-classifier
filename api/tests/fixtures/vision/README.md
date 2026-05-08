# Vision Agent 골든 이미지 픽스처

테스트 실행 전 이 디렉토리에 아래 이미지 5장 배치 필요.
출처: Pexels / Unsplash (무료·상업적 이용 가능)

## 이미지 목록

| 파일명 | 촬영 조건 | 검증 목적 |
|---|---|---|
| `01_casual_basic.jpg` | 흰 티셔츠 + 청바지 + 흰 스니커즈 | 기본 추출, 정상 흐름 |
| `02_contrast_color.jpg` | 흰 셔츠 + 검정 슬랙스 | RGB overwrite 정확도 |
| `03_with_outer.jpg` | 베이지 코트 + 내의 + 하의 | outer 슬롯 감지 |
| `04_pattern_jacket.jpg` | 체크 패턴 재킷 | pattern 필드 정확도 |
| `05_partial_occlusion.jpg` | 하의 명확, 상의 일부 잘림 | warnings 처리 |

## expected.json 작성 필요

각 이미지의 기대 결과를 아래 형식으로 작성.
색상(rgb)은 테스트 실행 시 OpenCV가 자동 측정하므로 생략 가능.

```json
{
  "01_casual_basic": {
    "garment_count": 3,
    "slots": ["top", "bottom", "shoes"],
    "top_pattern": "solid",
    "top_formality": "casual"
  }
}
```

## 이미지 조건

- 형식: JPEG 또는 PNG
- 최소 해상도: 480p (짧은 쪽 기준)
- 권장 해상도: 720p 이상
- 전신 또는 상반신 정면 촬영
