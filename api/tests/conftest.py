"""Shared pytest fixtures.

We disable MediaPipe-backed person detection for unit tests so they run
without the model files. Integration tests that need real preprocessing
should override the env var explicitly.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image


# Make ``api/`` importable as if uvicorn ran from there, plus the repo root so
# ``agents.<name>`` packages (per 08-roles-and-handoffs §3.3) resolve in tests.
API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (API_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("REQUIRE_PERSON_DETECTION", "false")


@pytest.fixture
def red_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (1200, 800), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
def tiny_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (50, 50), "blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()
