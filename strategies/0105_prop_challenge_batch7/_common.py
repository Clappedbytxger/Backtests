"""Shared helpers for prop-challenge batch-7 (ideas I0089-I0091).

Batch 7 harvests the multi-LLM review (#s40): of ~40 LLM-proposed CTI strategies
~32 were single-CFD intraday DIRECTION (the 9x-confirmed cost wall) -> dropped.
The genuinely valuable residue is the RV / MR / carry convergence:

  I0089  AUDNZD cointegration mean-reversion (USD-free decorrelator)   -> e1
  I0090  FX carry + momentum filter (CFD swap = the carry)             -> e2
  I0091  Overnight-gap reversal on index CFD (overreaction fade)       -> e3

Cost discipline (Step-0 gate): every HELD CFD pays spread + OVERNIGHT SWAP.
Cross-spread for FX crosses runs a touch wider than majors; index ~3 bps RT.

All return streams are simple (fraction) returns. Daily metrics via quantlab.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = Path(__file__).resolve().parent / "results"
STREAMS = RESULTS / "streams"
STREAMS.mkdir(parents=True, exist_ok=True)

from quantlab.data import get_prices  # noqa: E402

ANN = np.sqrt(252)

# ── CFD cost constants (round-trip, bps of notional, CTI/retail feed) ─────────
SPREAD_RT = {"fx": 1.6, "fx_cross": 2.2, "index": 3.0, "gold": 4.0, "crypto": 20.0}
SWAP_PER_NIGHT = {"index": 2.0, "gold": 2.0, "fx": 0.5, "fx_cross": 0.7, "crypto": 8.0}


def load_close(ticker: str, start="2004-01-01") -> pd.Series:
    df = get_prices(ticker, start=start)
    return df["Close"].dropna()


def load_ohlc(ticker: str, start="2004-01-01") -> pd.DataFrame:
    return get_prices(ticker, start=start)[["Open", "High", "Low", "Close"]].dropna()


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


def perm_test_trades(per_trade_signed_ret, n: int = 5000, seed: int = 0) -> float:
    """Permutation p vs random-SIGN timing on the same |moves| (drift-trap test)."""
    rng = np.random.default_rng(seed)
    x = np.asarray(per_trade_signed_ret, float)
    x = x[~np.isnan(x)]
    if x.size < 2:
        return float("nan")
    mag = np.abs(x)
    real = x.mean()
    cnt = sum((rng.choice([-1.0, 1.0], size=mag.size) * mag).mean() >= real for _ in range(n))
    return (cnt + 1) / (n + 1)


def perm_test_rotation(W: pd.DataFrame, R: pd.DataFrame, n: int = 2000, seed: int = 0) -> float:
    """Timing permutation for held-position sleeves (circular weight rotation)."""
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


def atr(ohlc: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = ohlc["High"], ohlc["Low"], ohlc["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def rolling_halflife(spread: pd.Series, window: int = 120) -> pd.Series:
    """Rolling Ornstein-Uhlenbeck half-life of mean reversion (in bars).

    Regress dY_t on Y_{t-1}: dY = a + b*Y_{t-1}; half-life = -ln(2)/ln(1+b).
    Computed look-ahead-free on the trailing `window`.
    """
    y = spread.values
    n = len(y)
    out = np.full(n, np.nan)
    for i in range(window, n):
        seg = y[i - window : i]
        yl = seg[:-1]
        dy = np.diff(seg)
        yl_c = yl - yl.mean()
        denom = (yl_c**2).sum()
        if denom == 0:
            continue
        b = (yl_c * (dy - dy.mean())).sum() / denom
        if b >= 0 or (1 + b) <= 0:
            continue
        out[i] = -np.log(2) / np.log(1 + b)
    return pd.Series(out, index=spread.index)


def save_stream(name: str, daily_net: pd.Series) -> None:
    s = pd.Series(daily_net).dropna()
    s.name = name
    s.to_frame().to_parquet(STREAMS / f"{name}.parquet")


def scale_to_vol(daily_net: pd.Series, target_ann_vol: float = 0.10) -> pd.Series:
    s = pd.Series(daily_net).dropna()
    rv = s.std() * ANN
    k = target_ann_vol / rv if rv > 0 else 1.0
    return s * k
