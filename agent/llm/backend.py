"""Hardware-abstracted local LLM inference for the agent.

One interface, three backends:
  - ``MockBackend``    — deterministic, no model (tests + dry runs)
  - ``LlamaCppBackend``— Windows / cross-platform GGUF via ``llama-cpp-python``
  - ``MLXBackend``     — macOS / Apple Silicon via ``mlx-lm``

The real backends are lazy-imported, so importing this module never requires a
multi-GB model or a heavy dependency. ``get_backend("auto")`` picks per platform
(mlx on Apple Silicon, llama.cpp otherwise). Models: DeepSeek-Coder for code,
Llama-3 for analysis/RAG.
"""

from __future__ import annotations

import platform
from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """Minimal text-generation interface used by the agent."""

    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None,
                 max_tokens: int = 2048, temperature: float = 0.2) -> str:
        ...


class MockBackend(LLMBackend):
    """Deterministic backend for tests/dry-runs. Set ``canned`` or a ``responder``."""

    name = "mock"

    def __init__(self, responder=None, canned: str = "") -> None:
        self._responder = responder
        self._canned = canned

    def generate(self, prompt: str, system: str | None = None,
                 max_tokens: int = 2048, temperature: float = 0.2) -> str:
        if self._responder is not None:
            return self._responder(prompt, system)
        return self._canned


class LlamaCppBackend(LLMBackend):
    """Local GGUF inference via llama-cpp-python (Windows + cross-platform)."""

    name = "llamacpp"

    def __init__(self, model_path: str, n_ctx: int = 8192, n_gpu_layers: int = -1, **kw) -> None:
        try:
            from llama_cpp import Llama
        except ImportError as e:  # pragma: no cover - optional heavy dep
            raise RuntimeError("llama-cpp-python not installed; run: pip install '.[agent]'") from e
        self._llm = Llama(model_path=model_path, n_ctx=n_ctx,
                          n_gpu_layers=n_gpu_layers, verbose=False, **kw)

    def generate(self, prompt: str, system: str | None = None,
                 max_tokens: int = 2048, temperature: float = 0.2) -> str:  # pragma: no cover
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        out = self._llm.create_chat_completion(messages=messages, max_tokens=max_tokens,
                                               temperature=temperature)
        return out["choices"][0]["message"]["content"]


class MLXBackend(LLMBackend):
    """Local inference via mlx-lm (macOS / Apple Silicon)."""

    name = "mlx"

    def __init__(self, model: str, **kw) -> None:
        try:
            from mlx_lm import generate as _gen, load
        except ImportError as e:  # pragma: no cover - optional heavy dep
            raise RuntimeError("mlx-lm not installed; run: pip install '.[agent]'") from e
        self._model, self._tokenizer = load(model)
        self._gen = _gen

    def generate(self, prompt: str, system: str | None = None,
                 max_tokens: int = 2048, temperature: float = 0.2) -> str:  # pragma: no cover
        full = (system + "\n\n" if system else "") + prompt
        return self._gen(self._model, self._tokenizer, prompt=full, max_tokens=max_tokens)


def detect_platform_backend() -> str:
    """Best local backend for this machine: mlx on Apple Silicon, else llama.cpp."""
    if platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"):
        return "mlx"
    return "llamacpp"


def get_backend(name: str | None = None, **kwargs) -> LLMBackend:
    """Resolve a backend by name (``auto`` | ``mock`` | ``llamacpp`` | ``mlx``).

    ``name=None`` reads ``llm_backend`` from the project config. Real backends are
    only instantiated (and their libs imported) here — pass their ``**kwargs``
    (e.g. ``model_path=`` / ``model=``).
    """
    settings = None
    if name is None or name.lower() in ("auto", "llamacpp", "mlx"):
        from quantlab.config import get_settings
        settings = get_settings()
    if name is None:
        name = settings.llm_backend
    name = (name or "auto").lower()
    if name == "auto":
        name = detect_platform_backend()
    if name == "mock":
        return MockBackend(**kwargs)
    if name == "llamacpp":
        if "model_path" not in kwargs and settings and settings.llm_model:
            kwargs["model_path"] = str(settings.llm_model)
        return LlamaCppBackend(**kwargs)
    if name == "mlx":
        if "model" not in kwargs and settings and settings.llm_model:
            kwargs["model"] = str(settings.llm_model)
        return MLXBackend(**kwargs)
    raise ValueError(f"unknown llm backend {name!r} (use auto|mock|llamacpp|mlx)")
