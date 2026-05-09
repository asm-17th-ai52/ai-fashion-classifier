"""Backend error taxonomy — maps to docs/specs/07-data-contracts.md §5.4."""
from __future__ import annotations

from typing import Optional


class BackendError(Exception):
    """Base class. status_code + machine-readable code + Korean message."""

    status_code: int = 500
    code: str = "internal_error"
    user_message: str = "서버 오류가 발생했습니다."

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message or self.user_message)
        self.details = details or {}
        if message:
            self.user_message = message


class ImageTooLargeError(BackendError):
    status_code = 413
    code = "image_too_large"
    user_message = "10MB 이하 이미지를 사용해 주세요"


class ImageInvalidError(BackendError):
    status_code = 400
    code = "image_invalid"
    user_message = "이미지를 읽을 수 없습니다. 다른 사진으로 다시 업로드해 주세요"


class PersonNotDetectedError(BackendError):
    status_code = 400
    code = "person_not_detected"
    user_message = "사람이 정면으로 보이는 사진으로 다시 업로드해 주세요"


class ValidationError(BackendError):
    status_code = 422
    code = "validation_error"
    user_message = "입력값이 올바르지 않습니다"


class RateLimitedError(BackendError):
    status_code = 429
    code = "rate_limited"
    user_message = "잠시 후 다시 시도해 주세요"


class AgentFailedError(BackendError):
    status_code = 502
    code = "agent_failed"
    user_message = "AI 분석에 실패했습니다. 다시 시도해 주세요"


class SessionNotFoundError(BackendError):
    status_code = 404
    code = "session_not_found"
    user_message = "세션을 찾을 수 없거나 만료되었습니다"
