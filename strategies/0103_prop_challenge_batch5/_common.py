"""Shared helpers for prop-challenge batch-5 (ideas I0080-I0085).

Batch 5 chases the two mathematical Sharpe levers from the spec:
  (1) BREADTH  -- more genuinely decorrelated sleeves (crypto TSMOM, FX x-section,
                  gold/silver RV, FX RV) so Sharpe_book ~ Sharpe_sleeve * sqrt(K).
  (2) FREQUENCY -- more cost-surviving bets/year (MR, not intraday direction which
                  is dead, batch 3 8/8).

Cost discipline (Step-0 gate): every HELD sleeve pays spread + OVERNIGHT SWAP.
The intraday-flat sleeve (I0084) pays spread only (no swap). Crypto financing on a
1:2 CFD is the binding kill-gate for I0080 -- modelled explicitly and conservatively.

  Spread (round-trip, bps of notional, CTI/retail CFD feed, from quantlab.costs):
    FX ~1.6   Index ~3.0   Gold ~4.0   Crypto ~20

  Overnight swap (per night held, bps of notional, long financing):
    Index ~2.0   Gold ~2.0   FX ~0.5 (pair-dependent)   Crypto ~8.0 (1:2 CFD financing)

All return streams are simple (fraction) daily returns. Daily metrics via quantlab.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
CACHE = ROOT / "data" / "cache"
RESULTS = Path(__file__).resolve().parent / "results"
STREAMS = RESULTS / "streams"
STREAMS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(252)

# ── CFD cost constants (round-trip spread, bps of notional) ───────────────────
SPREAD_RT = {"fx": 1.6, "index": 3.0, "gold": 4.0, "crypto": 20.0}
# Overnight swap per night held (bps of notional), long financing cost.
# Crypto: 1:2-leverage CFD financing is brutal -- ~8 bps/night (~30%/yr on notional)
# is a deliberately conservative CTI-style number (the I0079/I0080 kill-gate).
SWAP_PER_NIGHT = {"index": 2.0, "gold": 2.0, "fx": 0.5, "crypto": 8.0}


def ann_sharpe(daily_rets: pd.Series) -> float:
    r = pd.Series(daily_rets).dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * ANN)


def sharpe_per_trade(rets) -> float:
    r = np.asarray(rets, float)
    r = r[~np.isnan(r)]
    if r.size < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1))


def perm_test_sign(per_event_signed_ret, n: int = 5000, seed: int = 0) -> float:
    """Permutation p vs random-sign timing on the SAME events (drift-trap test).
    Null: the timing/sign carries no edge -> random +/-1 on the same |move| matches."""
    rng = np.random.default_rng(seed)
    x = np.asarray(per_event_signed_ret, float)
    x = x[~np.isnan(x)]
    mag = np.abs(x)
    real = x.mean()
    cnt = sum((rng.choice([-1.0, 1.0], size=mag.size) * mag).mean() >= real for _ in range(n))
    return (cnt + 1) / (n + 1)


def perm_test_rotation(W: pd.DataFrame, R: pd.DataFrame, n: int = 2000, seed: int = 0) -> float:
    """Timing permutation for held-position sleeves (trend/MR).

    Null: the position TIMING carries no edge -> circularly rotating the weight
    matrix against the returns (destroying alignment but preserving both the weight
    autocorrelation structure and the return distribution) matches the real gross
    Sharpe. One-sided (real >= null). Gross-based: tests timing, not cost.
    """
    rng = np.random.default_rng(seed)
    Wv = np.nan_to_num(W.values)
    Rv = np.nan_to_num(R.values)
    real_d = (Wv * Rv).sum(axis=1)
    real = real_d.mean() / real_d.std() if real_d.std() else 0.0
    T = len(Wv)
    cnt = 0
    for _ in range(n):
        k = int(rng.integers(1, T))
        d = (np.roll(Wv, k, axis=0) * Rv).sum(axis=1)
        s = d.mean() / d.std() if d.std() else 0.0
        cnt += s >= real
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
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def save_stream(name: str, daily_net: pd.Series) -> None:
    """Persist a sleeve's daily NET return stream for book integration."""
    s = pd.Series(daily_net).dropna()
    s.name = name
    s.to_frame().to_parquet(STREAMS / f"{name}.parquet")


def scale_to_vol(daily_net: pd.Series, target_ann_vol: float = 0.10) -> pd.Series:
    """Linearly scale a return stream to a target annual vol (Sharpe-invariant)."""
    s = pd.Series(daily_net).dropna()
    rv = s.std() * ANN
    k = target_ann_vol / rv if rv > 0 else 1.0
    return s * k
