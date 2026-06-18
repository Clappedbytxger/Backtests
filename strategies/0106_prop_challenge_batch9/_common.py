"""Shared helpers for prop-challenge batch-9 (ideas I0092-I0101).

Batch 9 implements the 10 "better" hypotheses derived in ideas/prop-challenge-batch8.md.
Design principle: exploit the confirmed-LIVING mechanisms (mandate-driven flow,
cointegration-GATED RV-MR, vol/USD-regime overlay, carry-with-crash-gate) and avoid
the confirmed-dead classes (single-CFD intraday direction, thin factors, naive carry).

Every RV-MR sleeve gets a rolling ADF + half-life gate (lesson I0089): no full-sample
stationarity. Cost discipline: spread + overnight swap on every held night.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = Path(__file__).resolve().parent / "results"
STREAMS = RESULTS / "streams"
STREAMS.mkdir(parents=True, exist_ok=True)

from quantlab.data import get_prices  # noqa: E402

ANN = np.sqrt(252)

# CFD cost (round-trip, bps of notional) + overnight swap (per night, bps)
SPREAD_RT = {"fx": 1.6, "fx_cross": 2.2, "index": 3.0, "gold": 4.0, "silver": 6.0, "crypto": 20.0}
SWAP_PER_NIGHT = {"index": 2.0, "gold": 2.0, "silver": 2.0, "fx": 0.5, "fx_cross": 0.7, "crypto": 8.0}


def load_close(t, start="2005-01-01"):
    return get_prices(t, start=start)["Close"].dropna()


def load_ohlc(t, start="2005-01-01"):
    return get_prices(t, start=start)[["Open", "High", "Low", "Close"]].dropna()


def ann_sharpe(r):
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std(ddof=1) * ANN) if len(r) > 2 and r.std(ddof=1) else 0.0


def sharpe_per_trade(r):
    r = np.asarray(r, float); r = r[~np.isnan(r)]
    return float(r.mean() / r.std(ddof=1)) if r.size > 2 and r.std(ddof=1) else 0.0


def cagr_mdd(daily):
    d = pd.Series(daily).dropna()
    if len(d) < 2:
        return 0.0, 0.0
    cagr = (1 + d).prod() ** (252 / len(d)) - 1
    eq = (1 + d).cumprod()
    mdd = (eq / eq.cummax() - 1).min()
    return float(cagr), float(mdd)


def perm_test_sign(x, n=5000, seed=0):
    """Permutation p vs random-sign timing on same |moves| (drift-trap)."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if x.size < 3:
        return float("nan")
    mag, real = np.abs(x), x.mean()
    return (sum((rng.choice([-1.0, 1.0], mag.size) * mag).mean() >= real for _ in range(n)) + 1) / (n + 1)


def perm_test_rotation(W, R, n=2000, seed=0):
    """Timing permutation for held-position sleeves (circular weight rotation)."""
    rng = np.random.default_rng(seed)
    Wv, Rv = np.nan_to_num(W.values), np.nan_to_num(R.values)
    rd = (Wv * Rv).sum(axis=1)
    real = rd.mean() / rd.std() if rd.std() else 0.0
    T = len(Wv); cnt = 0
    for _ in range(n):
        k = int(rng.integers(1, T))
        d = (np.roll(Wv, k, axis=0) * Rv).sum(axis=1)
        cnt += (d.mean() / d.std() if d.std() else 0.0) >= real
    return (cnt + 1) / (n + 1)


def bootstrap_mean_ci(x, n=5000, seed=0, alpha=0.05):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if x.size < 2:
        return float("nan"), float("nan")
    m = np.array([rng.choice(x, x.size, replace=True).mean() for _ in range(n)])
    return float(np.quantile(m, alpha / 2)), float(np.quantile(m, 1 - alpha / 2))


