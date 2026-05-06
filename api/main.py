"""FastAPI entry point for the Backend service.

Per docs/specs/05-backend-spec.md. Run with::

    uvicorn main:app --reload --port 8000

(executed from the ``api/`` directory; the .venv there has all deps.)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import (
    backend_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.core.config import settings
from app.core.errors import BackendError
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="AI 패션 상황 추천 — Backend",
        version="0.1.0",
        description=(
            "Vision/Context/Recommendation Agent를 LangGraph super-graph로 "
            "오케스트레이션하는 API Gateway."
        ),
    )

    cors_origins = (
        ["*"] if settings.cors_origins.strip() == "*"
        else [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(sessions_router)
    app.include_router(health_router)

    app.add_exception_handler(BackendError, backend_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    return app


app = create_app()
