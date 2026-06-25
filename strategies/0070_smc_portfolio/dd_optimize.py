"""0070 — diagnose the high portfolio drawdown and optimize it toward the video
(combined 29% DD) / a funded account (City Traders Imperium ~6-10% max DD).

Why is my combined DD 52% vs the video's 29%? Two suspects:
  (a) SPX + NDX are both LONG-ONLY US indices -> highly correlated -> their
      drawdowns coincide (no diversification);
  (b) pyramiding (max_concurrent>1) boosts return but worsens Ret/DD.

We measure the cross-sleeve correlation and test optimizations on the 1/N
equal-weight portfolio (the construction relevant for a funded account, where DD
is the binding constraint):
  - mc=1 (no pyramiding) vs config mc
  - merge the redundant indices (half-weight SPX & NDX, or drop NDX)
  - re-level each sleeve to ~20% standalone DD (the video's method, on MY DDs)
Risk scaling is linear, so we run each sleeve once per mc and scale analytically.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402

SMC0069 = ROOT / "strategies" / "0069_smc_sweep_bos"
_r = importlib.util.spec_from_file_location("smc_run", SMC0069 / "run.py")
run69 = importlib.util.module_from_spec(_r); _r.loader.exec_module(run69)

MEMBERS = ["XAUUSD", "BTCUSD", "SPX", "NDX", "GBPUSD"]
PPY = 365
COSTS = {"XAUUSD": (0.0, 0.40), "BTCUSD": (5.0, 0.5), "SPX": (0.3, 0.2),
         "NDX": (0.3, 0.2), "GBPUSD": (0.0, 0.25)}  # good_exec


def daily_net(name, a, P, mc):
    df = run69.filter_session(run69._slice_period(run69.LOADERS[name](),
         P["test_start"], P["test_end"]), a["session"])
    cb, sb = COSTS[name]
    res = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                           risk_frac=a["risk_frac"], n=a.get("n", P["n"]),
                           forward=a.get("forward", P.get("forward")), k=P["k"],
                           buffer_mult=a.get("buffer_mult", P["buffer_mult"]),
                           atr_period=P["atr_period"], max_concurrent=mc,
                           costs=SmcCosts(commission_bps=cb, spread_bps=sb))
    s = res["returns_net"].copy(); s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    return s, res["metrics_net"]["max_drawdown"], a["risk_frac"]


def port_metrics(weighted_series: dict) -> dict:
    X = pd.DataFrame(weighted_series).sort_index()
    full = pd.date_range(X.index.min(), X.index.max(), freq="D")
    p = X.reindex(full).fillna(0.0).sum(axis=1)
    m = compute_metrics(p, periods_per_year=PPY)
    m["ret_dd"] = m["total_return"] / abs(m["max_drawdown"]) if m["max_drawdown"] else float("nan")
    return m


def main() -> None:
    cfg = yaml.safe_load((SMC0069 / "config.yaml").read_text())
    P, assets = cfg["params"], cfg["assets"]

    # run each sleeve at config-mc and mc=1
    ser_cfg, ser_mc1, dd_cfg = {}, {}, {}
    for name in MEMBERS:
        a = assets[name]
        ser_cfg[name], dd_cfg[name], _ = daily_net(name, a, P, a.get("max_concurrent", 1))
        ser_mc1[name], _, _ = daily_net(name, a, P, 1)

    # align all on a common calendar
    X = pd.DataFrame(ser_cfg).sort_index()
    full = pd.date_range(X.index.min(), X.index.max(), freq="D")
    X = X.reindex(full).fillna(0.0)

    print("== Cross-Sleeve-Korrelation der Tages-Returns (config mc) ==")
    corr = X.corr()
    print(corr.round(2).to_string())
    print(f"\n  SPX-NDX Korrelation: {corr.loc['SPX','NDX']:.2f}  (Redundanz-Check)")
    print(f"  Standalone-MaxDD je Sleeve (config mc): " +
          ", ".join(f"{k} {abs(v)*100:.0f}%" for k, v in dd_cfg.items()) + "\n")

    def eqw(ser, weights):
        return {k: ser[k] * w for k, w in weights.items()}

    n = len(MEMBERS)
    base_w = {k: 1.0 / n for k in MEMBERS}
    variants = {
        "A 1/N, config mc (Ist)":      (ser_cfg, base_w),
        "B 1/N, mc=1 (kein Pyramid)":  (ser_mc1, base_w),
        "C mc=1, NDX raus (SPX bleibt)": (ser_mc1, {k: (0 if k == "NDX" else 1/4) for k in MEMBERS}),
        "D mc=1, SPX+NDX halbgewicht": (ser_mc1, {"XAUUSD":0.25,"BTCUSD":0.25,"SPX":0.125,"NDX":0.125,"GBPUSD":0.25}),
    }
    # E: mc=1 + re-level each sleeve to 20% standalone DD, then equal-weight
    dd_mc1 = {}
    for name in MEMBERS:
        dd_mc1[name] = abs(compute_metrics(ser_mc1[name], periods_per_year=PPY)["max_drawdown"])
    relevel = {k: (0.20 / dd_mc1[k]) / n if dd_mc1[k] > 0 else 0 for k in MEMBERS}
    variants["E mc=1, re-level 20% + 1/N"] = (ser_mc1, relevel)

    print("== 1/N-Portfolio-Varianten (netto good_exec) ==")
    print(f"  {'Variante':32} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7} {'Ret/DD':>7}")
    results = {}
    for label, (ser, w) in variants.items():
        m = port_metrics(eqw(ser, w))
        results[label] = m
        print(f"  {label:32} {m['cagr']*100:>+6.1f}% {m['sharpe']:>7.2f} "
              f"{m['max_drawdown']*100:>6.1f}% {m['ret_dd']:>7.2f}")
    print("  (Video Kombi-Ret/DD = 295; mein Ist-Kombi = 173. Höheres Ret/DD = besser fürs Funded-Konto.)\n")

    # funded sizing: take the best Ret/DD variant, size so MaxDD hits CTI limits
    best = max(results, key=lambda k: results[k]["ret_dd"])
    bm = results[best]
    print(f"== Funded-Sizing (beste Variante: {best}) ==")
    for limit, lab in [(0.06, "CTI Instant 6%"), (0.10, "CTI Challenge ~10%")]:
        scale = limit / abs(bm["max_drawdown"])
        cagr = bm["cagr"] * scale  # linear down-size (approx)
        print(f"  {lab:20}: Risiko ×{scale:.2f} -> MaxDD {limit*100:.0f}%, erwartete CAGR ~{cagr*100:+.1f}%/J "
              f"(Profit-Ziel {limit*100*0.8:.0f}-10% -> {'erreichbar' if cagr>0.10 else 'eng/mehrere Monate'})")


if __name__ == "__main__":
    main()
