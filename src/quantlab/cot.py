"""COT Institutional Positioning engine — net positions, COT index, z-score, signals.

Builds on the PIT-safe CFTC loader (:mod:`quantlab.cot_data`, legacy futures-only) and
turns the raw long/short contract counts into the institutional-positioning factors the
desk and the Alpha-Factory consume:

* **Net positions** — ``comm_net = comm_long - comm_short`` (the commercials, i.e.
  producers / merchants / swap dealers = "smart money") and ``noncomm_net`` (the
  non-commercials / large speculators ≈ managed money = the trend followers).
* **COT index** — net position min-max normalised over a rolling window (default 156
  weeks ≈ 3 years), in [0, 100]; 0 = most net-short in 3y, 100 = most net-long.
* **Rolling z-score** — standardised commercial net position; ``|z| > 2`` flags an
  *overcrowded / exhaustion* extreme.

The factors are exposed as "global variables" via :func:`latest_factors` /
:func:`factor_panel` so signal code (including agent-generated hypotheses) can gate on
them, e.g. *long gold only when the commercial COT index > 80*.

Look-ahead: weekly factors are derived from data known at the Tuesday ``ref_date``; the
backtest panel (:func:`factor_panel`) maps each value onto its Friday ``release_date``
and shifts one trading day (delegating to :func:`quantlab.cot_data.cot_daily_panel`), so
nothing leaks the same-week release into a same-day decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quantlab import cot_data

DEFAULT_WINDOW = 156  # weeks ≈ 3 years
EXTREME_Z = 2.0       # |z| beyond this = exhaustion / overcrowded
INDEX_LOW = 20.0      # COT-index oversold (commercials very net-short)
INDEX_HIGH = 80.0     # COT-index overbought (commercials very net-long)


@dataclass(frozen=True)
class CotMarket:
    root: str
    name: str
    group: str            # energy | metal | grain | livestock | fx | index
    price_ticker: str     # yfinance symbol for the candle chart


# Scannable universe: maps each CFTC root to a display name, group and a price feed.
UNIVERSE: list[CotMarket] = [
    CotMarket("CL", "Crude Oil (WTI)", "energy", "CL=F"),
    CotMarket("NG", "Natural Gas", "energy", "NG=F"),
    CotMarket("HO", "Heating Oil", "energy", "HO=F"),
    CotMarket("RB", "RBOB Gasoline", "energy", "RB=F"),
    CotMarket("GC", "Gold", "metal", "GC=F"),
    CotMarket("SI", "Silver", "metal", "SI=F"),
    CotMarket("HG", "Copper", "metal", "HG=F"),
    CotMarket("PL", "Platinum", "metal", "PL=F"),
    CotMarket("PA", "Palladium", "metal", "PA=F"),
    CotMarket("ZC", "Corn", "grain", "ZC=F"),
    CotMarket("ZW", "Wheat (SRW)", "grain", "ZW=F"),
    CotMarket("ZS", "Soybeans", "grain", "ZS=F"),
    CotMarket("ZL", "Soybean Oil", "grain", "ZL=F"),
    CotMarket("ZM", "Soybean Meal", "grain", "ZM=F"),
    CotMarket("LE", "Live Cattle", "livestock", "LE=F"),
    CotMarket("GF", "Feeder Cattle", "livestock", "GF=F"),
    CotMarket("HE", "Lean Hogs", "livestock", "HE=F"),
    CotMarket("6E", "Euro FX", "fx", "6E=F"),
    CotMarket("6B", "British Pound", "fx", "6B=F"),
    CotMarket("6J", "Japanese Yen", "fx", "6J=F"),
    CotMarket("6A", "Australian Dollar", "fx", "6A=F"),
    CotMarket("6C", "Canadian Dollar", "fx", "6C=F"),
    CotMarket("6S", "Swiss Franc", "fx", "6S=F"),
    CotMarket("DX", "US Dollar Index", "fx", "DX=F"),
    CotMarket("ES", "S&P 500", "index", "ES=F"),
    CotMarket("NQ", "Nasdaq 100", "index", "NQ=F"),
    CotMarket("YM", "Dow Jones", "index", "YM=F"),
]
_BY_ROOT = {m.root: m for m in UNIVERSE}


def get_market(root: str) -> CotMarket | None:
    return _BY_ROOT.get(root.upper())


# ── math primitives ──────────────────────────────────────────────────────────


def cot_index(net: pd.Series, window: int = DEFAULT_WINDOW) -> pd.Series:
    """Rolling min-max COT index in [0, 100] (Williams/Briese definition).

    ``(net - min) / (max - min) * 100`` over a trailing ``window``. A flat window
    (max == min) yields 50 (neutral). Look-ahead-safe: only trailing observations.
    """
    net = pd.Series(net, dtype="float64")
    mp = min(window, max(20, window // 6))
    lo = net.rolling(window, min_periods=mp).min()
    hi = net.rolling(window, min_periods=mp).max()
    rng = (hi - lo).replace(0.0, np.nan)
    idx = (net - lo) / rng * 100.0
    return idx.fillna(50.0).clip(0.0, 100.0)


def rolling_zscore(net: pd.Series, window: int = DEFAULT_WINDOW) -> pd.Series:
    """Rolling z-score of a net-position series over a trailing ``window``."""
    net = pd.Series(net, dtype="float64")
    mp = min(window, max(20, window // 6))
    mean = net.rolling(window, min_periods=mp).mean()
    std = net.rolling(window, min_periods=mp).std()
    z = (net - mean) / std.replace(0.0, np.nan)
    return z.replace([np.inf, -np.inf], np.nan)


def classify_signal(comm_index: float | None, comm_z: float | None) -> dict:
    """Map a commercial COT index + z-score to a positioning signal.

    Commercials are contrarian smart money: extreme commercial *net-long* (high index /
    high +z) is bullish for price; extreme commercial *net-short* (low index / low -z)
    is bearish. Returns ``{status, bias, severity}``.
    """
    z = comm_z if comm_z is not None and np.isfinite(comm_z) else 0.0
    idx = comm_index if comm_index is not None and np.isfinite(comm_index) else 50.0
    if z >= EXTREME_Z or idx >= INDEX_HIGH:
        return {"status": "Commercial Buying Extreme", "bias": "bullish",
                "severity": "extreme" if z >= EXTREME_Z else "elevated"}
    if z <= -EXTREME_Z or idx <= INDEX_LOW:
        return {"status": "Hedgefonds Overcrowded Short" if z <= -EXTREME_Z else "Commercial Selling",
                "bias": "bearish", "severity": "extreme" if z <= -EXTREME_Z else "elevated"}
    if idx >= 60:
        return {"status": "Commercials akkumulieren", "bias": "bullish", "severity": "mild"}
    if idx <= 40:
        return {"status": "Commercials verteilen", "bias": "bearish", "severity": "mild"}
    return {"status": "Neutral", "bias": "neutral", "severity": "none"}


# ── per-asset compute ─────────────────────────────────────────────────────────


def compute_cot(root: str, window: int = DEFAULT_WINDOW, **loader_kwargs) -> pd.DataFrame:
    """Full weekly COT factor frame for one root (indexed by Tuesday ``ref_date``).

    Columns: ``comm_net, noncomm_net, open_interest, comm_index, noncomm_index,
    comm_z, noncomm_z, hedging_pressure, release_date``.
    """
    df = cot_data.get_cot(root.upper(), **loader_kwargs).copy()
    df["comm_net"] = df["comm_long"] - df["comm_short"]
    df["noncomm_net"] = df["noncomm_long"] - df["noncomm_short"]
    df["comm_index"] = cot_index(df["comm_net"], window)
    df["noncomm_index"] = cot_index(df["noncomm_net"], window)
    df["comm_z"] = rolling_zscore(df["comm_net"], window)
    df["noncomm_z"] = rolling_zscore(df["noncomm_net"], window)
    return df


def latest_factors(root: str, window: int = DEFAULT_WINDOW, **loader_kwargs) -> dict:
    """Latest-week COT factors for one asset (the 'global variable' snapshot)."""
    m = get_market(root)
    df = compute_cot(root, window, **loader_kwargs)
    last = df.iloc[-1]
    sig = classify_signal(float(last["comm_index"]), float(last["comm_z"]))
    return {
        "root": root.upper(),
        "name": m.name if m else root.upper(),
        "group": m.group if m else "other",
        "ref_date": str(df.index[-1].date()),
        "comm_net": int(last["comm_net"]),
        "noncomm_net": int(last["noncomm_net"]),
        "open_interest": int(last["open_interest"]),
        "comm_index": round(float(last["comm_index"]), 1),
        "noncomm_index": round(float(last["noncomm_index"]), 1),
        "comm_z": round(float(last["comm_z"]), 2) if np.isfinite(last["comm_z"]) else None,
        "noncomm_z": round(float(last["noncomm_z"]), 2) if np.isfinite(last["noncomm_z"]) else None,
        "hedging_pressure": round(float(last["hedging_pressure"]), 4),
        "signal": sig,
    }


def scan_universe(roots: list[str] | None = None, window: int = DEFAULT_WINDOW,
                  **loader_kwargs) -> list[dict]:
    """Latest COT factors for every market, sorted by |commercial z| (most extreme first).

    The data behind the Extreme-Positioning table. One unreachable/unmapped root is
    skipped rather than failing the whole scan.
    """
    roots = roots or [m.root for m in UNIVERSE]
    out: list[dict] = []
    for r in roots:
        try:
            out.append(latest_factors(r, window, **loader_kwargs))
        except Exception:  # noqa: BLE001 - one bad feed must not kill the scan
            continue
    out.sort(key=lambda d: abs(d.get("comm_z") or 0.0), reverse=True)
    return out


# ── backtest / Alpha-Factory exposure (PIT-safe daily panel) ──────────────────


def factor_panel(root: str, trading_days: pd.DatetimeIndex, factor: str = "comm_index",
                 window: int = DEFAULT_WINDOW, **loader_kwargs) -> pd.Series:
    """PIT-safe daily series of one COT factor for use in a backtest signal.

    Computes the weekly factor, then delegates the Friday-release + next-trading-day
    shift to :func:`quantlab.cot_data.cot_daily_panel` so the factor is only actionable
    from the first close after its release. Returns a Series aligned to ``trading_days``.
    """
    df = compute_cot(root, window, **loader_kwargs)
    valid = {"comm_net", "noncomm_net", "comm_index", "noncomm_index",
             "comm_z", "noncomm_z", "hedging_pressure"}
    if factor not in valid:
        raise ValueError(f"unknown factor '{factor}'; choose from {sorted(valid)}")
    panel = cot_data.cot_daily_panel({root.upper(): df}, trading_days, column=factor)
    return panel[root.upper()]
