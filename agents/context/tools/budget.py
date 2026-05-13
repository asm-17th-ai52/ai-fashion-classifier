"""
Tier-2 비용/속도 카운터 (스펙 §6.8).

일일 글로벌 상한 (200 Tier-2 호출/일) 을 관리한다. 카운터는
``agents/context/data/tier2_budget.json`` 에 UTC 일자별로 누적되며,
파일 부재/손상 시 자동 재생성된다.

본 모듈은 **프로세스 외부 (외부 API 비용)** 의 자원을 보호하므로,
프로세스 간 race condition 을 줄이기 위해 atomic write (tmp → ``os.replace``) 를 사용한다.
멀티 프로세스 동시 쓰기에서 마지막 writer 의 값으로 덮어쓰이는 안전한 손실은 허용 — 비용
제어이지 정합성 요구 사항이 아니므로 OK.

상한:
- ``web_search`` 호출: spec §6.8 에 "1 요청당 최대 3회" — 본 모듈은 글로벌 일일 한도
  위주 관리. 요청 단위 카운터는 LangGraph state 가 다룸.
- 본 모듈의 일일 글로벌 상한 = web_search + fetch_page + react_step 의 합.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# 본 패키지 안 ``data/`` 에 저장. 런타임 데이터라 gitignore 대상.
_BUDGET_PATH = Path(__file__).resolve().parents[1] / "data" / "tier2_budget.json"

# spec §6.8: 일일 Tier-2 호출 글로벌 상한 200 회.
DAILY_LIMIT: int = 200

_VALID_KINDS: frozenset[str] = frozenset(
    {"web_search_calls", "fetch_calls", "total_react_steps"}
)


def _today() -> str:
    """UTC 기준 ISO 일자 (YYYY-MM-DD)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load() -> dict:
    """현재 카운터 파일을 dict 로 로드. 없거나 손상 시 빈 dict."""
    try:
        return json.loads(_BUDGET_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _atomic_write(payload: dict) -> None:
    """tmp file 작성 후 ``os.replace`` 로 atomic swap."""
    _BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".tier2_budget.", suffix=".tmp", dir=str(_BUDGET_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, sort_keys=True, indent=2)
        os.replace(tmp, _BUDGET_PATH)
    except Exception:
        # 실패 시 tmp 파일 정리. 실패 자체는 호출 측에 raise 하지 않고 조용히 무시.
        # 비용 카운터는 best-effort 이므로 정합성 < 가용성.
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _total_today(data: dict) -> int:
    """오늘 일자의 모든 카운터 합."""
    today_data = data.get(_today(), {})
    return sum(int(v) for v in today_data.values() if isinstance(v, (int, float)))


def check_budget() -> tuple[bool, Optional[str]]:
    """오늘 호출이 글로벌 상한 미만이면 ``(True, None)``, 도달 시 ``(False, warning)``."""
    data = _load()
    used = _total_today(data)
    if used >= DAILY_LIMIT:
        return False, (
            f"tier2_budget_exceeded: {used}/{DAILY_LIMIT} calls used today "
            f"({_today()} UTC). Falling back to 'general' dress code."
        )
    return True, None


def increment(kind: str, amount: int = 1) -> None:
    """오늘 일자 카운터를 누적. 잘못된 ``kind`` 는 silent no-op (비용 카운터는 best-effort)."""
    if kind not in _VALID_KINDS or amount <= 0:
        return
    data = _load()
    today = _today()
    bucket = data.setdefault(today, {})
    bucket[kind] = int(bucket.get(kind, 0)) + int(amount)
    _atomic_write(data)


def reset_today_for_tests() -> None:
    """테스트 전용. 오늘 일자 카운터를 비운다. 프로덕션 코드에서는 호출 금지."""
    data = _load()
    data.pop(_today(), None)
    _atomic_write(data)
