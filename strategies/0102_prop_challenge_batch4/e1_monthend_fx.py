"""I0075 - Month-end FX rebalancing flow (WMR 4pm London fix), FX-CFD basket.

Mechanism (Melvin & Prins 2015): foreign real-money hedgers restore their USD
hedge ratio at the 16:00 London fix on the last business day (LBD). Equities up
in the month -> under-hedged -> sell USD into the fix. So:
    sign(month-to-date equity return through LBD-1)  >0  ->  SHORT USD basket
    (long EURUSD/GBPUSD/AUDUSD, short USDCHF/USDJPY).

Stage-1 reproduction on free data, two reads:
  (A) DAILY basket directional test: does sign(equity MTD) predict the LBD
      close->close move of the USD-short basket?  (full-day proxy, noisier than
      the fix window but the honest free-data directional read; permutation vs
      random months = drift-trap test.)
  (B) GBPUSD M15 FIX-WINDOW test (the real microstructure claim, one pair we have
      intraday for): entry 15:00 London, exit 16:30 London on the LBD, signed by
      the equity sign. Gross then net of the FX spread.

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/e1_monthend_fx.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

PAIRS = {  # ticker -> +1 if xxxUSD (USD-short = long), -1 if USDxxx (USD-short = short pair)
    "EURUSD=X": +1, "GBPUSD=X": +1, "AUDUSD=X": +1, "USDCHF=X": -1, "USDJPY=X": -1,
}


def month_to_date_equity_sign(eq_close: pd.Series) -> pd.Series:
    """For each LBD, sign of equity return from first trading day of month to LBD-1 close.

    Decision-time safe: uses data only up to LBD-1 close; the sign is known before
    the LBD entry.
    """
    eq = eq_close.dropna()
    grp = eq.groupby([eq.index.year, eq.index.month])
    out = {}
    for (y, m), s in grp:
        s = s.sort_index()
        if len(s) < 3:
            continue
        lbd = s.index[-1]
        # MTD return through LBD-1 (the day before the last business day)
        mtd = s.iloc[-2] / s.iloc[0] - 1.0
        out[lbd] = np.sign(mtd)
    return pd.Series(out).sort_index()


def daily_basket_test(eq_sign: pd.Series) -> dict:
    closes = {t: get_prices(t, start="2003-01-01")["Close"] for t in PAIRS}
    px = pd.DataFrame(closes).dropna(how="all")
    # LBD close-to-close return per pair
    rets = px.pct_change()
    events = []
    for lbd, sgn in eq_sign.items():
        if lbd not in rets.index or np.isnan(sgn) or sgn == 0:
            continue
        row = rets.loc[lbd]
        legs = []
        for t, usd_short in PAIRS.items():
            r = row.get(t, np.nan)
            if np.isnan(r):
                continue
            legs.append(usd_short * r)  # USD-short stance return for this leg
        if not legs:
            continue
        basket = np.mean(legs)
        events.append((lbd, sgn * basket))  # sign by equity direction
    s = pd.Series(dict(events)).sort_index()
    gross_bps = s.mean() * 1e4
    net = s - C.SPREAD_RT["fx"] / 1e4  # round-trip spread on the basket entry/exit
    lo, hi = C.bootstrap_mean_ci(s.values)
    return {
        "n_events": int(len(s)),
        "gross_mean_bps": round(float(gross_bps), 3),
        "net_mean_bps": round(float(net.mean() * 1e4), 3),
        "gross_sharpe_per_event": round(C.sharpe_per_trade(s.values), 4),
        "win": round(float((s > 0).mean()), 4),
        "perm_p_vs_random_months": round(C.perm_test_timing(s), 4),
        "boot_mean_ci_bps": [round(lo * 1e4, 3), round(hi * 1e4, 3)],
        "period": f"{s.index.min().date()}..{s.index.max().date()}",
    }


def gbp_fix_window_test(eq_sign: pd.Series) -> dict:
    df = pd.read_parquet(C.CACHE / "fx" / "GBPUSD_M15.parquet")
    if df.index.tz is None:
        df.index = pd.to_datetime(df.index, utc=True)
    lon = df.tz_convert("Europe/London")
    close = lon["Close"]
    # for each calendar date, get price nearest 15:00 and 16:30 London
    by_date = close.groupby(close.index.normalize())
    win = {}
    for day, s in by_date:
        s = s.sort_index()
        t = s.index.time
        entry = s[(t >= pd.Timestamp("15:00").time()) & (t < pd.Timestamp("15:30").time())]
        exit_ = s[(t >= pd.Timestamp("16:30").time()) & (t < pd.Timestamp("17:00").time())]
        if len(entry) and len(exit_):
            win[day.tz_localize(None).normalize()] = exit_.iloc[0] / entry.iloc[0] - 1.0
    win = pd.Series(win).sort_index()
    # align to LBD events (eq_sign index is tz-naive normalized dates? -> normalize)
    eqs = eq_sign.copy()
    eqs.index = pd.DatetimeIndex(eqs.index).normalize()
    events = []
    for lbd, sgn in eqs.items():
        if lbd not in win.index or np.isnan(sgn) or sgn == 0:
            continue
        # GBPUSD is xxxUSD -> USD-short = long GBPUSD = +window return
        events.append((lbd, sgn * win.loc[lbd]))
    s = pd.Series(dict(events)).sort_index()
    if len(s) < 5:
        return {"n_events": int(len(s)), "note": "insufficient overlap"}
    net = s - C.SPREAD_RT["fx"] / 1e4
    lo, hi = C.bootstrap_mean_ci(s.values)
    return {
        "n_events": int(len(s)),
        "gross_mean_bps": round(float(s.mean() * 1e4), 3),
        "net_mean_bps": round(float(net.mean() * 1e4), 3),
        "gross_sharpe_per_event": round(C.sharpe_per_trade(s.values), 4),
        "win": round(float((s > 0).mean()), 4),
        "perm_p_vs_random_months": round(C.perm_test_timing(s), 4),
        "boot_mean_ci_bps": [round(lo * 1e4, 3), round(hi * 1e4, 3)],
        "period": f"{s.index.min().date()}..{s.index.max().date()}",
    }


def main() -> None:
    eq = get_prices("^GSPC", start="2003-01-01")["Close"]
    eq_sign = month_to_date_equity_sign(eq)
    out = {"idea": "I0075", "name": "Month-end FX rebalancing flow (WMR 4pm fix)"}
    print("=== I0075 Month-end FX flow ===")
    out["daily_basket"] = daily_basket_test(eq_sign)
    print("DAILY basket (5 majors, USD-short when equity up):")
    for k, v in out["daily_basket"].items():
        print(f"  {k}: {v}")
    out["gbp_fix_window"] = gbp_fix_window_test(eq_sign)
    print("GBPUSD M15 FIX window (15:00->16:30 London on LBD):")
    for k, v in out["gbp_fix_window"].items():
        print(f"  {k}: {v}")
    (RESULTS / "e1_monthend_fx.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
