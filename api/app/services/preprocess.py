"""Image preprocessing pipeline — per docs/specs/05-backend-spec.md §6.

Steps:
1. MIME / size check (≤ 10MB, jpeg|png)
2. PIL.Image.open + verify (decodable)
3. EXIF orientation normalize (ImageOps.exif_transpose)
4. Person detection via MediaPipe Pose — 400 if missing
5. Face detection + Gaussian blur (MediaPipe Face Detector, σ=20)
6. Resize long-side to 1024px (LANCZOS)
7. Re-encode JPEG quality=90
"""
from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import (
    ImageInvalidError,
    ImageTooLargeError,
    PersonNotDetectedError,
)


@dataclass
class PreprocessResult:
    image_bytes: bytes        # JPEG-encoded, normalized
    width: int
    height: int
    person_detected: bool
    faces_blurred: int
    pose_confidence: float
    original_format: str


# ---------------------------------------------------------------------------
# MediaPipe lazy singletons (heavy to construct; not thread-safe so we lock)
# ---------------------------------------------------------------------------
_pose_lock = threading.Lock()
_face_lock = threading.Lock()
_pose_singleton = None
_face_singleton = None


def _get_pose():
    global _pose_singleton
    if _pose_singleton is None:
        import mediapipe as mp  # local to avoid import cost in tests skipping it

        _pose_singleton = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.4,
        )
    return _pose_singleton


def _get_face_detector():
    global _face_singleton
    if _face_singleton is None:
        import mediapipe as mp

        _face_singleton = mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.4
        )
    return _face_singleton


# ---------------------------------------------------------------------------
# Step 1 — MIME / size check
# ---------------------------------------------------------------------------
ALLOWED_FORMATS = {"JPEG", "PNG"}


def _validate_size(raw: bytes) -> None:
    if len(raw) > settings.image_max_bytes:
        raise ImageTooLargeError()
    if len(raw) < settings.image_min_bytes:
        raise ImageInvalidError("이미지 크기가 너무 작습니다")


# ---------------------------------------------------------------------------
# Step 2-3 — open + EXIF normalize
# ---------------------------------------------------------------------------
def _decode(raw: bytes) -> tuple[Image.Image, str]:
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageInvalidError() from exc
    # verify() consumes; reopen for actual use
    img = Image.open(io.BytesIO(raw))
    fmt = (img.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise ImageInvalidError("JPEG 또는 PNG 이미지만 지원합니다")
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    return img, fmt


# ---------------------------------------------------------------------------
# Step 4 — person detection
# ---------------------------------------------------------------------------
def _detect_person(rgb: np.ndarray) -> tuple[bool, float]:
    """Returns (detected, confidence). Uses MediaPipe Pose visibility avg."""
    if not settings.require_person_detection:
        return True, 1.0
    with _pose_lock:
        try:
            pose = _get_pose()
            result = pose.process(rgb)
        except Exception as exc:  # MediaPipe internal failure — treat as invalid
            raise ImageInvalidError("이미지를 분석할 수 없습니다") from exc
    if not result.pose_landmarks:
        return False, 0.0
    visibilities = [lm.visibility for lm in result.pose_landmarks.landmark]
    if not visibilities:
        return False, 0.0
    conf = float(sum(visibilities) / len(visibilities))
    return conf >= 0.4, conf


# ---------------------------------------------------------------------------
# Step 5 — face blur
# ---------------------------------------------------------------------------
def _blur_faces(img: Image.Image, rgb: np.ndarray) -> tuple[Image.Image, int]:
    if not settings.require_person_detection:
        return img, 0
    with _face_lock:
        result = _get_face_detector().process(rgb)
    if not result.detections:
        return img, 0
    h, w = rgb.shape[:2]
    sigma = settings.face_blur_sigma
    out = img.copy()
    count = 0
    for det in result.detections:
        bbox = det.location_data.relative_bounding_box
        x = max(0, int(bbox.xmin * w))
        y = max(0, int(bbox.ymin * h))
        bw = max(1, int(bbox.width * w))
        bh = max(1, int(bbox.height * h))
        x2 = min(w, x + bw)
        y2 = min(h, y + bh)
        if x2 <= x or y2 <= y:
            continue
        face_region = out.crop((x, y, x2, y2))
        blurred = face_region.filter(ImageFilter.GaussianBlur(radius=sigma))
        out.paste(blurred, (x, y, x2, y2))
        count += 1
    return out, count


# ---------------------------------------------------------------------------
# Step 6 — resize
# ---------------------------------------------------------------------------
def _resize_long_side(img: Image.Image, target: int) -> Image.Image:
    w, h = img.size
    long_side = max(w, h)
    if long_side <= target:
        return img
    scale = target / long_side
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


# ---------------------------------------------------------------------------
# Step 7 — JPEG re-encode
# ---------------------------------------------------------------------------
def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def preprocess_image(raw: bytes) -> PreprocessResult:
    """Run the full pipeline. Raises BackendError subclasses on failure."""
    _validate_size(raw)
    img, fmt = _decode(raw)
    rgb = np.asarray(img)

    detected, conf = _detect_person(rgb)
    if not detected:
        raise PersonNotDetectedError()

    img, faces = _blur_faces(img, rgb)
    img = _resize_long_side(img, settings.image_resize_long_side)
    encoded = _encode_jpeg(img, settings.image_jpeg_quality)
    w, h = img.size
    return PreprocessResult(
        image_bytes=encoded,
        width=w,
        height=h,
        person_detected=True,
        faces_blurred=faces,
        pose_confidence=conf,
        original_format=fmt,
    )
