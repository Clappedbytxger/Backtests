"""Strategy 0086 — Macro regime overlays (I0038 DXY, I0039 yield-slope, I0040 Cu/Au).

Three macro regime-timing ideas from the handoff, each a signal->target overlay.
Tested as: signal-timed long/flat on the target vs buy&hold, with a drift-trap
permutation (does the regime TIMING beat random same-count timing?).

  I0038 USD regime    : DXY 63d momentum < 0 -> long commodity/EM basket (GC,HG,CL,EEM)
  I0039 Yield slope   : 2s10s (FRED T10Y2Y) > 0 / steepening -> SPY, else IEF (vs 60/40)
  I0040 Copper/Gold   : (HG/GC) 63d momentum > 0 -> long SPY (risk-on), else flat

Free data (yfinance + FRED). Overlays, so judged on whether they beat the naive
static allocation AND the permutation.

Run: .venv/Scripts/python.exe strategies/0086_macro_regime/run.py
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices
from quantlab.significance import permutation_test
RESULTS = Path(__file__).resolve().parent / "results"; RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def ns(r): r = r.dropna(); return float(r.mean()/r.std()*ANN) if r.std() else float("nan")


def fred(sid):
    key = (ROOT/".fred.key").read_text().strip()
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}&file_type=json&observation_start=1995-01-01"
    d = json.load(urllib.request.urlopen(url, timeout=30))
    return pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in d["observations"] if o["value"] != "."}).sort_index()


def timed(target_ret, signal_pos):
    """signal_pos decided at close t (we shift), long/flat on target."""
    pos = signal_pos.shift(1).reindex(target_ret.index).fillna(0.0)
    return pos * target_ret, pos


def main():
    out = {}
    # I0038 USD regime
    try:
        dxy = get_prices("DX-Y.NYB", start="2003-01-01")["Close"]
    except Exception:
        dxy = get_prices("UUP", start="2007-01-01")["Close"]
    basket = pd.DataFrame({t: get_prices(t, start="2003-01-01")["Close"] for t in ["GC=F", "HG=F", "CL=F", "EEM"]})
    bret = basket.pct_change().mean(axis=1)
    dmom = dxy.pct_change(63)
    sig = (dmom < 0).astype(float)
    strat, pos = timed(bret, sig)
    perm = permutation_test(strat, bret.reindex(strat.index).fillna(0), pos.reindex(strat.index).fillna(0), n_perm=4000)
    out["I0038_usd"] = {"timed_sharpe": ns(strat), "bh_basket_sharpe": ns(bret), "perm_p": perm["p_value"], "frac_long": float(pos.mean())}
    print(f"I0038 USD-regime: timed Sharpe {ns(strat):+.2f} vs B&H basket {ns(bret):+.2f}, perm p={perm['p_value']:.3f}")

    # I0039 yield slope
    slope = fred("T10Y2Y")
    spy = get_prices("SPY", start="1995-01-01")["Close"].pct_change()
    ief = get_prices("IEF", start="2002-01-01")["Close"].pct_change()
    common = spy.index.intersection(ief.index)
    sl = slope.reindex(common, method="ffill")
    # steepening (positive slope) -> SPY ; else IEF
    w_spy = (sl > 0).astype(float).shift(1).reindex(common).fillna(0.0)
    regime = w_spy * spy.reindex(common).fillna(0) + (1 - w_spy) * ief.reindex(common).fillna(0)
    static = 0.6 * spy.reindex(common).fillna(0) + 0.4 * ief.reindex(common).fillna(0)
    out["I0039_slope"] = {"regime_sharpe": ns(regime), "static_6040_sharpe": ns(static), "frac_spy": float(w_spy.mean())}
    print(f"I0039 Yield-slope: regime Sharpe {ns(regime):+.2f} vs static 60/40 {ns(static):+.2f}")

    # I0040 copper/gold
    hg = get_prices("HG=F", start="2003-01-01")["Close"]
    gc = get_prices("GC=F", start="2003-01-01")["Close"]
    ratio = (hg / gc).dropna()
    rmom = ratio.pct_change(63)
    spyc = get_prices("SPY", start="2003-01-01")["Close"].pct_change()
    sig40 = (rmom.reindex(spyc.index) > 0).astype(float)
    strat40, pos40 = timed(spyc, sig40)
    perm40 = permutation_test(strat40, spyc.reindex(strat40.index).fillna(0), pos40.reindex(strat40.index).fillna(0), n_perm=4000)
    out["I0040_coppergold"] = {"timed_sharpe": ns(strat40), "spy_bh_sharpe": ns(spyc), "perm_p": perm40["p_value"], "frac_long": float(pos40.mean())}
    print(f"I0040 Copper/Gold: timed-SPY Sharpe {ns(strat40):+.2f} vs SPY B&H {ns(spyc):+.2f}, perm p={perm40['p_value']:.3f}")

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
