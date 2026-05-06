# AI Fashion Situation Classifier

착장 이미지와 상황을 입력하면 **면접 / 장례식 / 발표** 상황에 적합한 옷차림인지 **YES / NO**로 판별하는 Vision 기반 Agent.

## 팀원
위승빈, 박상돈, 박현규, 이유리, 이태규

## 기술 스택
- **AI**: GPT-4o Vision (OpenAI API)
- **Backend**: FastAPI
- **판별 방식**: 상황별 rubric 기반 structured output (JSON)

## 지원 상황

| situation | 설명 |
|-----------|------|
| `interview` | 취업 면접 |
| `funeral` | 장례식 / 조문 |
| `presentation` | 사내·학교·컨퍼런스 발표 |

## 디렉토리 구조

```
ai-fashion-classifier/
├── agent/
│   ├── __init__.py
│   ├── classifier.py    # GPT-4o Vision 호출 + 판별 로직
│   └── rubrics.py       # 상황별 드레스코드 기준
├── api/
│   └── main.py          # FastAPI 엔드포인트
├── data/
│   └── test_cases/      # 평가용 이미지 (yes/no 레이블 폴더 구조)
├── eval/
│   └── evaluate.py      # Accuracy 측정 스크립트
├── .env.example
├── requirements.txt
└── README.md
```

## 실행 방법

### 1. 환경 설정
```bash
cp .env.example .env
# .env에 OPENAI_API_KEY 입력
pip install -r requirements.txt
```

### 2. API 서버 실행
```bash
uvicorn api.main:app --reload
```

### 3. API 호출 예시
```bash
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{
    "image": "<base64_encoded_image>",
    "situation": "interview"
  }'
```

응답:
```json
{
  "result": "NO",
  "reason": "청바지와 후드티는 면접 상황에 적합하지 않습니다."
}
```

### 4. 정확도 평가
```
data/test_cases/{situation}/yes/*.jpg  <- 적합 이미지
data/test_cases/{situation}/no/*.jpg   <- 부적합 이미지
```
이미지 배치 후:
```bash
python eval/evaluate.py
```

## API 명세

### `POST /classify`
| 필드 | 타입 | 설명 |
|------|------|------|
| `image` | string | base64 인코딩된 이미지 |
| `situation` | string | `interview` \| `funeral` \| `presentation` |

**Response**
| 필드 | 타입 | 설명 |
|------|------|------|
| `result` | string | `YES` \| `NO` |
| `reason` | string | 판단 근거 (한국어, 30자 이내) |
