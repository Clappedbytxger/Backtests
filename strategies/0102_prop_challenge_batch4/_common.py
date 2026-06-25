"""Shared helpers for the prop-challenge batch-4 screen (ideas I0075-I0079).

Batch 4 deliberately leaves the dead intraday-direction space of batch 3 and tests
either (a) LIVING catalogue edges ported onto CTI-tradable CFDs (month-end FX flow,
USD regime, TSMOM) or (b) the low-frequency daily-swing profile that BATCH-3-RESULTS
itself names as the CTI-viable path (RSI-2 index MR, overnight premium).

Cost discipline (Step-0 gate, like batch 3): for the *held* edges the binding cost is
no longer only the spread but the OVERNIGHT SWAP / financing on the CFD. We model both.

  Spread (round-trip, bps of notional, from quantlab.costs):
    FX     ~1.6   Index ~3.0   Gold ~4.0   Crypto ~20

  Overnight swap (per night held, bps of notional, long side):
    Index long  ~2.0 bps/night  (~SOFR + broker mark-up, annualised ~7%/360)
    Gold  long  ~2.0 bps/night
    FX          rate-differential dependent, modelled per-pair where relevant

All return streams are simple (fraction) returns. Daily metrics via quantlab.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
CACHE = ROOT / "data" / "cache"

ANN = np.sqrt(252)

# ── CFD cost constants (round-trip spread, bps of notional) ───────────────────
SPREAD_RT = {"fx": 1.6, "index": 3.0, "gold": 4.0, "crypto": 20.0}
# Overnight swap per night held (bps of notional), long financing cost
SWAP_PER_NIGHT = {"index": 2.0, "gold": 2.0, "fx": 0.5}


def ann_sharpe(daily_rets: pd.Series) -> float:
    r = daily_rets.dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * ANN)


def sharpe_per_trade(rets) -> float:
    r = np.asarray(rets, float)
    r = r[~np.isnan(r)]
    if r.size < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1))


def perm_test_timing(per_event_signed_ret: pd.Series, n: int = 5000, seed: int = 0) -> float:
    """Permutation p vs random-sign timing on the SAME events (drift-trap test).

    Null: the timing/sign carries no edge -> a random +/-1 per event on the same
    absolute move matches. One-sided (real mean >= null mean).
    """
    rng = np.random.default_rng(seed)
    mag = per_event_signed_ret.abs().values
    real = per_event_signed_ret.mean()
    cnt = 0
    for _ in range(n):
        s = rng.choice([-1.0, 1.0], size=mag.size)
        if (s * mag).mean() >= real:
            cnt += 1
    return (cnt + 1) / (n + 1)


def bootstrap_mean_ci(x, n: int = 5000, seed: int = 0, alpha: float = 0.05):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if x.size < 2:
        return float("nan"), float("nan")
    means = np.array([rng.choice(x, x.size, replace=True).mean() for _ in range(n)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def wilder_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    """Wilder RSI (the Connors RSI-2 definition uses Wilder smoothing)."""
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.fillna(50.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()
