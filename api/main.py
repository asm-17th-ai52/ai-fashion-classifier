import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal
from agent import classify, VALID_SITUATIONS

app = FastAPI(title="AI Fashion Situation Classifier")


class ClassifyRequest(BaseModel):
    image: str  # base64 encoded
    situation: Literal["interview", "funeral", "presentation"]


class ClassifyResponse(BaseModel):
    result: Literal["YES", "NO"]
    reason: str


@app.post("/classify", response_model=ClassifyResponse)
async def classify_outfit(request: ClassifyRequest):
    if request.situation not in VALID_SITUATIONS:
        raise HTTPException(status_code=400, detail=f"situation must be one of {VALID_SITUATIONS}")

    try:
        result = classify(request.image, request.situation)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ClassifyResponse(**result)


@app.get("/health")
async def health():
    return {"status": "ok"}
