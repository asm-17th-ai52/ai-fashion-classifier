"""Backend runtime configuration. Single source for env-driven knobs."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # External API keys
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # LangSmith (optional)
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="ai-swm-52", alias="LANGCHAIN_PROJECT")

    # Image preprocessing
    image_max_bytes: int = Field(default=10 * 1024 * 1024, alias="IMAGE_MAX_BYTES")
    image_min_bytes: int = Field(default=1, alias="IMAGE_MIN_BYTES")
    image_resize_long_side: int = Field(
        default=1024, alias="IMAGE_RESIZE_LONG_SIDE"
    )
    image_jpeg_quality: int = Field(default=90, alias="IMAGE_JPEG_QUALITY")
    face_blur_sigma: int = Field(default=20, alias="FACE_BLUR_SIGMA")

    # Cache
    session_ttl_seconds: int = Field(default=86400, alias="SESSION_TTL_SECONDS")

    # Rate limit
    rate_limit_per_min: int = Field(default=10, alias="RATE_LIMIT_PER_MIN")
    openai_max_concurrency: int = Field(default=5, alias="OPENAI_MAX_CONCURRENCY")
    tier2_daily_budget: int = Field(default=200, alias="TIER2_DAILY_BUDGET")
    tier2_rpm_limit: int = Field(default=10, alias="TIER2_RPM_LIMIT")

    # CORS
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    # Person detection toggle (allows tests/dev to skip MediaPipe)
    require_person_detection: bool = Field(
        default=True, alias="REQUIRE_PERSON_DETECTION"
    )


settings = Settings()
