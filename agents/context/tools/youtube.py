"""
YouTube 자막 추출 도구 (스펙 §6.2).

- URL 에서 video_id 정규식 추출 (`v=`, `youtu.be/`, `/shorts/` 패턴 지원).
- ``youtube_transcript_api`` 로 ko 자막 우선, 없으면 en. 영상 자체는 다운로드 X.
- 비-YouTube URL / 영상 ID 추출 실패 시 None + warning.
- 모든 도구 함수와 동일: 예외 X, ``(transcript, warning)`` tuple.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (  # type: ignore[import-untyped]
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )
    # IP/요청 차단 — 1.x 부터 도입. 구버전에서는 import 실패해서 fallback.
    try:
        from youtube_transcript_api._errors import (  # type: ignore[import-untyped]
            IpBlocked,
            RequestBlocked,
        )
    except ImportError:  # pragma: no cover - 구버전 youtube_transcript_api
        IpBlocked = RequestBlocked = Exception  # type: ignore[assignment, misc]
except ImportError:  # pragma: no cover - import-time guard
    YouTubeTranscriptApi = None  # type: ignore[assignment, misc]
    NoTranscriptFound = TranscriptsDisabled = VideoUnavailable = Exception  # type: ignore[assignment, misc]
    IpBlocked = RequestBlocked = Exception  # type: ignore[assignment, misc]


# `/shorts/<id>` 또는 `/embed/<id>` 패스에서 video_id 추출용.
_PATH_VIDEO_ID_RE = re.compile(r"/(?:shorts|embed)/([A-Za-z0-9_-]{11})")


def _extract_video_id(url: str) -> Optional[str]:
    """다양한 YouTube URL 포맷에서 11자 video_id 추출. 매칭 실패 시 None."""
    if not isinstance(url, str) or not url:
        return None
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return None
    host = (parsed.hostname or "").lower()
    if host not in {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}:
        return None

    # youtu.be/<id>
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate if len(candidate) == 11 else None

    # youtube.com/watch?v=<id>
    qs = parse_qs(parsed.query or "")
    vid = qs.get("v", [None])[0]
    if vid and len(vid) == 11:
        return vid

    # youtube.com/shorts/<id> or /embed/<id>
    match = _PATH_VIDEO_ID_RE.search(parsed.path or "")
    if match:
        return match.group(1)
    return None


def fetch_transcript(url: str) -> tuple[Optional[str], Optional[str]]:
    """YouTube URL 의 자막을 한 줄로 합쳐 반환.

    Returns:
        ``(transcript_text, warning)``:
            - transcript_text: 자막 segment 의 ``text`` 를 공백으로 join 한 결과.
              실패 시 ``None``.
            - warning: 실패 사유. 정상 시 ``None``.
    """
    if YouTubeTranscriptApi is None:
        return None, "youtube_transcript_api_not_installed"

    vid = _extract_video_id(url)
    if vid is None:
        return None, "youtube_invalid_url_or_video_id"

    try:
        api = YouTubeTranscriptApi()
        # ko 자막 우선, 없으면 en (auto-generated 포함).
        transcript = api.fetch(vid, languages=["ko", "en"])
    except (RequestBlocked, IpBlocked) as exc:
        # YouTube 가 본 IP 를 차단했거나 요청 빈도 제한에 걸린 경우 — 별도 시그널
        # 로 분리해 호출 측이 즉시 Tier-2 fallback 으로 회피하기 쉽게 한다.
        return None, f"youtube_ip_blocked: {type(exc).__name__}"
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as exc:
        return None, f"youtube_transcript_unavailable: {type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001 — 네트워크/SDK 변경 등 방어적 catch
        return None, f"youtube_unexpected: {type(exc).__name__}: {exc}"

    segments = getattr(transcript, "snippets", None) or list(transcript)
    text_parts: list[str] = []
    for seg in segments:
        if isinstance(seg, dict):
            chunk = seg.get("text") or ""
        else:
            chunk = getattr(seg, "text", "") or ""
        if chunk:
            text_parts.append(str(chunk).strip())
    body = " ".join(p for p in text_parts if p)
    if not body:
        return None, "youtube_empty_transcript"
    return body, None
