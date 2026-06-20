"""Hardware-abstracted local LLM backends for the agent."""

from .backend import (
    LLMBackend,
    LlamaCppBackend,
    MLXBackend,
    MockBackend,
    detect_platform_backend,
    get_backend,
)

__all__ = [
    "LLMBackend", "MockBackend", "LlamaCppBackend", "MLXBackend",
    "detect_platform_backend", "get_backend",
]
