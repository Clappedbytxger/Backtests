"""Strategy 0091 — Combined live book: per-sleeve metrics + portfolio combination.

Reconstructs each live-calendar strategy as a DAILY net-of-cost return stream
(each sleeve on its own notional, flat = 0 return), then reports:
  1. per-sleeve metrics (active-day Sharpe, full Sharpe, CAGR, MaxDD, %time active,
     trades/yr, mean per-trade),
  2. the correlation matrix between sleeves (the diversification case),
  3. the COMBINED book (equal-weight 1/N and inverse-vol risk-parity) with its
     Sharpe / CAGR / MaxDD vs the average standalone sleeve.

Sleeves reconstructible on daily data: seasonal futures legs (Benzin/Mastrind/
Platin/Baumwolle/Mais), Turn-of-Month (0050), EOM-Treasury (0075), Auction-short
(0078), VIX-carry (0056). Pre-FOMC (overnight) and the crypto monthly book need
intraday / cross-sectional data and are reported standalone, NOT in the daily curve.

Run: .venv/Scripts/python.exe strategies/0091_combined_book/run.py
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF, MES_INTRADAY
from quantlab.data import get_prices
from quantlab.backtest import run_backtest
from quantlab.metrics import compute_metrics, trade_stats
from quantlab.seasonal import event_signal, date_window_signal, turn_of_month_signal
RESULTS = Path(__file__).resolve().parent / "results"; RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def asd(r):  # annualised Sharpe on active (nonzero) days
    a = r[r != 0]
    return float(a.mean()/a.std()*ANN) if len(a) > 1 and a.std() else float("nan")


def sleeve_from_signal(ticker, sig_fn, cost, direction=1, start="2004-01-01"):
    p = get_prices(ticker, start=start)
    sig = direction * sig_fn(p.index)
    bt = run_backtest(p, sig, cost_model=cost)
    return bt["returns"], bt, p


def auction_short_returns(start="2004-01-01"):
    terms = {"30-Year", "29-Year 11-Month", "29-Year 10-Month", "29-Year 9-Month"}
    cache = ROOT / "strategies/0078_treasury_auction/results/auctions_bond.json"
    data = json.loads(cache.read_text())
    auc = pd.DatetimeIndex(sorted({x["auctionDate"][:10] for x in data
                                   if x["securityTerm"] in terms and x["auctionDate"][:10] >= start}))
    tlt = get_prices("TLT", start=start)
    idx = tlt.index
    s = np.zeros(len(idx))
    for d in auc:
        a = idx.searchsorted(d)
        if 0 <= a < len(idx):
            s[max(0, a-5):a] = -1.0
    bt = run_backtest(tlt, pd.Series(s, index=idx), cost_model=IBKR_LIQUID_ETF)
    return bt["returns"], bt, tlt


FOMC = [  # 2000-2026 scheduled announcement days (from 0052/0076)
    "2000-02-02","2000-03-21","2000-05-16","2000-06-28","2000-08-22","2000-10-03","2000-11-15","2000-12-19",
    "2001-01-31","2001-03-20","2001-05-15","2001-06-27","2001-08-21","2001-10-02","2001-11-06","2001-12-11",
    "2002-01-30","2002-03-19","2002-05-07","2002-06-26","2002-08-13","2002-09-24","2002-11-06","2002-12-10",
    "2003-01-29","2003-03-18","2003-05-06","2003-06-25","2003-08-12","2003-09-16","2003-10-28","2003-12-09",
    "2004-01-28","2004-03-16","2004-05-04","2004-06-30","2004-08-10","2004-09-21","2004-11-10","2004-12-14",
    "2005-02-02","2005-03-22","2005-05-03","2005-06-30","2005-08-09","2005-09-20","2005-11-01","2005-12-13",
    "2006-01-31","2006-03-28","2006-05-10","2006-06-29","2006-08-08","2006-09-20","2006-10-25","2006-12-12",
    "2007-01-31","2007-03-21","2007-05-09","2007-06-28","2007-08-07","2007-09-18","2007-10-31","2007-12-11",
    "2008-01-30","2008-03-18","2008-04-30","2008-06-25","2008-08-05","2008-09-16","2008-10-29","2008-12-16",
    "2009-01-28","2009-03-18","2009-04-29","2009-06-24","2009-08-12","2009-09-23","2009-11-04","2009-12-16",
    "2010-01-27","2010-03-16","2010-04-28","2010-06-23","2010-08-10","2010-09-21","2010-11-03","2010-12-14",
    "2011-01-26","2011-03-15","2011-04-27","2011-06-22","2011-08-09","2011-09-21","2011-11-02","2011-12-13",
    "2012-01-25","2012-03-13","2012-04-25","2012-06-20","2012-08-01","2012-09-13","2012-10-24","2012-12-12",
    "2013-01-30","2013-03-20","2013-05-01","2013-06-19","2013-07-31","2013-09-18","2013-10-30","2013-12-18",
    "2014-01-29","2014-03-19","2014-04-30","2014-06-18","2014-07-30","2014-09-17","2014-10-29","2014-12-17",
    "2015-01-28","2015-03-18","2015-04-29","2015-06-17","2015-07-29","2015-09-17","2015-10-28","2015-12-16",
    "2016-01-27","2016-03-16","2016-04-27","2016-06-15","2016-07-27","2016-09-21","2016-11-02","2016-12-14",
    "2017-02-01","2017-03-15","2017-05-03","2017-06-14","2017-07-26","2017-09-20","2017-11-01","2017-12-13",
    "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
    "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
    "2020-01-29","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
    "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
    "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
    "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
    "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
    "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
    "2026-01-28","2026-03-18","2026-04-29",
]


def prefomc_returns(start="2004-01-01"):
    """0052 overnight into the announcement: Open[A]/Close[A-1]-1 on FOMC days."""
    spy = get_prices("SPY", start=start)
    on = spy["Open"] / spy["Close"].shift(1) - 1.0
    fomc = pd.to_datetime(FOMC)
    mask = spy.index.normalize().isin(fomc.normalize())
    r = pd.Series(0.0, index=spy.index)
    r[mask] = on[mask].values
    return r.fillna(0.0), None, spy


def usd_regime_returns(start="2004-01-01", lb=63):
    try:
        dxy = get_prices("DX-Y.NYB", start=start)["Close"]
    except Exception:
        dxy = get_prices("UUP", start="2007-01-01")["Close"]
    basket = pd.DataFrame({t: get_prices(t, start=start)["Close"] for t in ["GC=F", "HG=F", "CL=F", "EEM"]})
    bret = basket.pct_change().mean(axis=1)
    sig = (dxy.pct_change(lb) < 0).astype(float).reindex(bret.index).ffill().shift(1).fillna(0.0)
    return (sig * bret).fillna(0.0), None, None


def wheat_rv_returns(start="2004-01-01", lb=252, entry=2.0):
    zw = get_prices("ZW=F", start=start)["Close"]
    ke = get_prices("KE=F", start=start)["Close"]
    ix = zw.index.intersection(ke.index)
    spread = (np.log(zw.reindex(ix)) - np.log(ke.reindex(ix)))
    z = (spread - spread.rolling(lb).mean()) / spread.rolling(lb).std()
    sret = spread.diff()
    pos = pd.Series(0.0, index=spread.index); cur = 0.0
    for i in range(len(z)):
        zz = z.iloc[i]
        if np.isnan(zz):
            pos.iloc[i] = cur; continue
        if cur == 0.0:
            cur = -1.0 if zz > entry else (1.0 if zz < -entry else 0.0)
        elif (cur > 0 and zz >= 0) or (cur < 0 and zz <= 0):
            cur = 0.0
        pos.iloc[i] = cur
    held = pos.shift(1).fillna(0.0)
    net = held * sret - held.diff().abs().fillna(0.0) * (4.0/1e4)
    return net.fillna(0.0), None, None


def vix_carry_returns(start="2011-01-01", factor=0.149):
    vixy = get_prices("VIXY", start=start)
    vix = get_prices("^VIX", start=start)["Close"]
    vix3m = get_prices("^VIX3M", start=start)["Close"]
    ratio = (vix3m / vix).reindex(vixy.index).ffill()
    short = (ratio > 1.03).astype(float)  # contango -> short
    sig = -short * factor
    bt = run_backtest(vixy, sig, cost_model=IBKR_LIQUID_ETF)
    return bt["returns"], bt, vixy


def main():
    out = {}
    sleeves = {}
    bts = {}
    # seasonal legs
    defs = [
        ("benzin_kw9", "RB=F", lambda i: event_signal(i, 9, 5), IBKR_FUTURES, 1),
        ("mastrind_kw21", "GF=F", lambda i: event_signal(i, 21, 5), IBKR_FUTURES, 1),
        ("platin_yearend", "PL=F", lambda i: date_window_signal(i, (12, 18), (1, 10)), IBKR_FUTURES, 1),
        ("baumwolle", "CT=F", lambda i: date_window_signal(i, (11, 21), (12, 29)), IBKR_FUTURES, 1),
        ("mais_dez", "ZC=F", lambda i: date_window_signal(i, (12, 8), (12, 18)), IBKR_FUTURES, 1),
        ("turn_of_month", "SPY", lambda i: turn_of_month_signal(i, 1, 3), MES_INTRADAY, 1),
        ("eom_treasury", "TLT", lambda i: turn_of_month_signal(i, 2, 0), IBKR_LIQUID_ETF, 1),
    ]
    for name, tk, fn, cost, d in defs:
        r, bt, p = sleeve_from_signal(tk, fn, cost, d)
        sleeves[name] = r; bts[name] = (bt, p)
    r, bt, p = auction_short_returns(); sleeves["auction_short"] = r; bts["auction_short"] = (bt, p)
    r, bt, p = vix_carry_returns(); sleeves["vix_carry"] = r; bts["vix_carry"] = (bt, p)
    # sleeves without a standard trade-log (reconstructed return streams)
    for nm, fn in [("pre_fomc", prefomc_returns), ("usd_regime", usd_regime_returns), ("wheat_rv", wheat_rv_returns)]:
        r, _, _ = fn()
        sleeves[nm] = r
        bts[nm] = (None, None)

    # align on a common index (union of dates), fill flat=0
    allret = pd.DataFrame(sleeves).sort_index()
    allret = allret[allret.index >= "2004-01-01"]

    # per-sleeve metrics
    print(f"{'sleeve':16}{'fullShrp':>9}{'actShrp':>9}{'CAGR%':>8}{'MaxDD%':>8}{'%active':>8}{'trades':>7}{'exp%/tr':>8}")
    out["sleeves"] = {}
    for name in sleeves:
        bt, p = bts[name]
        r = sleeves[name].dropna()
        m = compute_metrics(r)
        if bt is not None and len(bt["trades"]):
            ts = trade_stats(bt["trades"])
        else:
            # reconstructed stream: count active blocks as "trades", mean active-block return
            active = (r != 0).astype(int)
            n_blocks = int(((active.diff() == 1)).sum()) or int(active.sum())
            ts = {"n_trades": n_blocks, "expectancy": float(r[r != 0].mean()) if (r != 0).any() else 0.0}
        yrs = (r.index.max() - r.index.min()).days / 365.25
        rec = {"full_sharpe": m["sharpe"], "active_sharpe": asd(r), "cagr_pct": float(m["cagr"]*100),
               "maxdd_pct": float(m["max_drawdown"]*100), "pct_active": float((r != 0).mean()*100),
               "trades_per_yr": round(ts["n_trades"]/yrs, 1), "exp_per_trade_pct": float(ts["expectancy"]*100),
               "n_trades": ts["n_trades"]}
        out["sleeves"][name] = rec
        print(f"{name:16}{rec['full_sharpe']:>9.2f}{rec['active_sharpe']:>9.2f}{rec['cagr_pct']:>8.1f}"
              f"{rec['maxdd_pct']:>8.1f}{rec['pct_active']:>8.1f}{rec['trades_per_yr']:>7.1f}{rec['exp_per_trade_pct']:>+8.2f}")

    # correlation matrix (on active overlap)
    corr = allret.fillna(0.0).corr()
    out["correlation"] = corr.round(3).to_dict()
    print("\nCorrelation matrix (daily returns):")
    print(corr.round(2).to_string())

    # combined book: equal-weight 1/N and inverse-vol risk-parity (common window 2011+)
    common = allret[allret.index >= "2011-06-01"].fillna(0.0)  # VIXY starts 2011
    N = common.shape[1]
    ew = common.mean(axis=1)  # equal capital 1/N
    vol = common.std().replace(0, np.nan)
    w_rp = (1/vol) / (1/vol).sum()
    rp = (common * w_rp).sum(axis=1)
    for label, series, w in [("equal_weight", ew, {c: 1/N for c in common.columns}),
                             ("risk_parity", rp, w_rp.round(3).to_dict())]:
        m = compute_metrics(series)
        out[f"combined_{label}"] = {"sharpe": m["sharpe"], "cagr_pct": float(m["cagr"]*100),
                                    "maxdd_pct": float(m["max_drawdown"]*100),
                                    "ann_vol_pct": float(series.std()*ANN*100),
                                    "weights": w if isinstance(w, dict) else w}
        print(f"\nCombined {label} (2011-2026, {N} sleeves): Sharpe {m['sharpe']:+.2f}, "
              f"CAGR {m['cagr']*100:+.1f}%, MaxDD {m['max_drawdown']*100:.1f}%, vol {series.std()*ANN*100:.1f}%")
    avg_sleeve_sharpe = float(np.nanmean([out["sleeves"][n]["full_sharpe"] for n in common.columns]))
    out["avg_standalone_full_sharpe"] = avg_sleeve_sharpe
    print(f"\nDiversification: combined EW Sharpe {out['combined_equal_weight']['sharpe']:.2f} "
          f"vs avg standalone {avg_sleeve_sharpe:.2f}")

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    corr.to_csv(RESULTS / "correlation.csv")


if __name__ == "__main__":
    main()
