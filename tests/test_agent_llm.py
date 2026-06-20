"""Tests for the LLM backend abstraction (mock + selection logic; no model needed)."""

from __future__ import annotations

import platform

import pytest

from agent.llm import LLMBackend, MockBackend, detect_platform_backend, get_backend


def test_mock_canned_and_responder():
    assert MockBackend(canned="hello").generate("anything") == "hello"
    echo = MockBackend(responder=lambda p, s: f"echo:{p}")
    assert echo.generate("xyz") == "echo:xyz"
    assert MockBackend().name == "mock"


def test_get_backend_mock():
    assert isinstance(get_backend("mock"), MockBackend)
    assert isinstance(get_backend("MOCK"), MockBackend)  # case-insensitive


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError):
        get_backend("does-not-exist")


def test_detect_platform_backend():
    d = detect_platform_backend()
    assert d in ("mlx", "llamacpp")
    if platform.system() == "Windows":
        assert d == "llamacpp"


def test_mock_is_backend_subclass():
    assert issubclass(MockBackend, LLMBackend)
