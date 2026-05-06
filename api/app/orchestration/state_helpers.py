"""Tiny helper that lets nodes read state regardless of whether LangGraph
hands them a Pydantic model or a plain dict (varies by version)."""
from __future__ import annotations

from typing import Any


def state_get(state: Any, name: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)
