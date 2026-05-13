"""
도메인 화이트리스트 / 블록 패턴.

스펙 ``docs/specs/03-agent-context-spec.md`` §6.3 의 trusted 도메인 13 개와 block
패턴을 그대로 옮긴 것. ``url_allowed(url)`` 은 web_search 결과 필터링과
fetch_page 호출 전 검증 두 곳에서 사용된다.

매칭 규칙:
- ``tistory.com`` 같은 멀티테넌트 블로그 호스트는 **suffix 매칭**: ``foo.tistory.com``,
  ``bar.tistory.com`` 모두 허용.
- ``blog.naver.com`` 은 **정확 매칭**: 네이버는 매거진 카테고리만 허용 정책이므로
  서브도메인 확장이 의미 없음 (다른 서브도메인 매칭은 별도 검토).
- ``youtu.be`` 는 ``youtube.com`` 의 short-URL 별칭으로 같이 허용 (자막 추출 도구가
  short-URL 도 video_id 로 정규화하므로 fetch 측 정합).
- 블록 패턴 (``*.adult.*``, ``*shopping*``) 은 **hostname 에만** ``fnmatch`` 적용.
  full URL fnmatch 는 ``tistory.com/post-about-online-shopping`` 같은 정상 글까지
  over-block 하는 부작용이 있어 hostname 으로 한정.
"""
from __future__ import annotations

import fnmatch
from urllib.parse import urlparse


# Suffix-match: 서브도메인까지 허용.
_SUFFIX_DOMAINS: tuple[str, ...] = (
    "brunch.co.kr",
    "tistory.com",
    "velog.io",
    "magazine.hankyung.com",
    "news.naver.com",
    "vogue.co.kr",
    "elle.co.kr",
    "gqkorea.co.kr",
    "jobkorea.co.kr",
    "saramin.co.kr",
    "linkedin.com",
    "youtube.com",
    "youtu.be",  # YouTube short-URL 별칭.
)

# Exact-match: 서브도메인 확장 막음 (정책상 매거진 카테고리 path 만 허용).
_EXACT_DOMAINS: frozenset[str] = frozenset({"blog.naver.com"})

# Tavily / fetch 양쪽에서 사용. 합집합.
ALLOWED_DOMAINS: tuple[str, ...] = tuple(_SUFFIX_DOMAINS) + tuple(_EXACT_DOMAINS)

_BLOCK_PATTERNS: tuple[str, ...] = ("*.adult.*", "*shopping*")


def url_allowed(url: str) -> bool:
    """URL 의 도메인이 화이트리스트에 있고 block 패턴에 안 걸리면 True."""
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False

    # Block 패턴: hostname 만 검사 (URL path 의 “shopping” 단어 over-block 방지).
    for pattern in _BLOCK_PATTERNS:
        if fnmatch.fnmatchcase(host, pattern):
            return False

    # Exact 매칭 우선 (blog.naver.com 등).
    if host in _EXACT_DOMAINS:
        return True

    # Suffix 매칭 (``foo.tistory.com`` ⊂ ``tistory.com``).
    for domain in _SUFFIX_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True

    return False
