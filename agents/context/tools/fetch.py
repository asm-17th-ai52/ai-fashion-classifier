"""
URL 본문 fetch + 본문 추출 도구 (스펙 §6.2).

- robots.txt 존중 (1h TTL 캐시) — disallow 면 즉시 warning 반환.
- HTML 외 content-type 거부 (PDF/이미지 등 LLM 입력 불가).
- raw HTML 은 메모리 보호용 1 MB 상한 (`MAX_HTML_BYTES`).
- 추출은 ``trafilatura.extract`` (ko 우선, fallback 비활성화 — 노이즈 줄이기).
- spec §6.2 의 "최대 50KB 본문" 은 *추출된 본문* 기준 → 추출 결과를 50KB 로 트림.
  raw HTML 을 50KB 로 트림하면 한국 매거진/블로그의 nav/sidebar 가 앞부분을 차지해
  article body 가 잘리는 문제가 있어 분리한다.

설계 원칙은 다른 Tier-2 도구와 동일: 예외 X, ``(body, warning)`` tuple 반환.
"""
from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

try:
    import trafilatura  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - import-time guard
    trafilatura = None  # type: ignore[assignment]


# 추출된 본문 cap — spec §6.2 의 "최대 50KB 본문".
MAX_BODY_BYTES: int = 50 * 1024

# raw HTML cap — 메모리/대역폭 보호. 50KB 의 nav/script 만으로 본문이 잘리는 사례
# 회피 위해 1 MB 까지 허용 (extract 후 본문이 다시 50KB 로 트림된다).
MAX_HTML_BYTES: int = 1024 * 1024

# robots.txt 캐시 TTL 1h — 재조회 트래픽 최소화.
_ROBOTS_TTL_SECONDS: int = 60 * 60

_USER_AGENT = "AI-Fashion-Classifier/0.1"

# (origin → (RobotFileParser, fetched_at_epoch)) cache.
_robots_cache: dict[str, tuple[RobotFileParser, float]] = {}


def _robots_allowed(url: str) -> tuple[bool, Optional[str]]:
    """robots.txt 캐시 룩업/갱신 후 fetch 허용 여부 반환."""
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False, "fetch_invalid_url"
    if not parsed.scheme or not parsed.hostname:
        return False, "fetch_invalid_url"
    origin = f"{parsed.scheme}://{parsed.hostname}"
    now = time.time()
    cached = _robots_cache.get(origin)
    if cached is None or (now - cached[1]) > _ROBOTS_TTL_SECONDS:
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            parser.read()
        except Exception:  # noqa: BLE001 — robots 조회 실패는 fail-open
            # robots 미존재/네트워크 오류 시 보수적으로 ‘허용’ — Tier-2 차단해도 안 좋음.
            parser = RobotFileParser()
            parser.parse([])
        _robots_cache[origin] = (parser, now)
        cached = (parser, now)
    return cached[0].can_fetch(_USER_AGENT, url), None


def fetch_page(
    url: str,
    timeout: float = 5.0,
) -> tuple[Optional[str], Optional[str]]:
    """URL 을 안전하게 fetch 하고 본문 텍스트만 추출해 반환.

    Args:
        url: 대상 URL. 사전 화이트리스트 검증은 호출 측 책임이지만, 본 함수도
            robots 와 content-type 으로 한 번 더 방어한다.
        timeout: httpx connect+read timeout (초).

    Returns:
        ``(body, warning)``:
            - body: 추출된 한국어 본문. 50KB 초과 시 잘려서 반환되며 warning 에
              ``fetch_partial`` 신호. 호출 측은 ``FetchedPage.partial=True`` 로 기록 권장.
            - warning: 실패/스킵 사유 또는 partial 신호. 정상 시 ``None``.
    """
    if trafilatura is None:
        return None, "trafilatura_not_installed: pip install 'trafilatura[all]'"

    allowed, robots_warn = _robots_allowed(url)
    if robots_warn:
        return None, robots_warn
    if not allowed:
        return None, f"fetch_robots_disallow: {url}"

    headers = {"User-Agent": _USER_AGENT}
    chunks: list[bytes] = []
    received = 0
    html_truncated = False
    try:
        with httpx.stream(
            "GET",
            url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        ) as resp:
            if resp.status_code >= 400:
                return None, f"fetch_http_{resp.status_code}"
            content_type = (resp.headers.get("content-type") or "").lower()
            if "html" not in content_type:
                return None, f"fetch_non_html_content_type: {content_type or 'unknown'}"
            for chunk in resp.iter_bytes(chunk_size=16 * 1024):
                if not chunk:
                    continue
                if received + len(chunk) > MAX_HTML_BYTES:
                    chunks.append(chunk[: MAX_HTML_BYTES - received])
                    received = MAX_HTML_BYTES
                    html_truncated = True
                    break
                chunks.append(chunk)
                received += len(chunk)
    except httpx.HTTPError as exc:
        return None, f"fetch_httpx_error: {type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — 방어적 catch (스트림 중단 등)
        return None, f"fetch_unexpected: {type(exc).__name__}: {exc}"

    html = b"".join(chunks).decode("utf-8", errors="replace")
    body = trafilatura.extract(
        html,
        target_language="ko",
        include_comments=False,
        include_tables=False,
        no_fallback=True,
    )
    if not body:
        return None, "fetch_no_main_content"

    # spec §6.2: "최대 50KB 본문". UTF-8 바이트 기준으로 트림 (멀티바이트 경계 안전).
    body_bytes = body.encode("utf-8")
    if len(body_bytes) > MAX_BODY_BYTES:
        body = body_bytes[:MAX_BODY_BYTES].decode("utf-8", errors="ignore")
        return body, "fetch_partial: body trimmed at 50KB cap"
    if html_truncated:
        # HTML 자체가 1 MB 에 걸려 잘렸음을 호출 측에 알린다 — body 는 정상 추출됐어도
        # 뒷부분 컨텐츠가 누락됐을 가능성 있음.
        return body, "fetch_partial: raw HTML trimmed at 1MB cap"
    return body, None
