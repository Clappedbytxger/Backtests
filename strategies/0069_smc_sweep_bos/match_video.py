"""0069 — search N x buffer to reproduce the video's per-asset numbers.

Targets (video "Current individual results", 1% risk/trade, GROSS, his final
per-asset config = long-only indices, fixed-1R GBP, trailing else):
    XAUUSD  2588 trades  +477.5%  DD 41.7%
    BTCUSD   223 trades  +173.2%  DD 10.5%
    SPX(L)   221 trades  + 82.0%  DD 14.1%
    NDX(L)   307 trades  + 73.2%  DD 14.1%
    GBPUSD   819 trades  +131.1%  DD 14.4%   (fixed 1R)

We hold risk_frac=0.01 and report GROSS total return + MaxDD so the comparison
is apples-to-apples with the table. Scans the swing lookback and the stop buffer
(the 1R-trailing needs room to ride trends; too tight a stop caps winners).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("smc_run", Path(__file__).with_name("run.py"))
_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run)

HERE = Path(__file__).resolve().parent

# asset -> (direction, exit, N-list, buffer-list, target_str)
PLAN = {
    "BTCUSD": ("both", "trailing", [5, 8, 12], [0.1, 0.5, 1.0, 2.0], "223tr +173% DD10"),
    "SPX":    ("long", "trailing", [3, 5, 8],  [0.1, 0.5, 1.0, 2.0], "221tr +82% DD14"),
    "NDX":    ("long", "trailing", [3, 5, 8],  [0.1, 0.5, 1.0, 2.0], "307tr +73% DD14"),
    "GBPUSD": ("both", "fixed1r",  [4, 6, 8],  [0.1, 0.5, 1.0, 2.0], "819tr +131% DD14"),
    "XAUUSD": ("both", "trailing", [6, 8, 10], [0.1, 0.5, 1.0, 2.0], "2588tr +477% DD42"),
}


def main() -> None:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    P = cfg["params"]
    for name, (direction, exit_type, ns, buffers, target) in PLAN.items():
        a = cfg["assets"][name]
        df = _run.LOADERS[name]()
        df = _run._slice_period(df, P["test_start"], P["test_end"])
        df = _run.filter_session(df, a["session"])
        print(f"=== {name} ({direction}, {exit_type}, 1% risk, GROSS) | VIDEO: {target} ===")
        print(f"  {'N':>3} {'buf':>5} {'trades':>7} {'totRet':>9} {'MaxDD':>7} {'avgR':>7} {'win':>4}")
        for n in ns:
            for buf in buffers:
                res = run_smc_backtest(
                    df, direction=direction, exit_type=exit_type, risk_frac=0.01,
                    n=n, k=3, buffer_mult=buf, atr_period=P["atr_period"],
                    require_structure=True, costs=SmcCosts())  # gross
                tr = res["trades"]
                if tr.empty:
                    continue
                m = res["metrics_gross"]
                win = (tr["r_mult_gross"] > 0).mean()
                print(f"  {n:>3} {buf:>5.2f} {len(tr):>7} {m['total_return']*100:>+8.0f}% "
                      f"{m['max_drawdown']*100:>6.1f}% {tr['r_mult_gross'].mean():>+7.3f} {win*100:>3.0f}%")
        print()


if __name__ == "__main__":
    main()
