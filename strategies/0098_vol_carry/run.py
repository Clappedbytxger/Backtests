"""Strategy 0098 — VIX Roll-Down Carry slope-gated (I0064) + Cross-Asset VRP (I0065).

Batch-2 ideas from `D:\\Backtest Ideas` (#s24). Both extend the CONFIRMED VRP family
0054/0056 (short-vol carry, real edge but tail-dangerous).

I0064 (Contango-Harvest): short VIX (via short VIXY) ONLY when the VIX term structure
is in steep contango (VIX3M/VIX > threshold), flat at backwardation. Hypothesis: the
slope gate cuts the short-gamma crash tail (the 0056 problem) while keeping the carry.
MUST survive Feb-2018 (Volmageddon) and Mar-2020 stress sub-periods.

I0065 (Cross-Asset VRP dispersion): the variance risk premium exists in bond/FX/
commodity vol too (MOVE, ^EVZ FX, ^GVZ gold, ^OVX oil), not just equity (VIX). Rank
VRP across classes, short where richest. BLOCKER (idea-flagged): only EQUITY vol has a
liquid retail short-vol instrument (VIXY/SVXY) — bond/FX/commodity short-vol needs
options. We test the SIGNAL (does cross-asset VRP ranking carry information?) and judge
the tradable implication honestly.

Free data: yfinance (^VIX/^VIX3M/VIXY/SVXY/^MOVE/^GVZ/^OVX/^EVZ + SPY/GLD/USO/FXE/IEF).

Run: .venv/Scripts/python.exe strategies/0098_vol_carry/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import permutation_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    m = compute_metrics(r)
    return {"sharpe": ns(r), "cagr_pct": float(m["cagr"] * 100),
            "maxdd_pct": float(m["max_drawdown"] * 100),
            "worst_day_pct": float(r.min() * 100), "kurtosis": float(r.kurtosis())}


def sub(r: pd.Series, lo, hi) -> dict:
    s = r[(r.index >= lo) & (r.index <= hi)]
    return {"sharpe": ns(s), "ret_pct": float(((1 + s).prod() - 1) * 100),
            "worst_day_pct": float(s.min() * 100) if len(s) else np.nan}


def main() -> None:
    out = {"idea_ids": ["I0064", "I0065"]}

    # ---------- I0064 VIX roll-down carry, slope-gated ----------
    print("=== I0064 VIX roll-down carry (slope-gated short VIXY) ===")
    vix = get_prices("^VIX", start="2011-01-01")["Close"]
    vix3m = get_prices("^VIX3M", start="2011-01-01")["Close"]
    vixy = get_prices("VIXY", start="2011-01-01")["Close"]
    common = vixy.index.intersection(vix.index).intersection(vix3m.index)
    vixy_ret = vixy["Close"].pct_change().reindex(common).fillna(0.0) if isinstance(vixy, pd.DataFrame) else vixy.pct_change().reindex(common).fillna(0.0)
    slope = (vix3m / vix).reindex(common).ffill()  # >1 = contango

    out["I0064"] = {}
    # ungated baseline = always short VIXY (the 0054 outright)
    short = -vixy_ret
    out["I0064"]["ungated"] = stats(short)
    # gated variants over a small slope-threshold grid
    grid = {}
    for thr in (1.00, 1.05, 1.10):
        gate = (slope.shift(1) > thr).astype(float)  # decided yesterday, PIT-safe
        gret = gate * short
        grid[f"thr{thr:.2f}"] = {**stats(gret), "frac_in": float(gate.mean())}
    out["I0064"]["gated"] = grid
    base_thr = 1.05
    gate = (slope.shift(1) > base_thr).astype(float)
    gret = gate * short
    # permutation: does the slope TIMING beat random same-count gating?
    perm = permutation_test(gret, short, gate, n_perm=4000, metric="sharpe")
    out["I0064"]["perm_p_thr1.05"] = perm["p_value"]
    out["I0064"]["stress"] = {
        "ungated_feb2018": sub(short, "2018-02-01", "2018-02-28"),
        "gated_feb2018": sub(gret, "2018-02-01", "2018-02-28"),
        "ungated_mar2020": sub(short, "2020-02-20", "2020-03-31"),
        "gated_mar2020": sub(gret, "2020-02-20", "2020-03-31"),
    }
    u, g = out["I0064"]["ungated"], grid["thr1.05"]
    print(f"  ungated short VIXY : Sharpe {u['sharpe']:+.2f}, MaxDD {u['maxdd_pct']:.0f}%, "
          f"worst-day {u['worst_day_pct']:.1f}%, kurt {u['kurtosis']:.0f}")
    print(f"  gated (VIX3M/VIX>1.05): Sharpe {g['sharpe']:+.2f}, MaxDD {g['maxdd_pct']:.0f}%, "
          f"worst-day {g['worst_day_pct']:.1f}%, kurt {g['kurtosis']:.0f}, in {g['frac_in']:.0%}, perm p={perm['p_value']:.3f}")
    for k, v in out["I0064"]["stress"].items():
        print(f"    {k:18s}: ret {v['ret_pct']:+.1f}%, worst-day {v['worst_day_pct']:.1f}%")

    # ---------- I0065 cross-asset VRP (signal diagnostic) ----------
    print("\n=== I0065 cross-asset VRP (signal — implementation blocker noted) ===")
    classes = {"equity": ("^VIX", "SPY"), "fx": ("^EVZ", "FXE"),
               "gold": ("^GVZ", "GLD"), "oil": ("^OVX", "USO")}
    vrp = {}
    for cls, (ivol_tk, und_tk) in classes.items():
        try:
            iv = get_prices(ivol_tk, start="2011-01-01")["Close"]
            ur = get_prices(und_tk, start="2011-01-01")["Close"].pct_change()
            rv = ur.rolling(21).std() * np.sqrt(252) * 100  # realized vol (annualised %)
            common2 = iv.index.intersection(rv.index)
            vrp[cls] = (iv.reindex(common2) - rv.reindex(common2)).dropna()  # implied - realized
        except Exception as e:  # noqa: BLE001
            print(f"  {cls}: skip ({e})")
    vrp_df = pd.DataFrame(vrp).dropna()
    out["I0065"] = {"mean_vrp": {c: float(vrp_df[c].mean()) for c in vrp_df},
                    "vrp_corr": vrp_df.corr().round(2).to_dict()}
    print("  mean VRP (implied-realized, vol pts):", {c: round(float(vrp_df[c].mean()), 1) for c in vrp_df})
    # does next-month equity short-vol return depend on equity VRP being top-ranked? (tradable only in equity)
    # rank classes each day; when equity VRP is the HIGHEST, is the equity short-vol return better?
    ranks = vrp_df.rank(axis=1, ascending=False)
    eq_top = (ranks["equity"] == 1)
    sv = short.reindex(vrp_df.index).fillna(0.0)
    out["I0065"]["eq_shortvol_when_eq_VRP_top"] = ns(sv[eq_top])
    out["I0065"]["eq_shortvol_when_eq_VRP_not_top"] = ns(sv[~eq_top])
    print(f"  equity short-vol Sharpe when equity-VRP ranked #1: {ns(sv[eq_top]):+.2f} "
          f"vs not-#1: {ns(sv[~eq_top]):+.2f} (frac #1: {eq_top.mean():.0%})")
    print("  -> only equity vol is tradable retail (VIXY/SVXY); bond/FX/comm short-vol needs options.")

    # ---------- plot ----------
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    equ = (1 + short).cumprod(); eqg = (1 + gret).cumprod()
    ax[0].plot(equ.index, equ.values, label="ungated short VIXY", color="firebrick", lw=0.9)
    ax[0].plot(eqg.index, eqg.values, label="slope-gated (>1.05)", color="navy", lw=0.9)
    ax[0].set_yscale("log"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    ax[0].set_title("I0064 short-vol carry: gated vs ungated (log)")
    ax[1].bar(list(vrp_df.columns), [float(vrp_df[c].mean()) for c in vrp_df], color="teal")
    ax[1].set_title("I0065 mean VRP by asset class (vol pts)"); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "vol_carry.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    g05 = grid["thr1.05"]
    improved = (g05["maxdd_pct"] > u["maxdd_pct"] and g05["worst_day_pct"] > u["worst_day_pct"]
                and g05["sharpe"] >= u["sharpe"] - 0.1)
    print("\nVerdict I0064:", "slope-gate cuts tail at comparable Sharpe — useful refinement."
          if improved else "see REPORT — gate trades Sharpe for tail or doesn't help enough.")


if __name__ == "__main__":
    main()
