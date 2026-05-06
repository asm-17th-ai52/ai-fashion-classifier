import base64
import json
from openai import OpenAI
from .rubrics import RUBRICS

client = OpenAI()

SYSTEM_PROMPT = """You are a fashion appropriateness classifier.
You will be given an outfit image and a situation.
You must answer ONLY in the following JSON format, nothing else:
{"result": "YES" | "NO", "reason": "<one sentence in Korean>"}

- YES means the outfit is appropriate for the situation.
- NO means it is not appropriate.
- Keep the reason concise (under 30 words in Korean).
- Base your judgment strictly on the rubric provided."""


def build_user_prompt(situation: str) -> str:
    rubric = RUBRICS[situation]
    required = "\n".join(f"  - {r}" for r in rubric["required"])
    forbidden = "\n".join(f"  - {f}" for f in rubric["forbidden"])
    return f"""상황: {rubric['name']} ({rubric['description']})

[판단 기준]
적합 요소:
{required}

부적합 요소:
{forbidden}

위 기준에 따라 이미지 속 착장이 해당 상황에 적합한지 YES 또는 NO로 판단하세요."""


def classify(image_base64: str, situation: str) -> dict:
    """
    이미지와 상황을 받아 착장 적합도를 YES/NO로 반환.
    image_base64: base64 인코딩된 이미지 문자열
    situation: "interview" | "funeral" | "presentation"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "low",
                        },
                    },
                    {"type": "text", "text": build_user_prompt(situation)},
                ],
            },
        ],
        max_tokens=200,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)

    if result.get("result") not in ("YES", "NO"):
        raise ValueError(f"Unexpected result value: {result}")

    return result
