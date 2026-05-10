"""Selector contract tests for ``app.agents_stub.get_subgraphs``.

The selector wires real agent sub-graphs into the super-graph when the
owner module imports cleanly, and falls back to schema-valid stubs when
they don't (deps missing, code not yet shipped, etc.). These tests pin
both branches.
"""
from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents_stub import get_subgraphs
from app.agents_stub.context import context_subgraph_stub
from app.agents_stub.recommendation import recommendation_subgraph_stub
from app.agents_stub.vision import vision_subgraph_stub


# ---------------------------------------------------------------------------
# Real-import branch — only checks for whichever agent modules import
# cleanly in this venv right now.
# ---------------------------------------------------------------------------
def _vision_real_importable() -> bool:
    try:
        importlib.import_module("agents.vision")
        return True
    except Exception:
        return False


def _recommendation_real_importable() -> bool:
    try:
        importlib.import_module("agents.recommendation")
        return True
    except Exception:
        return False


def test_real_vision_routes_through_adapter_when_available() -> None:
    if not _vision_real_importable():
        pytest.skip("agents.vision not importable (likely missing google-generativeai)")
    from app.agents_stub.vision_adapter import vision_adapter

    assert get_subgraphs()["vision"] is vision_adapter


def test_real_recommendation_routes_through_adapter_when_available() -> None:
    if not _recommendation_real_importable():
        pytest.skip("agents.recommendation not importable")
    from app.agents_stub.recommendation_adapter import recommendation_adapter

    assert get_subgraphs()["recommendation"] is recommendation_adapter


def test_context_always_falls_back_to_stub() -> None:
    """Context agent has no real implementation yet."""
    assert get_subgraphs()["context"] is context_subgraph_stub


# ---------------------------------------------------------------------------
# Fallback branch — simulate a broken import and confirm we land on the stub.
# ---------------------------------------------------------------------------
def test_vision_falls_back_to_stub_when_import_raises(monkeypatch) -> None:
    # Force the real-module path to ImportError, even if the package is
    # installed in this venv.
    real_import = importlib.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "agents.vision":
            raise ImportError("simulated broken vision agent")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    # Selector evaluates imports lazily on each call, so the new behaviour
    # takes effect immediately.
    assert get_subgraphs()["vision"] is vision_subgraph_stub


def test_recommendation_falls_back_to_stub_when_import_raises(monkeypatch) -> None:
    real_import = importlib.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "agents.recommendation":
            raise ImportError("simulated broken recommendation agent")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert get_subgraphs()["recommendation"] is recommendation_subgraph_stub
