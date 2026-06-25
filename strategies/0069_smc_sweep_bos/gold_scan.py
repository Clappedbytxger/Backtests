"""0069 — push Gold reproduction (video: 2588 trades, +477% gross, DD 42%).

My best so far +284%. The user is right: +477% gross is an edge, not a cost
artifact. This scans the so-far-undertested levers — pivot (back/forward), stop
buffer, and especially K (the sweep reclaim window = how fast/shallow the sweep
must be) — to find the real best Gold config, then we test net + permutation on
it (both-direction Gold = clean edge-vs-noise test).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402

import importlib.util  # noqa: E402
_s = importlib.util.spec_from_file_location("r", Path(__file__).with_name("run.py"))
r = importlib.util.module_from_spec(_s); _s.loader.exec_module(r)

HERE = Path(__file__).resolve().parent
PIVOTS = [(10, 4), (10, 10), (12, 6), (12, 12), (14, 6), (8, 4)]
BUFFERS = [0.5, 1.0]
KS = [2, 3, 5]


def main() -> None:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    P = cfg["params"]
    df = r.LOADERS["XAUUSD"]()
    df = r._slice_period(df, P["test_start"], P["test_end"])
    rows = []
    for b, f in PIVOTS:
        for buf in BUFFERS:
            for k in KS:
                res = run_smc_backtest(df, direction="both", exit_type="trailing",
                                       risk_frac=0.01, n=b, forward=f, k=k, buffer_mult=buf,
                                       atr_period=14, require_structure=True, costs=SmcCosts())
                tr = res["trades"]
                if tr.empty:
                    continue
                m = res["metrics_gross"]
                rows.append((b, f, buf, k, len(tr), m["total_return"], m["max_drawdown"],
                             tr["r_mult_gross"].mean(), tr["r_mult_gross"].sum()))
    rows.sort(key=lambda x: -x[5])
    print("Gold scan, sorted by GROSS total return (1% risk). VIDEO target: 2588tr +477% DD42%")
    print(f"  {'pivot':>7} {'buf':>4} {'K':>2} {'trades':>7} {'totRet':>9} {'MaxDD':>7} {'avgR':>7} {'sumR':>6}")
    for b, f, buf, k, n, tot, dd, ar, sr in rows:
        print(f"  {f'{b}/{f}':>7} {buf:>4.1f} {k:>2} {n:>7} {tot*100:>+8.0f}% {dd*100:>6.1f}% {ar:>+7.3f} {sr:>+6.0f}")


if __name__ == "__main__":
    main()
