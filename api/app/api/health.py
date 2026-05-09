"""GET /v1/health — per spec §4.4."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas import HealthResponse
from app.services.budget import tier2_budget

router = APIRouter(tags=["health"])


@router.get("/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    deps: dict[str, str] = {}
    deps["openai"] = "configured" if settings.openai_api_key else "missing_key"
    deps["langsmith"] = "enabled" if settings.langchain_tracing_v2 else "disabled"
    deps["tier2_budget"] = (
        f"{tier2_budget.snapshot()['daily_count']}/{tier2_budget.daily_cap}"
    )
    return HealthResponse(status="ok", dependencies=deps, version="0.1.0")
