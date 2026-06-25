"""PyInstaller entry for the Quant-OS API sidecar.

Frozen into a standalone binary (`scripts/build_sidecar_mac.sh`) and launched by the
Tauri desktop app on startup. It:

1. honours ``QOS_DATA_DIR`` (passed by Tauri = a writable Application-Support folder) by
   mapping it onto the ``QUANTLAB_*`` settings the API resolves its paths from — this must
   happen **before** importing the app, because :func:`quantlab.config.get_settings` is
   cached on first call;
2. makes ``quantlab`` / ``apps`` / ``agent`` / ``live`` importable when run as a plain
   script (the frozen build collects them via the build flags);
3. serves the FastAPI app with uvicorn on ``127.0.0.1:8000`` (the URL the frontend's
   ``NEXT_PUBLIC_API_URL`` defaults to).

Note: endpoints that shell out to a Python interpreter or git (the autonomous-agent
run/evaluate/promote routes) do not function inside a frozen binary — they are
developer-only and irrelevant to the shipped commercial app. The read-only decision
surfaces (registry, regime, COT, seasonal, risk, swarm, switchboard, live book) work.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _base_dir() -> Path:
    """Repo root when run from source; the executable's dir when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _seed_from_bundle(dd: Path) -> None:
    """First-run only: copy the bundled registry DB + result plots into the writable dir.

    Tauri ships ``strategies.db`` and ``strategies/*/results/*.png`` as read-only app
    resources and points ``QOS_BUNDLE_DIR`` at them. We copy them once into the writable
    data dir so SQLite can open the DB read-write and the plot endpoints resolve. Small
    (~16 MB), so a one-time copy on first launch is cheap.
    """
    bundle = os.environ.get("QOS_BUNDLE_DIR")
    if not bundle:
        return
    b = Path(bundle)
    src_db, dst_db = b / "strategies.db", dd / "strategies.db"
    if src_db.exists() and not dst_db.exists():
        shutil.copy2(src_db, dst_db)
    src_strat, dst_strat = b / "strategies", dd / "strategies"
    if src_strat.exists() and not dst_strat.exists():
        shutil.copytree(src_strat, dst_strat)


def _configure_env() -> None:
    # Map the Tauri-provided writable dir onto the quantlab settings (only if not already
    # set by the user, so an explicit override always wins).
    data_dir = os.environ.get("QOS_DATA_DIR")
    if data_dir:
        dd = Path(data_dir)
        (dd / "data").mkdir(parents=True, exist_ok=True)
        _seed_from_bundle(dd)
        os.environ.setdefault("QUANTLAB_BACKTEST_DIR", str(dd))
        os.environ.setdefault("QUANTLAB_DATA_DIR", str(dd / "data"))
        os.environ.setdefault("QUANTLAB_REGISTRY_DB", str(dd / "strategies.db"))

    # Importability when run as a plain (non-frozen) script.
    root = _base_dir()
    for p in (root, root / "src"):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)


def main() -> None:
    _configure_env()
    host = os.environ.get("QOS_API_HOST", "127.0.0.1")
    port = int(os.environ.get("QOS_API_PORT", "8000"))

    import uvicorn  # imported after env setup
    from apps.api.main import app  # noqa: WPS433 (deferred import is intentional)

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
