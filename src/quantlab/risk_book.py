"""Trade-log → daily-returns-panel adapter for the Risk Desk.

Turns the heterogeneous ``strategies/*/results/trades.csv`` files into one common
**daily return panel** (date index × strategy columns) that :mod:`quantlab.risk`
can aggregate. Each sleeve's per-trade net return is spread evenly across its holding
days on a business-day calendar — a 4-day hold of +2.0% contributes +0.5%/day — so
overlapping sleeves correlate correctly and flat days read as 0.

Which strategies form "the book" is governed by the CATALOG status: by default the
*alive* sleeves (testing / Kandidat / overlay / abgeschlossen — anything not an
outright ``abgelehnt``) that actually have a parseable trade log. The caller may also
pass an explicit list of strategy numbers (the dashboard's manual selection).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.config import get_settings
from quantlab.registry.db import parse_catalog

# the dominant schema (25+ sleeves): entry_date,exit_date,direction,holding_days,gross_return,pnl
_DATE_COLS = ("entry_date", "exit_date")
_RET_COLS = ("net_return", "pnl", "gross_return", "ret_primary")  # preference order


def _is_alive(status: str | None) -> bool:
    """A CATALOG status that is *not* an outright rejection / pure data-blocker."""
    s = (status or "").lower()
    if not s:
        return False
    if "abgelehnt" in s or "reject" in s or "artefakt" in s or "messlatte" in s:
        return False
    alive = ("testing", "kandidat", "overlay", "lead", "live", "abgeschlossen",
             "diversifikator", "dokumentiert", "confirmed", "active")
    return any(k in s for k in alive)


def _trade_returns_to_daily(df: pd.DataFrame) -> pd.Series | None:
    """Spread each trade's net return across its holding business days.

    Returns a daily ``pd.Series`` (date → return), or ``None`` if the frame lacks the
    entry/exit/return columns. Multiple concurrent trades on a day are summed (a sleeve
    can hold several positions); a same-day trade lands fully on the entry date.
    """
    cols = {c.lower(): c for c in df.columns}
    if not all(c in cols for c in _DATE_COLS):
        return None
    ret_col = next((cols[c] for c in _RET_COLS if c in cols), None)
    if ret_col is None:
        return None

    entry = pd.to_datetime(df[cols["entry_date"]], errors="coerce")
    exit_ = pd.to_datetime(df[cols["exit_date"]], errors="coerce")
    ret = pd.to_numeric(df[ret_col], errors="coerce")
    ok = entry.notna() & exit_.notna() & ret.notna()
    entry, exit_, ret = entry[ok], exit_[ok], ret[ok]
    if entry.empty:
        return None

    daily: dict[pd.Timestamp, float] = {}
    for e, x, r in zip(entry, exit_, ret):
        days = pd.bdate_range(e, x)
        if len(days) == 0:
            days = pd.DatetimeIndex([e])
        per = float(r) / len(days)
        for d in days:
            daily[d] = daily.get(d, 0.0) + per
    if not daily:
        return None
    return pd.Series(daily).sort_index()


def load_strategy_returns(
    repo_root: Path | str | None = None,
    *,
    nums: list[str] | None = None,
    alive_only: bool = True,
    min_trades: int = 5,
) -> tuple[pd.DataFrame, list[dict]]:
    """Build the daily-returns panel for the active book.

    Parameters
    ----------
    nums : explicit strategy numbers to include (overrides the alive filter).
    alive_only : keep only non-rejected CATALOG statuses (ignored if ``nums`` given).
    min_trades : drop sleeves whose trade log has fewer rows (too thin to risk-measure).

    Returns ``(panel, meta)`` — ``panel`` is the aligned business-day return frame
    (outer-joined over all sleeves, missing = NaN), ``meta`` a per-strategy descriptor
    list (num, name, status, n_trades, span, annualised vol/return).
    """
    settings = get_settings()
    root = Path(repo_root) if repo_root else settings.backtest_dir
    catalog = parse_catalog(root / "CATALOG.md")
    strat_dir = root / "strategies"

    wanted = set(nums) if nums else None
    series: dict[str, pd.Series] = {}
    meta: list[dict] = []

    for folder in sorted(strat_dir.glob("[0-9][0-9][0-9][0-9]_*")):
        num = folder.name[:4]
        if wanted is not None and num not in wanted:
            continue
        row = catalog.get(num, {})
        if wanted is None and alive_only and not _is_alive(row.get("status")):
            continue
        tcsv = folder / "results" / "trades.csv"
        if not tcsv.exists():
            continue
        try:
            df = pd.read_csv(tcsv)
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        if len(df) < min_trades:
            continue
        daily = _trade_returns_to_daily(df)
        if daily is None or daily.size < min_trades:
            continue
        # within-life 0-fill: a sleeve holds 0 (cash) on its non-trade days, so its
        # standalone vol and the book covariance are economically correct (flat ≠ missing).
        life = pd.bdate_range(daily.index.min(), daily.index.max())
        daily = daily.reindex(life, fill_value=0.0)

        label = f"{num} {(_short(row.get('name')) or folder.name[5:])}"
        series[label] = daily
        ann = float(daily.std(ddof=1) * np.sqrt(252)) if daily.size > 1 else float("nan")
        meta.append({
            "num": num,
            "label": label,
            "name": row.get("name") or folder.name[5:],
            "status": row.get("status"),
            "category": row.get("category"),
            "n_trades": int(len(df)),
            "n_days": int(daily.size),
            "start": daily.index.min().strftime("%Y-%m-%d"),
            "end": daily.index.max().strftime("%Y-%m-%d"),
            "vol_annual": ann,
            "return_annual": float(daily.mean() * 252),
        })

    if not series:
        return pd.DataFrame(), meta

    panel = pd.DataFrame(series).sort_index()
    # outer-join leaves NaN only OUTSIDE each sleeve's life (pre-inception / post-death).
    panel = panel[panel.notna().any(axis=1)]
    return panel, meta


def to_risk_matrix(panel: pd.DataFrame, window: int | None = None,
                   *, min_obs: int = 20) -> pd.DataFrame:
    """Clean rectangular return matrix for covariance / VaR / optimisation.

    Takes the trailing ``window`` business days (``None`` = full history), drops sleeves
    that are not meaningfully alive in that slice (fewer than ``min_obs`` in-life days or
    zero variance — a dead/flat column would break inverse-variance), then fills the
    remaining out-of-life gaps with 0 (flat = cash). The result is finite and PSD-friendly.
    """
    if panel.empty:
        return panel
    sl = panel if (window is None or window <= 0 or window >= len(panel)) else panel.iloc[-window:]
    keep = [c for c in sl.columns
            if sl[c].notna().sum() >= min_obs and float(np.nanstd(sl[c].values)) > 0]
    sl = sl[keep].fillna(0.0)
    return sl


def window_panel(panel: pd.DataFrame, window: int | None) -> pd.DataFrame:
    """Trailing-``window`` (in observations) slice of the panel; ``None`` = full."""
    if window is None or window <= 0 or window >= len(panel):
        return panel
    return panel.iloc[-window:]


def _short(name: str | None) -> str | None:
    if not name:
        return None
    return name.replace("*", "").strip()[:26]
