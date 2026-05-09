"""Unit tests for image preprocessing — spec §6 + §11.1."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.errors import ImageInvalidError, ImageTooLargeError
from app.services.preprocess import preprocess_image


def test_preprocess_normalizes_size_and_format(red_jpeg_bytes: bytes) -> None:
    res = preprocess_image(red_jpeg_bytes)
    assert res.image_bytes  # JPEG re-encoded
    assert max(res.width, res.height) <= 1024
    assert res.original_format == "JPEG"


def test_preprocess_resizes_long_side() -> None:
    img = Image.new("RGB", (3000, 1000), "green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    res = preprocess_image(buf.getvalue())
    assert max(res.width, res.height) == 1024


def test_preprocess_accepts_png() -> None:
    img = Image.new("RGB", (800, 600), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    res = preprocess_image(buf.getvalue())
    assert res.original_format == "PNG"


def test_preprocess_rejects_oversize_blob() -> None:
    too_big = b"\xff\xd8\xff\xe0" + b"x" * (11 * 1024 * 1024)
    with pytest.raises(ImageTooLargeError):
        preprocess_image(too_big)


def test_preprocess_rejects_garbage() -> None:
    with pytest.raises(ImageInvalidError):
        preprocess_image(b"not actually an image at all")


def test_preprocess_handles_exif_orientation() -> None:
    """The pipeline must not crash on images without EXIF; rotation handling
    is implicit via ``ImageOps.exif_transpose`` and tested via shape change
    only when EXIF rotation is present. We at minimum confirm the no-EXIF
    happy path completes."""
    img = Image.new("RGB", (1000, 1500), "purple")  # portrait
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    res = preprocess_image(buf.getvalue())
    assert res.height >= res.width  # portrait preserved
