"""0069 — reproduce the video with the CORRECT asymmetric swing pivot.

Prior video reveals the swing definition is asymmetric "(back, forward)" candles
(e.g. 6/2, 8/4, 12/6, 12/4), picked by in-sample optimization. My first build
used a symmetric fractal — the core error. This scans his candidate pivots x
stop buffer against his per-asset targets (1% risk, GROSS, his final config:
long-only indices, fixed-1R GBP, trailing else).

Targets: XAU 2588tr +477% | BTC 223tr +173% | SPX(L) 221tr +82% |
         NDX(L) 307tr +73% | GBP 819tr +131%
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
PIVOTS = [(6, 2), (8, 4), (12, 6), (12, 4)]
BUFFERS = [0.1, 0.5, 1.0]
PLAN = {
    "BTCUSD": ("both", "trailing", "223tr +173%"),
    "SPX":    ("long", "trailing", "221tr +82%"),
    "NDX":    ("long", "trailing", "307tr +73%"),
    "GBPUSD": ("both", "fixed1r",  "819tr +131%"),
    "XAUUSD": ("both", "trailing", "2588tr +477%"),
}


def main() -> None:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    P = cfg["params"]
    for name, (direction, exit_type, target) in PLAN.items():
        a = cfg["assets"][name]
        df = _run.LOADERS[name]()
        df = _run._slice_period(df, P["test_start"], P["test_end"])
        df = _run.filter_session(df, a["session"])
        print(f"=== {name} ({direction}, {exit_type}, 1% risk, GROSS) | VIDEO: {target} ===")
        print(f"  {'pivot':>8} {'buf':>5} {'trades':>7} {'totRet':>9} {'MaxDD':>7} {'avgR':>7} {'win':>4}")
        for back, fwd in PIVOTS:
            for buf in BUFFERS:
                res = run_smc_backtest(
                    df, direction=direction, exit_type=exit_type, risk_frac=0.01,
                    n=back, forward=fwd, k=3, buffer_mult=buf, atr_period=14,
                    require_structure=True, costs=SmcCosts())
                tr = res["trades"]
                if tr.empty:
                    continue
                m = res["metrics_gross"]
                win = (tr["r_mult_gross"] > 0).mean()
                print(f"  {f'{back}/{fwd}':>8} {buf:>5.2f} {len(tr):>7} {m['total_return']*100:>+8.0f}% "
                      f"{m['max_drawdown']*100:>6.1f}% {tr['r_mult_gross'].mean():>+7.3f} {win*100:>3.0f}%")
        print()


if __name__ == "__main__":
    main()
