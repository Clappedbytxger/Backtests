"""0069 reconciliation — sweep the swing/sweep lookback N (spec Teil 2 robustness,
and the video author's hint: "test multiple values for the liquidity sweep
definition look-back").

The video's V1 (same TF/session/exit as our frozen config) reports every asset
GROSS-positive (Gold +344.88%, SPX +20.10%, NDX +42.78%, GBPUSD +115.68% over
10y) with ~3,699 trades total. Our N=2 produced 11,089 trades and a mixed/negative
gross. N=2 fractals on M5 are micro-noise; a larger lookback targets more
significant swing liquidity. This scan measures, per asset and per N (K fixed=3):
gross CAGR / avg-R / trades / win, plus net CAGR with spread+commission only
(no slippage, matching the video's cost method).

Run:  python strategies/0069_smc_sweep_bos/lookback_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("smc_run", Path(__file__).with_name("run.py"))
_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run)

HERE = Path(__file__).resolve().parent
NS = [2, 3, 5, 8, 12, 20, 30, 50]
K = 3


def main() -> None:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    P = cfg["params"]
    for name, a in cfg["assets"].items():
        df = _run.LOADERS[name]()
        if df is None:
            continue
        df = _run._slice_period(df, P["test_start"], P["test_end"])
        df = _run.filter_session(df, a["session"])
        # spread+commission only (no slippage) = the video's cost method
        c = a["costs"]
        cost_nc = SmcCosts(commission_bps=c["commission_bps"], spread_bps=c["spread_bps"],
                           slip_coef=0.0, slip_min_bps=0.0)
        print(f"=== {name} ({a['timeframe']}, {a['direction']}, {a['exit']}, "
              f"session={a['session']}) — Video-Baseline-Return(10J) zum Vergleich ===")
        print(f"  {'N':>3} {'trades':>7} {'grossCAGR':>10} {'grossR':>8} {'win':>5} "
              f"{'grossTotRet':>12} {'netCAGR(sp+co)':>15} {'netR':>8}")
        for n in NS:
            res = run_smc_backtest(
                df, direction=a["direction"], exit_type=a["exit"],
                risk_frac=a["risk_frac"], n=n, k=K,
                buffer_mult=P["buffer_mult"], atr_period=P["atr_period"], costs=cost_nc)
            tr = res["trades"]
            if tr.empty:
                print(f"  {n:>3} {0:>7}  (keine Trades)")
                continue
            g, nm = res["metrics_gross"], res["metrics_net"]
            win = (tr["r_mult_net"] > 0).mean()
            print(f"  {n:>3} {len(tr):>7} {g['cagr']*100:>9.1f}% {tr['r_mult_gross'].mean():>+8.3f} "
                  f"{win*100:>4.0f}% {g['total_return']*100:>+11.0f}% "
                  f"{nm['cagr']*100:>+14.1f}% {tr['r_mult_net'].mean():>+8.3f}")
        print()


if __name__ == "__main__":
    main()
