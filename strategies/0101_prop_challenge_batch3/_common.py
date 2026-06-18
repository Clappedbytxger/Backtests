"""Shared helpers for the prop-challenge batch-3 screen (ideas I0067-I0074).

All ideas are intraday on a single liquid CTI-tradable instrument (index/gold/FX
CFD or BTC). The framework's robust prior is that liquid-index intraday DIRECTION
is empty net of cost (rejects 0012-0015 / 0038-0041 / 0049). These ideas are
"umgeht-Reject" candidates: we reproduce each rule faithfully, measure the GROSS
edge first (the 4-line killer, lesson 0049), and only if a gross pulse survives do
we charge the CFD cost gate (CFD_INDEX / CFD_GOLD / CFD_FX) and run the battery.

Data: cached 1-min Databento bars (ES/NQ/GC) and GBPUSD M15 (Dukascopy). UTC
index -> converted to US/Eastern for index/gold RTH sessions.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"

PATHS = {
    "ES": CACHE / "futures" / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet",
    "NQ": CACHE / "futures" / "NQ_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet",
    "GC": CACHE / "futures" / "GC_v_0_ohlcv-1m_2016-01-01_2026-05-31.parquet",
    "6B": CACHE / "futures" / "6B_v_0_ohlcv-1m_2016-01-01_2026-05-31.parquet",
    "GBPUSD_M15": CACHE / "fx" / "GBPUSD_M15.parquet",
    "BTC_1h": CACHE / "crypto" / "binance_BTC_USDT_1h.parquet",
}


def load(symbol: str) -> pd.DataFrame:
    """Load a cached intraday OHLCV frame, UTC-indexed, columns O/H/L/C/V."""
    df = pd.read_parquet(PATHS[symbol])
    if df.index.tz is None:
        df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    # normalise column names
    ren = {c: c.capitalize() for c in df.columns}
    df = df.rename(columns=ren)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep].copy()


def to_eastern(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = out.index.tz_convert("US/Eastern")
    return out


def rth(df_et: pd.DataFrame) -> pd.DataFrame:
    """Filter an Eastern-time frame to the RTH cash session 09:30-16:00."""
    t = df_et.index.time
    mask = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    return df_et[mask]


def sessions(df_et: pd.DataFrame):
    """Group an Eastern frame by calendar date (one RTH session each)."""
    return df_et.groupby(df_et.index.normalize())


# ── stats helpers ────────────────────────────────────────────────────────────

def sharpe_per_trade(rets: np.ndarray) -> float:
    rets = np.asarray(rets, float)
    rets = rets[~np.isnan(rets)]
    if rets.size < 2 or rets.std(ddof=1) == 0:
        return 0.0
    return rets.mean() / rets.std(ddof=1)


def ann_sharpe_daily(daily_rets: pd.Series) -> float:
    r = daily_rets.dropna()
    if r.std(ddof=1) == 0 or len(r) < 2:
        return 0.0
    return r.mean() / r.std(ddof=1) * np.sqrt(252)


def perm_test_timing(per_day_signed_ret: pd.Series, n: int = 2000, seed: int = 0) -> float:
    """Permutation p-value vs random-sign timing on the SAME days.

    Null: the sign/timing carries no edge -> a random +/-1 per day on the same
    absolute daily move should match. One-sided (real mean > null mean).
    """
    rng = np.random.default_rng(seed)
    mag = per_day_signed_ret.abs().values
    real = per_day_signed_ret.mean()
    cnt = 0
    for _ in range(n):
        s = rng.choice([-1.0, 1.0], size=mag.size)
        if (s * mag).mean() >= real:
            cnt += 1
    return (cnt + 1) / (n + 1)


def bootstrap_mean_ci(x: np.ndarray, n: int = 5000, seed: int = 0, alpha: float = 0.05):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    means = np.array([rng.choice(x, x.size, replace=True).mean() for _ in range(n)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def summarize(label: str, signed_rets: np.ndarray, cost_rt_bps: float) -> dict:
    """Gross + net per-trade stats for a stream of signed trade returns (fraction)."""
    r = np.asarray(signed_rets, float)
    r = r[~np.isnan(r)]
    n = r.size
    gross_mean_bps = r.mean() * 1e4
    net = r - cost_rt_bps / 1e4
    net_mean_bps = net.mean() * 1e4
    return {
        "label": label,
        "n": int(n),
        "gross_bps": round(gross_mean_bps, 3),
        "gross_sharpe": round(sharpe_per_trade(r), 4),
        "net_bps": round(net_mean_bps, 3),
        "net_sharpe": round(sharpe_per_trade(net), 4),
        "win": round((r > 0).mean(), 4),
        "cost_rt_bps": cost_rt_bps,
    }
