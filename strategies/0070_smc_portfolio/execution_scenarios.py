"""0070 — execution-cost scenarios: how much does better order execution (IBKR
relative/adaptive/pegged-to-midpoint, limit/maker) move the net portfolio vs B&H?

Three tiers (per side bps -> RT = 2x), NO slippage:
  taker     : cross the spread both sides (current "netto")
  good_exec : adaptive/relative saves ~half the spread on liquid legs; BTC maker
              entry + taker exit
  limit_max : optimistic upper bound — limit/maker both sides, captures the spread
              (IGNORES non-fills / adverse selection — see caveat)

CAVEAT printed in the output: V1 enters at the BOS-close (a momentum breakout), so
passive limits suffer adverse selection (you miss the runners, you catch the
reversers — exactly why the video's retracement entry V2 was worse). The exit is a
trailing STOP (market when hit) and pays the spread regardless. So the realistic
result sits between `taker` and `good_exec`; `limit_max` is an unreachable bound.
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

MEMBERS = ["XAUUSD", "BTCUSD", "SPX", "NDX"]
PPY = 365
# per-asset (commission_bps, spread_bps) per side for each tier
TIERS = {
    "taker (aktuell)": {"XAUUSD": (0.0, 0.75), "BTCUSD": (7.5, 1.0), "SPX": (0.5, 0.5), "NDX": (0.5, 0.5)},
    "good_exec":       {"XAUUSD": (0.0, 0.40), "BTCUSD": (5.0, 0.5), "SPX": (0.3, 0.2), "NDX": (0.3, 0.2)},
    "limit_max (bound)": {"XAUUSD": (0.0, 0.20), "BTCUSD": (4.0, 0.0), "SPX": (0.2, 0.0), "NDX": (0.2, 0.0)},
}


def main() -> None:
    cfg = yaml.safe_load((SMC0069 / "config.yaml").read_text())
    P, assets = cfg["params"], cfg["assets"]

    def overrides(a):
        return dict(n=a.get("n", P["n"]), forward=a.get("forward", P.get("forward")),
                    k=P["k"], buffer_mult=a.get("buffer_mult", P["buffer_mult"]),
                    atr_period=P["atr_period"], max_concurrent=a.get("max_concurrent", 1))

    # B&H equal-weight benchmark
    bh = {}
    for name in MEMBERS:
        df = run69._slice_period(run69.LOADERS[name](), P["test_start"], P["test_end"])
        c = df["Close"].copy(); c.index = pd.DatetimeIndex(c.index).tz_convert("UTC").tz_localize(None)
        bh[name] = c.resample("1D").last().dropna().pct_change().fillna(0.0)
    X = pd.DataFrame(bh).sort_index(); full = pd.date_range(X.index.min(), X.index.max(), freq="D")
    pbh = X.reindex(full).fillna(0.0).mean(axis=1)
    mbh = compute_metrics(pbh, periods_per_year=PPY)

    print("Portfolio (¼ Gold/BTC/SPX/NDX) netto je Ausführungs-Tier vs Buy & Hold")
    print(f"  {'Tier':20} {'Return':>9} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7} {'Ret/DD':>7} {'schlägt B&H?':>13}")
    for tier, costs_map in [("GROSS (0 Kosten)", None)] + list(TIERS.items()):
        ser = {}
        for name in MEMBERS:
            a = assets[name]
            df = run69.filter_session(run69._slice_period(run69.LOADERS[name](),
                 P["test_start"], P["test_end"]), a["session"])
            if costs_map is None:
                cost = SmcCosts()
            else:
                cb, sb = costs_map[name]
                cost = SmcCosts(commission_bps=cb, spread_bps=sb)
            res = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                                   risk_frac=a["risk_frac"], costs=cost, **overrides(a))
            s = res["returns_net"].copy(); s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            ser[name] = s
        Y = pd.DataFrame(ser).sort_index(); f2 = pd.date_range(Y.index.min(), Y.index.max(), freq="D")
        port = Y.reindex(f2).fillna(0.0).mean(axis=1)
        m = compute_metrics(port, periods_per_year=PPY)
        rod = m["total_return"] / abs(m["max_drawdown"])
        verdict = "JA" if m["sharpe"] > mbh["sharpe"] else "nein"
        print(f"  {tier:20} {m['total_return']*100:>+8.0f}% {m['cagr']*100:>+6.1f}% {m['sharpe']:>7.2f} "
              f"{m['max_drawdown']*100:>6.1f}% {rod:>7.2f} {verdict:>13}")
    print(f"\n  Buy & Hold (¼):      {mbh['total_return']*100:>+8.0f}% {mbh['cagr']*100:>+6.1f}% "
          f"{mbh['sharpe']:>7.2f} {mbh['max_drawdown']*100:>6.1f}% "
          f"{mbh['total_return']/abs(mbh['max_drawdown']):>7.2f}")
    print("\n  CAVEAT: V1 = Breakout-Entry am BOS-Close. Passive Limits -> adverse Selektion")
    print("  (Runner laufen weg, Reversals fuellen). Exit = Trailing-STOP (Market) zahlt Spread.")
    print("  Realistisch zwischen taker und good_exec; limit_max ignoriert Non-Fills = obere Schranke.")


if __name__ == "__main__":
    main()