def wilder_rsi(close, period=2):
    d = close.diff()
    up = d.clip(lower=0.0); dn = -d.clip(upper=0.0)
    ru = up.ewm(alpha=1.0 / period, adjust=False).mean()
    rd = dn.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = ru / rd.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def atr(ohlc, period=14):
    h, l, c = ohlc["High"], ohlc["Low"], ohlc["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def rolling_halflife(spread, window=250):
    """Rolling OU half-life (bars) of mean reversion, look-ahead-free."""
    y = spread.values; n = len(y); out = np.full(n, np.nan)
    for i in range(window, n):
        seg = y[i - window:i]; yl = seg[:-1]; dy = np.diff(seg)
        ylc = yl - yl.mean(); den = (ylc ** 2).sum()
        if den == 0:
            continue
        b = (ylc * (dy - dy.mean())).sum() / den
        if b < 0 and (1 + b) > 0:
            out[i] = -np.log(2) / np.log(1 + b)
    return pd.Series(out, index=spread.index)


def rolling_adf_p(spread, window=250, step=5):
    """Trailing ADF p-value every `step` bars, ffill between (look-ahead-free)."""
    y = spread.values; n = len(y); out = np.full(n, np.nan)
    for i in range(window, n, step):
        try:
            out[i] = adfuller(y[i - window:i], maxlag=1, regression="c")[1]
        except Exception:
            pass
    return pd.Series(out, index=spread.index).ffill()


def zscore(s, win):
    return (s - s.rolling(win).mean()) / s.rolling(win).std(ddof=0)


def backtest_spread_mr(legA, legB, *, z_win=60, adf_win=250, adf_p=0.10,
                       hl_lo=10, hl_hi=120, z_entry=2.0, z_exit=0.5, z_stop=3.5,
                       time_stop=30, spread_rt=0.0, swap=0.0, extreme_dec=None,
                       log_ratio=True):
    """Generic gated relative-value mean-reversion on ratio legA/legB.

    Trades a vol-matched A/B spread (~beta-neutral). Entry on z<-entry / z>+entry
    ONLY while a rolling ADF + half-life gate confirms live stationarity (lesson
    I0089). Returns (daily_net, trades[], stats). legA/legB are price Series.
    """
    df = pd.concat([legA.rename("A"), legB.rename("B")], axis=1).dropna()
    a, b = df["A"], df["B"]
    ratio = np.log(a / b) if log_ratio else (a / b)
    z = zscore(ratio, z_win)
    adf = rolling_adf_p(ratio, adf_win)
    hl = rolling_halflife(ratio, adf_win)
    live = (adf.shift(1) <= adf_p) & (hl.shift(1) > hl_lo) & (hl.shift(1) <= hl_hi)
    if extreme_dec is not None:  # only trade |z| in top decile of trailing window
        zabs_thr = z.abs().rolling(extreme_dec).quantile(0.90)
        live = live & (z.abs().shift(1) >= zabs_thr.shift(1))
    rA, rB = a.pct_change(), b.pct_change()
    volA = rA.rolling(20).std(); volB = rB.rolling(20).std()
    z_dec = z.shift(1)
    idx = df.index
    pos = 0; days = 0; trades = []
    daily = pd.Series(0.0, index=idx)
    entry_z = np.nan; wA = wB = 0.0
    for k in range(max(z_win, adf_win) + 2, len(idx)):
        t = idx[k]
        if pos != 0:
            # mark-to-market vol-matched spread leg returns minus swap (both legs)
            daily.loc[t] = pos * (wA * rA.loc[t] - wB * rB.loc[t]) - 2 * swap
            days += 1
            zt = z_dec.loc[t]
            exit_now = abs(zt) < z_exit or abs(zt) > z_stop or days >= time_stop or not bool(live.loc[t])
            if exit_now:
                pos = 0
        if pos == 0 and bool(live.loc[t]) and not np.isnan(z_dec.loc[t]):
            zt = z_dec.loc[t]
            if abs(zt) >= z_entry:
                pos = -1 if zt > 0 else 1  # z>0 ratio rich -> short A/long B
                vA = volA.loc[t]; vB = volB.loc[t]
                if not (vA > 0 and vB > 0):
                    pos = 0; continue
                wA = 1.0; wB = vA / vB  # vol-match B leg to A
                norm = wA + wB
                wA, wB = wA / norm, wB / norm
                entry_z = zt; days = 0
                daily.loc[t] += pos * (wA * rA.loc[t] - wB * rB.loc[t]) - spread_rt - 2 * swap
    daily = daily.dropna()
    # rebuild per-trade returns from contiguous nonzero runs
    seg = []; trs = []
    cur = 0.0; inpos = False
    for v in daily:
        if v != 0:
            cur += v; inpos = True
        elif inpos:
            trs.append(cur); cur = 0.0; inpos = False
    if inpos:
        trs.append(cur)
    return daily, np.array(trs, float)


def save_stream(name, daily_net):
    s = pd.Series(daily_net).dropna(); s.name = name
    s.to_frame().to_parquet(STREAMS / f"{name}.parquet")


def scale_to_vol(daily_net, target=0.10):
    s = pd.Series(daily_net).dropna()
    rv = s.std() * ANN
    return s * (target / rv if rv > 0 else 1.0)
