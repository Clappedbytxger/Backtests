"""I0068 - Intraday-Momentum "Noise-Area-Boundary" (Zarattini & Aziz 2024).

"Beat the Market: An Effective Intraday Momentum Strategy for SPY" (SSRN 4824172)
claims SPY 2007-2024 +1,985% net, Sharpe 1.33 (B&H 0.45), and Sharpe 3.50 when
VIX>40. This is the strongest single-instrument peer evidence in the batch, so we
reproduce the rule faithfully on ES (SPY analog) and NQ.

Rule (faithful):
  - For each minute-of-session m, boundary(m) = sigma * mean over the last `lb`
    sessions of |Close(m)/Open_today - 1| -> the intraday vol "noise" envelope.
  - Bands: UB(m) = Open_today*(1+boundary(m)), LB(m) = Open_today*(1-boundary(m)).
  - When Close(m) > UB(m): be long; when Close(m) < LB(m): be short; else hold the
    last side. Position changes act on the NEXT bar (decision-time safe).
  - Trailing stop at VWAP (exit if price crosses back through VWAP against you).
  - Flat at session close.
Cost: CFD_INDEX (3 bps round-trip) charged per position change.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.costs import CFD_INDEX

LOOKBACK = 14
SIGMA = 1.0


def minute_index(g: pd.DataFrame) -> np.ndarray:
    base = g.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
    return ((g.index - base) / pd.Timedelta(minutes=1)).astype(int).values


def build_boundary(df_rth: pd.DataFrame, lb: int = LOOKBACK):
    """Return per-(date,minute) boundary fraction from the trailing `lb` days."""
    recs = {}
    for day, g in C.sessions(df_rth):
        op = g["Open"].iloc[0]
        mi = minute_index(g)
        absmove = np.abs(g["Close"].values / op - 1.0)
        recs[day] = pd.Series(absmove, index=mi)
    panel = pd.DataFrame(recs).T.sort_index()  # rows=date, cols=minute
    # trailing mean of |move| per minute, shifted so day t uses only days < t
    boundary = panel.shift(1).rolling(lb, min_periods=5).mean()
    return panel, boundary


def run_symbol(symbol: str, label: str, sigma: float = SIGMA, use_vwap_stop: bool = True):
    df = C.rth(C.to_eastern(C.load(symbol)))
    _, boundary = build_boundary(df)
    cost_side = CFD_INDEX.slippage_bps + CFD_INDEX.regulatory_bps  # bps per change
    day_rets = []
    for day, g in C.sessions(df):
        if day not in boundary.index:
            continue
        b = boundary.loc[day].dropna()
        if b.empty or len(g) < 60:
            continue
        op = g["Open"].iloc[0]
        mi = minute_index(g)
        o_arr = g["Open"].values
        close = g["Close"].values
        bvals = b.reindex(mi).ffill().values
        ub = op * (1 + sigma * bvals)
        lb_ = op * (1 - sigma * bvals)
        nb = len(g)
        nxt_ret = np.zeros(nb)
        nxt_ret[:-1] = (close[1:] - o_arr[1:]) / o_arr[1:]
        # Pure intraday-momentum band: long above UB, short below LB, else CARRY
        # the last side (low-turnover, ~1-4 changes/day, matches the paper).
        des = np.where(close > ub, 1.0, np.where(close < lb_, -1.0, np.nan))
        des[np.isnan(bvals)] = np.nan
        pos = pd.Series(des).ffill().fillna(0.0).values
        if use_vwap_stop:
            tp = (g["High"].values + g["Low"].values + close) / 3.0
            vol = g["Volume"].values.astype(float)
            cum_v = np.cumsum(vol); cum_pv = np.cumsum(tp * vol)
            vwap = np.where(cum_v > 0, cum_pv / np.maximum(cum_v, 1), close)
            # flatten to 0 when price is on the wrong side of VWAP
            wrong = ((pos == 1) & (close < vwap)) | ((pos == -1) & (close > vwap))
            pos = np.where(wrong, 0.0, pos)
        gross = float(np.nansum(pos * nxt_ret))
        changes = int(np.sum(np.abs(np.diff(np.concatenate([[0.0], pos])) ) > 0))
        net = gross - changes * 2 * cost_side / 1e4
        day_rets.append({"date": day, "gross": gross, "net": net, "changes": changes})
    t = pd.DataFrame(day_rets).set_index("date")
    if t.empty:
        print(f"  {label}: no data"); return None
    # attach VIX (daily close) for the regime claim
    try:
        import glob
        vp = sorted(glob.glob(str(C.CACHE / "idx_VIX_1d_*.parquet")))[-1]
        vx = pd.read_parquet(vp)
        vcol = "Close" if "Close" in vx.columns else vx.columns[0]
        vser = vx[vcol]; vser.index = pd.to_datetime(vser.index).tz_localize(None)
        t["vix"] = vser.reindex(t.index.tz_localize(None)).values
    except Exception as e:
        t["vix"] = np.nan
    print(f"\n=== {label} ({symbol}, {len(t)} sessions) ===")
    print(f"  trades/day avg: {t['changes'].mean():.2f}")
    for col in ("gross", "net"):
        s = t[col]
        print(f"  {col:5s}: mean/day {s.mean()*1e4:7.3f} bps  ann.Sharpe {C.ann_sharpe_daily(s):6.3f}  "
              f"total {s.sum()*100:7.1f}%  win-day {(s>0).mean():.3f}")
    for thr in (20, 30, 40):
        m = t["vix"] > thr
        if m.sum() > 20:
            s = t.loc[m, "net"]
            print(f"   VIX>{thr}: n={m.sum():4d} netSharpe {C.ann_sharpe_daily(s):6.3f} "
                  f"net mean/day {s.mean()*1e4:7.3f}bps")
    return t


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    for sym, lab in [("ES", "I0068 ES (SPY analog)"), ("NQ", "I0068 NQ")]:
        for sg in (0.5, 1.0):
            run_symbol(sym, f"{lab} sigma={sg}", sigma=sg)
