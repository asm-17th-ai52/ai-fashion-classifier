"""Session ID minting — ULID-like 26-char base32 string."""
from __future__ import annotations

import os
import time


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def mint_session_id() -> str:
    """Format: ``sess_<26-char ULID-style ID>``.

    Compact, lexicographically sortable; good enough without an extra dep.
    """
    ts_ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    val = (ts_ms << 80) | rand
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[val & 0x1F])
        val >>= 5
    return "sess_" + "".join(reversed(chars))
