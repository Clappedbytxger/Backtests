"""I0089 - AUDNZD cointegration mean-reversion (USD-free FX cross).

Gemini S6 (#s40). AUD & NZD are tightly coupled commodity/antipode economies;
the cross oscillates around a time-varying equilibrium band. The cross IS the
stationary residual -> no second leg. Value = decorrelation (USD-free) to the
USD-heavy book (I0075/I0078/I0087).

Rules (faithful to the spec):
  z = (Close - SMA60) / std60      (look-ahead-free, from Close[<= t-1])
  Long  z < -2.0 ; Short z > +2.0  (enter next-bar open)
  Exit  |z| < 0.5 ; Stop |z| > 3.5 (or 35 pips) ; Time-stop 30 trading days
  Stage-0 gate: rolling ADF stationarity + half-life -- trade only while the
  cointegration is live (NOT assumed full-sample). The classic RV mistake.

Daily variant (robust vs microstructure). Cost = cross spread + per-night swap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

from _common import (
    ANN, SPREAD_RT, SWAP_PER_NIGHT, ann_sharpe, bootstrap_mean_ci, load_ohlc,
    perm_test_trades, rolling_halflife, save_stream, sharpe_per_trade,
)

LOOKBACK = 60
Z_ENTRY = 2.0
Z_EXIT = 0.5
Z_STOP = 3.5
TIME_STOP = 30
ADF_WIN = 250        # rolling window for the live stationarity gate
ADF_P = 0.10         # trade only when trailing ADF p <= this
HALFLIFE_MAX = 60    # and half-life is sane (mean-reverting within a month-ish)

SPREAD = SPREAD_RT["fx_cross"] / 1e4      # round-trip, fraction
SWAP = SWAP_PER_NIGHT["fx_cross"] / 1e4   # per night held, fraction


def rolling_adf_p(spread: pd.Series, window: int = ADF_WIN, step: int = 5) -> pd.Series:
    """Trailing ADF p-value, recomputed every `step` bars (ffill between)."""
    y = spread.values
    n = len(y)
    out = np.full(n, np.nan)
    for i in range(window, n, step):
        try:
            out[i] = adfuller(y[i - window : i], maxlag=1, regression="c")[1]
        except Exception:
            pass
    return pd.Series(out, index=spread.index).ffill()


def run(start="2004-01-01", gated=True, verbose=True):
    ohlc = load_ohlc("AUDNZD=X", start=start)
    close = ohlc["Close"]
    pip = 1e-4

    sma = close.rolling(LOOKBACK).mean()
    sd = close.rolling(LOOKBACK).std(ddof=0)
    z = (close - sma) / sd
    # decision-time signal: z known at close[t], act at open[t+1]
    z_dec = z.shift(1)

    adf_p = rolling_adf_p(close) if gated else pd.Series(0.0, index=close.index)
    hl = rolling_halflife(close, window=120) if gated else pd.Series(1.0, index=close.index)
    live = (adf_p.shift(1) <= ADF_P) & (hl.shift(1) > 0) & (hl.shift(1) <= HALFLIFE_MAX)
    if not gated:
        live = pd.Series(True, index=close.index)

    idx = close.index
    opn = ohlc["Open"]
    pos = 0
    entry_px = entry_z = np.nan
    days_held = 0
    trades = []          # signed net return per trade
    daily = pd.Series(0.0, index=idx)  # daily net return stream (mark-to-market)
    last_px = np.nan

    for k in range(LOOKBACK + 1, len(idx)):
        t = idx[k]
        o = opn.loc[t]
        c = close.loc[t]
        zt = z_dec.loc[t]
        # mark-to-market the open position on today's close move
        if pos != 0 and not np.isnan(last_px):
            daily.loc[t] = pos * (c / last_px - 1) - SWAP  # 1 night financing
        last_px = c

        if pos == 0:
            if bool(live.loc[t]) and not np.isnan(zt):
                if zt < -Z_ENTRY:
                    pos, entry_px, entry_z, days_held = 1, o, zt, 0
                    daily.loc[t] += 1 * (c / o - 1) - SPREAD / 2 - SWAP
                    last_px = c
                elif zt > Z_ENTRY:
                    pos, entry_px, entry_z, days_held = -1, o, zt, 0
                    daily.loc[t] += -1 * (c / o - 1) - SPREAD / 2 - SWAP
                    last_px = c
        else:
            days_held += 1
            exit_now = False
            if abs(zt) < Z_EXIT:                       # reversion done
                exit_now = True
            elif abs(zt) > Z_STOP:                     # regime break
                exit_now = True
            elif pos == 1 and (entry_px - o) > 35 * pip:   # 35-pip stop
                exit_now = True
            elif pos == -1 and (o - entry_px) > 35 * pip:
                exit_now = True
            elif days_held >= TIME_STOP:
                exit_now = True
            if exit_now:
                ret = pos * (o / entry_px - 1) - SPREAD - SWAP * days_held
                trades.append(ret)
                pos = 0

    daily = daily.dropna()
    trades = np.array(trades, float)
    if verbose:
        tag = "GATED" if gated else "ungated"
        print(f"\n=== I0089 AUDNZD coint-MR ({tag}) ===")
        print(f"trades={len(trades)}  win={np.mean(trades>0):.1%}  "
              f"meanR={trades.mean()*1e4:+.1f}bps  sumR={trades.sum()*100:+.1f}%")
        print(f"daily-net ann.Sharpe={ann_sharpe(daily):.2f}  "
              f"per-trade Sharpe={sharpe_per_trade(trades):.3f}")
        if len(trades) > 5:
            print(f"perm(random-sign) p={perm_test_trades(trades):.3f}  "
                  f"boot meanR CI={tuple(round(x*1e4,1) for x in bootstrap_mean_ci(trades))} bps")
        cagr = (1 + daily).prod() ** (252 / len(daily)) - 1 if len(daily) else 0
        eq = (1 + daily).cumprod()
        mdd = (eq / eq.cummax() - 1).min()
        print(f"net CAGR={cagr:+.2%}  MaxDD={mdd:.1%}  yrs={len(daily)/252:.1f}")
    return daily, trades


if __name__ == "__main__":
    d_g, t_g = run(gated=True)
    d_u, t_u = run(gated=False)
    # IS/OOS split on gated
    n = len(d_g)
    is_, oos = d_g.iloc[: n // 2], d_g.iloc[n // 2 :]
    print(f"\nIS/OOS gated daily-Sharpe: IS={ann_sharpe(is_):.2f}  OOS={ann_sharpe(oos):.2f}")
    save_stream("i0089_audnzd_mr", d_g)
