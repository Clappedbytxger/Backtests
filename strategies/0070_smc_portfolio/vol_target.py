"""0070 — "keep the return, cut the drawdown" via portfolio volatility targeting.

The combined account (all sleeves full risk) is +54%/yr but 52% DD; that DD is
pure leverage, not poor diversification (correlations ~0). To lower DD WITHOUT
cutting the return-engine (vs. crudely de-levering / mc=1), scale total exposure
inversely to trailing realized vol: cut risk in turbulent regimes, hold it in
calm ones. We report Calmar (CAGR/MaxDD) — the leverage-invariant efficiency the
video beats us on (his +54%/29% = Calmar 1.86 vs my un-targeted ~1.0).

Also answers the funded-account math: at CTI's 10% STATIC max DD (+ 5% daily),
what CAGR is reachable, and is +54% even possible (no — 54% CAGR needs >10% DD).
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


def metr(daily: pd.Series) -> dict:
    m = compute_metrics(daily, periods_per_year=PPY)
    m["calmar"] = m["cagr"] / abs(m["max_drawdown"]) if m["max_drawdown"] else float("nan")
    m["worst_day"] = float(daily.min())
    return m


def main() -> None:
    cfg = yaml.safe_load((SMC0069 / "config.yaml").read_text())
    P, assets = cfg["params"], cfg["assets"]

    ser = {}
    for name in MEMBERS:
        a = assets[name]
        df = run69.filter_session(run69._slice_period(run69.LOADERS[name](),
             P["test_start"], P["test_end"]), a["session"])
        cb, sb = COSTS[name]
        res = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                               risk_frac=a["risk_frac"], n=a.get("n", P["n"]),
                               forward=a.get("forward", P.get("forward")), k=P["k"],
                               buffer_mult=a.get("buffer_mult", P["buffer_mult"]),
                               atr_period=P["atr_period"], max_concurrent=a.get("max_concurrent", 1),
                               costs=SmcCosts(commission_bps=cb, spread_bps=sb))
        s = res["returns_net"].copy(); s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
        ser[name] = s

    X = pd.DataFrame(ser).sort_index()
    full = pd.date_range(X.index.min(), X.index.max(), freq="D")
    X = X.reindex(full).fillna(0.0)
    combined = X.sum(axis=1)               # all sleeves full risk = the +54% account

    base = metr(combined)
    print(f"VIDEO: CAGR +53.89%  MaxDD 29.24%  Calmar 1.86  (das Effizienz-Ziel)")
    print(f"{'Variante':34} {'CAGR':>8} {'MaxDD':>8} {'Calmar':>7} {'worstDay':>9}")
    print(f"{'Kombi-Konto (Ist, kein Vol-Target)':34} {base['cagr']*100:>+7.0f}% "
          f"{base['max_drawdown']*100:>7.1f}% {base['calmar']:>7.2f} {base['worst_day']*100:>8.1f}%")

    # vol targeting: scale exposure to a constant target vol using trailing 30d vol
    def vol_target(daily, target_ann, window=30, max_lev=3.0):
        tv = daily.rolling(window).std() * np.sqrt(PPY)
        lev = (target_ann / tv).shift(1).clip(0, max_lev).fillna(0.0)
        return lev * daily

    results = {}
    for tv in [0.15, 0.20, 0.25, 0.30, 0.40]:
        d = vol_target(combined, tv)
        m = metr(d); results[tv] = (m, d)
        print(f"{'Vol-Target ' + str(int(tv*100)) + '% p.a.':34} {m['cagr']*100:>+7.0f}% "
              f"{m['max_drawdown']*100:>7.1f}% {m['calmar']:>7.2f} {m['worst_day']*100:>8.1f}%")

    # best Calmar vol-target, sized to CTI 10% static DD; check 5% daily
    best_tv = max(results, key=lambda k: results[k][0]["calmar"])
    bm, bd = results[best_tv]
    scale = 0.10 / abs(bm["max_drawdown"])
    sized = bd * scale
    ms = metr(sized)
    print(f"\n== Funded-Sizing: bestes Vol-Target ({int(best_tv*100)}% p.a.) auf CTI 10% statischen DD ==")
    print(f"  Risiko ×{scale:.2f} -> CAGR {ms['cagr']*100:+.1f}%/J, MaxDD {ms['max_drawdown']*100:.1f}%, "
          f"worst day {ms['worst_day']*100:.1f}% (CTI Tageslimit 5% -> {'ok' if abs(ms['worst_day'])<0.05 else 'BREACH'})")
    print(f"  -> 10% Profit-Ziel in ~{0.10/ms['cagr']*12:.0f} Monaten erreichbar (kein Zeitlimit bei CTI).")
    # what leverage would +54% CAGR need, and what DD does that imply?
    s54 = bd * (0.5389 / bm["cagr"])
    m54 = metr(s54)
    print(f"\n== Gegenrechnung: +53.89% CAGR auf der vol-getargeten Reihe erzwingen ==")
    print(f"  braucht Risiko ×{0.5389/bm['cagr']:.2f} -> MaxDD {m54['max_drawdown']*100:.0f}%, "
          f"worst day {m54['worst_day']*100:.0f}% -> auf CTI (10% DD / 5% Tag) UNMÖGLICH.")


if __name__ == "__main__":
    main()
