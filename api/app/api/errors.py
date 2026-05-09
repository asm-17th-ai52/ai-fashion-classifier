"""FastAPI exception handlers — converts BackendError + Pydantic validation
into the unified error envelope from docs/specs/07-data-contracts.md §5.4.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import BackendError
from app.core.logging import get_logger
from app.schemas import ErrorBody, ErrorResponse

log = get_logger("backend.errors")


async def backend_error_handler(_: Request, exc: BackendError) -> JSONResponse:
    log.warning(
        "backend_error",
        code=exc.code,
        status=exc.status_code,
        message=exc.user_message,
        details=exc.details,
    )
    body = ErrorResponse(
        error=ErrorBody(
            code=exc.code, message=exc.user_message, details=exc.details or None
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(exclude_none=True),
    )


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    log.warning("validation_error", errors=exc.errors())
    body = ErrorResponse(
        error=ErrorBody(
            code="validation_error",
            message="입력값이 올바르지 않습니다",
            details={"errors": exc.errors()},
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump(exclude_none=True))


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception")
    body = ErrorResponse(
        error=ErrorBody(
            code="internal_error",
            message="서버 오류가 발생했습니다",
            details=None,
        )
    )
    return JSONResponse(status_code=500, content=body.model_dump(exclude_none=True))
