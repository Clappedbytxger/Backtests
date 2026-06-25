"""I0067 STUFE 1 — Faithful Reproduktion des Zarattini "Stocks-in-Play" ORB.

Die Single-Instrument-Adaption (e1) verfehlt den Edge, WEIL die behauptete Sharpe
2,81 in der QUERSCHNITT-Diversifikation eines Aktien-Universums sitzt, nicht im
Einzel-Timing. Hier die Originalform: jeden Tag die Top-K "stocks in play" (höchstes
Relative-Volumen) selektieren, 5-Min-Opening-Range-Breakout long+short, ATR-
Risikoparität (jede Position riskiert gleich viel), viele simultane Positionen,
flat zum Close. Portfolio-Tagesrendite → Sharpe/Alpha vs. die behaupteten Werte.

Daten: XNAS.ITCH 1-Min, 50 liquide Nasdaq-Namen 2018-2026 (quantlab.equities_intraday).
Survivorship-Vorbehalt: heutiges liquides Universum (wie 0074). Für ein INTRADAY-
L/S-Setup (flat overnight, beide Richtungen) ist der Bias milder als bei B&H, aber
vermerkt. Gross + realistische IBKR-Aktienkosten (Stufe 1); CTI-Handelbarkeit ist
Stufe 2 (CTI hat kein Einzelaktien-Universum -> separat).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.equities_intraday import get_equities_intraday

UNI = ['AAPL','MSFT','AMZN','NVDA','GOOGL','TSLA','AVGO','COST','PEP','ADBE','AMD',
       'NFLX','INTC','QCOM','TXN','AMAT','MU','INTU','ISRG','BKNG','ADI','LRCX',
       'KLAC','REGN','GILD','MDLZ','ADP','SBUX','PYPL','CSCO','CMCSA','AMGN','MNST',
       'MAR','ORLY','CTAS','CSX','PCAR','PAYX','ROST','FAST','EA','CHTR','EXC','XEL',
       'IDXX','WBA','EBAY','VRTX','ADSK']

OR_MIN = 5            # opening range = first 5 minutes
RVOL_LB = 20          # trailing days for the relative-volume baseline
TOP_K = 10            # number of "stocks in play" traded per day
STOP_ATR = 0.10       # stop distance as fraction of price (paper: tight ATR stop)
COST_BPS_RT = 4.0     # IBKR liquid stock round-trip (commission + half-spread), bps


def session_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Eastern RTH frame with a per-bar minute-of-session offset."""
    e = C.rth(C.to_eastern(df))
    return e


