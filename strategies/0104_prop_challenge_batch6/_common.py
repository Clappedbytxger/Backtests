"""Shared helpers for prop-challenge batch-6 (ideas I0086-I0088).

Batch 6 = three Robin images + Batch-5 "breadth/decorrelation" directive.
  I0086  MVRV-Z on-chain regime gate (overlay)  -> PIT data-blocker, see REPORT
  I0087  MSCI/FTSE index-rebalance FX flow       -> e2 (Stage-2 proxy only)
  I0088  crypto cross-sectional momentum (5 CTI coins) -> e1

Cost discipline: crypto CFD = the hardest wall (20 bps RT spread + ~8 bps/night
1:2-financing). FX majors ~1.6 bps RT. Every held night pays swap.
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
SPREAD_RT = {"fx": 1.6, "fx_cross": 2.2, "index": 3.0, "gold": 4.0, "crypto": 20.0}
SWAP_PER_NIGHT = {"index": 2.0, "gold": 2.0, "fx": 0.5, "fx_cross": 0.7, "crypto": 8.0}


def load_close(ticker: str, start="2010-01-01") -> pd.Series:
    return get_prices(ticker, start=start)["Close"].dropna()


def ann_sharpe(daily_rets: pd.Series) -> float:
    r = pd.Series(daily_rets).dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * ANN)


def perm_test_rotation(W: pd.DataFrame, R: pd.DataFrame, n: int = 2000, seed: int = 0) -> float:
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


def save_stream(name: str, daily_net: pd.Series) -> None:
    s = pd.Series(daily_net).dropna()
    s.name = name
    s.to_frame().to_parquet(STREAMS / f"{name}.parquet")


def scale_to_vol(daily_net: pd.Series, target_ann_vol: float = 0.10) -> pd.Series:
    s = pd.Series(daily_net).dropna()
    rv = s.std() * ANN
    k = target_ann_vol / rv if rv > 0 else 1.0
    return s * k
