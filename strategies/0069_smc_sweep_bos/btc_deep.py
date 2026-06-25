"""0069 — deep-dive on the one real lead: BTC both-direction SMC sweep+BOS.

The full-sample permutation gave p=0.053 (real Sharpe +0.31 vs random-timing null
-0.14) on a BOTH-direction asset, where long-beta is not the explanation. This
script stress-tests that:
  1. Robustness grid (pivot x buffer): plateau (real) or single spike (overfit)?
  2. True OOS split: pick on 2017-2021, FROZEN test on 2022-2026 — does the edge
     survive, or is it just the 2017-21 crypto-trend regime?
  3. Year-by-year net-R: is the edge spread or concentrated in the bull years?
  4. Cost sensitivity incl. a FUNDING proxy (both-direction needs a perp; funding
     every 8h is a real holding cost the spot-based video ignores).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402
from quantlab.significance import permutation_test, bootstrap_ci  # noqa: E402
from quantlab.metrics import sharpe_ratio  # noqa: E402

import importlib.util  # noqa: E402
_a = importlib.util.spec_from_file_location("an", Path(__file__).with_name("analyze.py"))
an = importlib.util.module_from_spec(_a); _a.loader.exec_module(an)

HERE = Path(__file__).resolve().parent
PIVOTS = [(6, 2), (8, 2), (8, 4), (10, 4), (12, 4), (12, 6)]
BUFFERS = [0.5, 1.0, 1.5, 2.0]


def load_btc(P):
    a = {"session": "none"}
    df = an._run.LOADERS["BTCUSD"]()
    df = an._run._slice_period(df, P["test_start"], P["test_end"])
    return df


def run(df, b, f, buf, cost, fund_bps_per_day=0.0):
    res = run_smc_backtest(df, direction="both", exit_type="trailing", risk_frac=0.01,
                           n=b, forward=f, k=3, buffer_mult=buf, atr_period=14,
                           require_structure=True, costs=cost)
    tr = res["trades"]
    if fund_bps_per_day and not tr.empty:
        # funding proxy: charge fund_bps_per_day * holding_days in R units, where
        # 1R move = r_price; cost fraction = fund * notional; in R = fund*(price/r).
        # approx with entry price; holding_days = bars / bars_per_day.
        bpd = 24  # H1
        hold_days = tr["holding_days"] / bpd
        fund_R = (fund_bps_per_day / 1e4) * hold_days * (tr["entry"] / tr["r_price"])
        tr = tr.copy()
        tr["r_mult_net"] = tr["r_mult_net"] - fund_R
        tr["pnl_frac_net"] = 0.01 * tr["r_mult_net"]
    return res, tr


def main() -> None:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    P = cfg["params"]
    cc = cfg["assets"]["BTCUSD"]["costs"]
    cost = SmcCosts(commission_bps=cc["commission_bps"], spread_bps=cc["spread_bps"])  # spread+comm
    df = load_btc(P)
    aret = an.asset_daily_returns("BTCUSD", df.index, P)

    print("== 1) Robustness grid (both, trailing, net spread+comm, 1% risk) ==")
    print(f"  {'pivot':>6} {'buf':>4} {'trd':>4} {'grossRet':>9} {'netAvgR':>8} {'perm_p':>7} {'win':>4}")
    cells = []
    for b, f in PIVOTS:
        for buf in BUFFERS:
            res, tr = run(df, b, f, buf, cost)
            if tr.empty:
                continue
            net = res["returns_net"]
            pos = an.daily_position(tr, df.index)
            com = net.index.intersection(pos.index).intersection(aret.index)
            perm = permutation_test(net.reindex(com).fillna(0), aret.reindex(com).fillna(0),
                                    pos.reindex(com).fillna(0), n_perm=1000)
            avgR = tr["r_mult_net"].mean()
            cells.append((b, f, buf, len(tr), res["metrics_gross"]["total_return"], avgR, perm["p_value"]))
            print(f"  {f'{b}/{f}':>6} {buf:>4.1f} {len(tr):>4} "
                  f"{res['metrics_gross']['total_return']*100:>+8.0f}% {avgR:>+8.3f} "
                  f"{perm['p_value']:>7.3f} {(tr['r_mult_net']>0).mean()*100:>3.0f}%")
    pos_cells = sum(1 for c in cells if c[5] > 0)
    print(f"  -> {pos_cells}/{len(cells)} Zellen netto-Ø-R > 0 (Plateau-Check); n_trials={len(cells)}\n")

    # choose the config used in the headline (8/4, buf=1.0)
    b, f, buf = 8, 4, 1.0
    print(f"== 2) True OOS split @ {b}/{f} buf={buf} ==")
    for lab, lo, hi in [("IS 2017-2021", "2016-01-01", "2021-12-31"),
                        ("OOS 2022-2026", "2022-01-01", "2026-05-31")]:
        sub = df[(df.index >= pd.Timestamp(lo, tz="UTC")) & (df.index <= pd.Timestamp(hi, tz="UTC"))]
        res, tr = run(sub, b, f, buf, cost)
        net = res["returns_net"]
        ar = an.asset_daily_returns("BTCUSD", sub.index, P)
        pos = an.daily_position(tr, sub.index)
        com = net.index.intersection(pos.index).intersection(ar.index)
        perm = permutation_test(net.reindex(com).fillna(0), ar.reindex(com).fillna(0),
                                pos.reindex(com).fillna(0), n_perm=2000)
        boot = bootstrap_ci(tr["r_mult_net"].reset_index(drop=True), statistic="mean", n_boot=2000)
        print(f"  {lab}: trades={len(tr)} grossRet={res['metrics_gross']['total_return']*100:+.0f}% "
              f"netAvgR={tr['r_mult_net'].mean():+.3f} netSharpe={res['metrics_net']['sharpe']:.2f} "
              f"perm_p={perm['p_value']:.3f} (null {perm['null_mean']:.2f} vs {perm['observed']:.2f}) "
              f"bootKI[{boot['ci_low']:+.3f},{boot['ci_high']:+.3f}]")
    print()

    print(f"== 3) Year-by-year net-R sum @ {b}/{f} buf={buf} ==")
    res, tr = run(df, b, f, buf, cost)
    tr2 = tr.copy(); tr2["yr"] = pd.DatetimeIndex(tr2["exit_time"]).year
    yr = tr2.groupby("yr").agg(n=("r_mult_net", "size"), sumR=("r_mult_net", "sum"),
                               avgR=("r_mult_net", "mean"))
    for y, row in yr.iterrows():
        print(f"  {y}: n={int(row['n']):3d}  sumR={row['sumR']:+6.1f}  avgR={row['avgR']:+.3f}")
    print()

    print(f"== 4) Cost sensitivity incl. funding proxy @ {b}/{f} buf={buf} ==")
    for lab, factor, fund in [("gross", 0.0, 0.0), ("spread+comm 1x", 1.0, 0.0),
                              ("+funding 1bp/d", 1.0, 1.0), ("+funding 3bp/d", 1.0, 3.0),
                              ("2x cost +funding 3bp/d", 2.0, 3.0)]:
        res, tr = run(df, b, f, buf, cost.scaled(factor), fund_bps_per_day=fund)
        print(f"  {lab:24}: netAvgR={tr['r_mult_net'].mean():+.3f}  "
              f"sumR={tr['r_mult_net'].sum():+.1f}  win={(tr['r_mult_net']>0).mean()*100:.0f}%")


if __name__ == "__main__":
    main()