def per_stock_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Per-session ORB trade for one stock, RISK-PARITY R-multiple.

    Stop = opposite opening-range boundary (the paper's risk unit). Each trade is
    expressed as an R-multiple = direction*(exit-entry)/(entry-stop), so a fixed-%
    risk per name makes the portfolio daily return = mean of R-multiples. Returns
    columns: r (R-multiple net of cost-in-R), rvol (relative 5-min volume)."""
    e = session_frame(df)
    rows = []
    g = e.groupby(e.index.normalize())
    or5_vol = {day: float(gg["Volume"].iloc[:OR_MIN].sum()) for day, gg in g}
    or5 = pd.Series(or5_vol).sort_index()
    base = or5.shift(1).rolling(RVOL_LB, min_periods=5).mean()
    for day, gg in g:
        if len(gg) < OR_MIN + 5:
            continue
        orw = gg.iloc[:OR_MIN]
        or_hi = orw["High"].max(); or_lo = orw["Low"].min()
        rng = or_hi - or_lo
        if rng <= 0:
            continue
        body = gg.iloc[OR_MIN:]
        bu = body["High"] > or_hi; bd = body["Low"] < or_lo
        fu = body.index[bu.values][0] if bu.any() else None
        fd = body.index[bd.values][0] if bd.any() else None
        if fu is None and fd is None:
            continue
        if fu is not None and (fd is None or fu <= fd):
            direction, ts, stop = 1, fu, or_lo
        else:
            direction, ts, stop = -1, fd, or_hi
        after = body.loc[body.index > ts]
        if after.empty:
            continue
        entry = after["Open"].iloc[0]
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        exit_px = after["Close"].iloc[-1]   # time-exit at close
        for _, bar in after.iterrows():
            if direction == 1 and bar["Low"] <= stop:
                exit_px = stop; break
            if direction == -1 and bar["High"] >= stop:
                exit_px = stop; break
        r_gross = direction * (exit_px - entry) / risk
        cost_in_r = (COST_BPS_RT / 1e4) * entry / risk   # round-trip cost in R units
        bval = base.get(day, np.nan)
        rv = or5.get(day, np.nan) / bval if bval and np.isfinite(bval) else np.nan
        rows.append({"date": day, "r_gross": r_gross, "r_net": r_gross - cost_in_r,
                     "rvol": rv})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def build_portfolio():
    data = get_equities_intraday(UNI, "ohlcv-1m", "2018-05-01", "2026-06-01", max_usd=0.01)
    per = {}
    for s in UNI:
        if s in data and not data[s].empty:
            t = per_stock_daily(data[s])
            if not t.empty:
                per[s] = t
    print(f"stocks with trades: {len(per)}")
    # for each date pick top-K by relative volume; equal risk per name -> the
    # portfolio's daily return (in R units) is the MEAN of the selected R-multiples.
    all_dates = sorted(set().union(*[set(t.index) for t in per.values()]))
    daily_gross, daily_net, nsel = [], [], []
    for d in all_dates:
        cands = []
        for s, t in per.items():
            if d in t.index:
                r = t.loc[d]
                if np.isfinite(r["rvol"]):
                    cands.append((s, r["r_gross"], r["r_net"], r["rvol"]))
        if len(cands) < 3:
            continue
        cands.sort(key=lambda x: x[3], reverse=True)  # top relative volume = in play
        sel = cands[:TOP_K]
        # equal risk per name -> deployed risk = risk_frac * n_sel; portfolio daily
        # return = risk_frac * SUM of R-multiples (n_sel may be < K on thin days).
        daily_gross.append((d, float(np.sum([c[1] for c in sel]))))
        daily_net.append((d, float(np.sum([c[2] for c in sel]))))
        nsel.append(len(sel))
    g = pd.Series(dict(daily_gross)).sort_index()
    n = pd.Series(dict(daily_net)).sort_index()
    return g, n, np.mean(nsel)


RISK_FRAC = 0.005  # 0.5% equity risk per name (paper sizes small; Sharpe is invariant)


def stats(sum_r: pd.Series, label: str, risk_frac: float = RISK_FRAC):
    s = risk_frac * sum_r  # daily portfolio return
    ann = s.mean() / s.std(ddof=1) * np.sqrt(252) if s.std(ddof=1) > 0 else 0
    eq = (1 + s).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    cagr = eq.iloc[-1] ** (252 / len(s)) - 1 if eq.iloc[-1] > 0 else float("nan")
    print(f"  {label:10s}: ann.Sharpe {ann:6.3f}  CAGR {cagr*100:7.2f}%  MaxDD {dd*100:6.1f}%  "
          f"total {(eq.iloc[-1]-1)*100:8.1f}%  days {len(s)}  win-day {(s>0).mean():.3f}  "
          f"meanR/day {sum_r.mean():+.3f}")
    return ann, cagr, dd, s


def _naive(idx):
    idx = pd.DatetimeIndex(idx)
    return idx.tz_localize(None) if idx.tz is not None else idx


def alpha_vs_market(daily: pd.Series):
    import glob
    sp = sorted(glob.glob(str(C.CACHE / "SPY_1d_*.parquet")))[-1]
    spy = pd.read_parquet(sp)
    col = "Close" if "Close" in spy.columns else spy.columns[0]
    mr = spy[col].pct_change(); mr.index = _naive(mr.index)
    x = mr.reindex(_naive(daily.index)).values
    y = daily.values
    m = np.isfinite(x) & np.isfinite(y)
    b, a = np.polyfit(x[m], y[m], 1)
    print(f"  vs SPY: beta {b:+.3f}  daily alpha {a*1e4:+.2f}bps  (ann.alpha {a*252*100:+.1f}%)")


def perm_inout(net_sum_r: pd.Series, n=2000, seed=0):
    """IS (2018-2022) vs OOS (2023-2026) Sharpe + permutation vs random direction."""
    is_ = net_sum_r[net_sum_r.index < pd.Timestamp("2023-01-01").tz_localize(net_sum_r.index.tz)]
    oos = net_sum_r[net_sum_r.index >= pd.Timestamp("2023-01-01").tz_localize(net_sum_r.index.tz)]
    for lab, s in [("IS 2018-22", is_), ("OOS 2023-26", oos)]:
        if len(s) > 20:
            ann = s.mean()/s.std(ddof=1)*np.sqrt(252)
            print(f"    {lab}: ann.Sharpe {ann:6.3f}  days {len(s)}")


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    print("=== I0067 STUFE 1 — Stocks-in-Play 5-min ORB cross-sectional portfolio ===")
    print(f"params: OR={OR_MIN}min TOP_K={TOP_K} rvol_lb={RVOL_LB} cost={COST_BPS_RT}bps RT risk/name={RISK_FRAC}")
    g, n, avg_sel = build_portfolio()
    print(f"avg positions/day: {avg_sel:.1f}")
    print("--- gross ---"); stats(g, "gross")
    print("--- net (IBKR ~4bps RT) ---"); _, _, _, net_daily = stats(n, "net")
    alpha_vs_market(net_daily)
    print("--- IS/OOS split ---"); perm_inout(n)
    # save
    out = pd.DataFrame({"gross_sumR": g, "net_sumR": n})
    out.to_csv("results/stocksinplay_orb_daily.csv")
