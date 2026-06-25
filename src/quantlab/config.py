"""Central configuration for Quant-OS — cross-platform paths and settings.

Resolves settings with this precedence (highest first):

    1. constructor kwargs (tests)
    2. environment variables, prefix ``QUANTLAB_`` (and a ``.env`` file)
    3. ``config.yaml`` at the repo root (optional, per-machine, git-ignored)
    4. defaults derived from the repo location via :mod:`pathlib`

No hardcoded absolute paths: the same code works on Windows and macOS. Users set
their machine-specific base paths once in ``config.yaml`` (copy from
``config.example.yaml``); everything else falls back to sensible defaults so a
fresh clone runs out of the box.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# Repo root = two levels up from this file: src/quantlab/config.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_YAML = REPO_ROOT / "config.yaml"


class _YamlSource(PydanticBaseSettingsSource):
    """Settings source that reads the optional ``config.yaml`` at the repo root.

    Tolerates a missing file (returns ``{}``) so a fresh clone without a local
    ``config.yaml`` still works purely from defaults.
    """

    def get_field_value(self, field: Any, field_name: str):  # noqa: D102 (abstract, unused)
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if CONFIG_YAML.exists():
            data = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        return {}


class Settings(BaseSettings):
    """Resolved Quant-OS settings. Access via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_prefix="QUANTLAB_",
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core locations (machine-specific; overridable). Defaults derive from the repo.
    backtest_dir: Path = REPO_ROOT
    ideas_dir: Path = REPO_ROOT.parent / "Backtest Ideas"  # sibling research workspace
    data_dir: Path = REPO_ROOT / "data"
    keys_dir: Path = REPO_ROOT  # location of .<service>.key files (git-ignored *.key)
    registry_db: Path = REPO_ROOT / "strategies.db"

    # Local LLM inference for the autonomous agent (P4).
    llm_backend: str = "auto"  # auto | mlx (macOS) | llamacpp (Windows) | mock
    llm_model: str = ""        # local model path (GGUF for llama.cpp) or MLX model id

    # Swarm Command Center (hybrid multi-agent desk): local Ollama "worker drones"
    # aggregated by a cloud "commander" (Gemini free tier). Everything degrades to a
    # deterministic fallback when a service is unreachable, so the JSON flow always runs.
    ollama_base_url: str = "http://localhost:11434"  # point at the Mac M5 over LAN later
    ollama_model: str = "llama3"                     # small/fast model for the drones
    ollama_timeout_s: float = 45.0
    gemini_model: str = "gemini-2.5-flash"           # commander, primary
    gemini_fallback_model: str = "gemini-2.0-flash"  # auto-switch on quota/429
    gemini_timeout_s: float = 60.0

    # Quant Academy (interactive learning module). All paths derive from the repo
    # so a fresh clone works on Windows and macOS; override per-machine in config.yaml.
    books_dir: Path = REPO_ROOT / "Quant Books"           # local reference literature (PDFs)
    academy_content_dir: Path = REPO_ROOT / "content" / "academy"  # curriculum.json + module md
    progress_file: Path = REPO_ROOT / "progress.json"     # learning progress (git/cloud-synced)
    academy_agent_interval_h: int = 24                     # min hours between agent content refreshes

    # Alpha Factory (autonomous continuous research worker).
    reports_dir: Path = REPO_ROOT / "reports"             # pending_review reports + reject log

    @field_validator(
        "backtest_dir", "ideas_dir", "data_dir", "keys_dir", "registry_db",
        "books_dir", "academy_content_dir", "progress_file", "reports_dir",
        mode="before",
    )
    @classmethod
    def _expand_user(cls, v: Any) -> Any:
        """Expand ``~`` in user-provided paths (helps macOS ``~/...`` configs)."""
        return Path(str(v)).expanduser() if v is not None else v

    @property
    def cache_dir(self) -> Path:
        """Parquet data-cache root (always ``data_dir/cache``)."""
        return self.data_dir / "cache"

    def ensure_dirs(self) -> "Settings":
        """Create the data + cache directories if missing. Returns self."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Precedence: init > env > .env > config.yaml > field defaults.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _YamlSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide, cached :class:`Settings` instance."""
    return Settings()
