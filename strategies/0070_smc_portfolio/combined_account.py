"""0070 — reconcile with the VIDEO's headline (one combined account, +53.89%/yr
net, MaxDD 29.24%, $10k -> $873,928).

The video's number is NOT an equal-weight (1/N) portfolio. It runs all sleeves
simultaneously, each sized at its DD-leveled per-trade risk, COMPOUNDING in ONE
account. We reproduce that by merging every trade from every sleeve onto one
timeline and compounding equity *= (1 + risk_frac * R_net) in exit order.

We show: (1) the 1/N equal-weight (what "gleichgewichtet" literally means), and
(2) the combined account (the video's method). GBPUSD is still excluded (6B
proxy broken) — the video's GBP added ~21% of net profit, so even a perfect
reconstruction lands BELOW the video by that sleeve.
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

MEMBERS = ["XAUUSD", "BTCUSD", "SPX", "NDX", "GBPUSD"]   # GBP now real spot (diversifier)
PPY = 365
TIERS = {
    "taker":     {"XAUUSD": (0.0, 0.75), "BTCUSD": (7.5, 1.0), "SPX": (0.5, 0.5), "NDX": (0.5, 0.5), "GBPUSD": (0.0, 0.5)},
    "good_exec": {"XAUUSD": (0.0, 0.40), "BTCUSD": (5.0, 0.5), "SPX": (0.3, 0.2), "NDX": (0.3, 0.2), "GBPUSD": (0.0, 0.25)},
}


def main() -> None:
    cfg = yaml.safe_load((SMC0069 / "config.yaml").read_text())
    P, assets = cfg["params"], cfg["assets"]

    def overrides(a):
        return dict(n=a.get("n", P["n"]), forward=a.get("forward", P.get("forward")),
                    k=P["k"], buffer_mult=a.get("buffer_mult", P["buffer_mult"]),
                    atr_period=P["atr_period"], max_concurrent=a.get("max_concurrent", 1))

    print("VIDEO (5 Assets inkl. GBP, 1 Konto): +53.89%/J netto, MaxDD 29.24%, $10k->$873,928\n")

    for tier, cmap in TIERS.items():
        per_asset_cagr = {}
        all_trades = []
        ew = {}  # 1/N daily series
        for name in MEMBERS:
            a = assets[name]
            df = run69.filter_session(run69._slice_period(run69.LOADERS[name](),
                 P["test_start"], P["test_end"]), a["session"])
            cb, sb = cmap[name]
            res = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                                   risk_frac=a["risk_frac"], costs=SmcCosts(commission_bps=cb, spread_bps=sb),
                                   **overrides(a))
            tr = res["trades"]
            per_asset_cagr[name] = res["metrics_net"]["cagr"]
            rf = a["risk_frac"]
            for _, t in tr.iterrows():
                all_trades.append((pd.Timestamp(t["exit_time"]).tz_localize(None), rf, t["r_mult_net"]))
            s = res["returns_net"].copy(); s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            ew[name] = s

        # (1) combined ACCOUNT: merge all trades, compound in exit order
        all_trades.sort(key=lambda x: x[0])
        eq = 1.0
        rows = []
        for t, rf, r in all_trades:
            eq *= (1.0 + rf * r)
            rows.append((t, eq))
        ec = pd.Series({t: e for t, e in rows})
        ec = ec.groupby(ec.index.normalize()).last()
        full = pd.date_range(ec.index.min(), ec.index.max(), freq="D")
        ec = ec.reindex(full).ffill().fillna(1.0)
        daily = ec.pct_change().fillna(0.0)
        m = compute_metrics(daily, periods_per_year=PPY)
        years = (ec.index[-1] - ec.index[0]).days / 365.25
        cagr_acct = ec.iloc[-1] ** (1 / years) - 1

        # (2) 1/N equal weight
        Y = pd.DataFrame(ew).sort_index(); f2 = pd.date_range(Y.index.min(), Y.index.max(), freq="D")
        pew = Y.reindex(f2).fillna(0.0).mean(axis=1)
        mew = compute_metrics(pew, periods_per_year=PPY)

        print(f"=== Tier: {tier} (netto, ohne Slippage) ===")
        print(f"  per-Asset Standalone-CAGR: " + ", ".join(f"{k} {v*100:+.1f}%" for k, v in per_asset_cagr.items()))
        print(f"  (1) 1/N EQUAL-WEIGHT     : CAGR {mew['cagr']*100:+.1f}%  TotRet {mew['total_return']*100:+.0f}%  "
              f"MaxDD {mew['max_drawdown']*100:.1f}%")
        print(f"  (2) KOMBI-KONTO (Video)  : CAGR {cagr_acct*100:+.1f}%  TotRet {(ec.iloc[-1]-1)*100:+.0f}%  "
              f"MaxDD {m['max_drawdown']*100:.1f}%  ($10k -> ${ec.iloc[-1]*10000:,.0f})")
        # year by year on the combined account
        yr = (1 + daily).groupby(daily.index.year).prod() - 1
        print("  Jahr-für-Jahr (Kombi-Konto): " + "  ".join(f"{y}:{v*100:+.0f}%" for y, v in yr.items()))
        print()


if __name__ == "__main__":
    main()
