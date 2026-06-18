"""I0072 - ICT Judas-Swing / Silver-Bullet killzone reversal.

Mechanically a variant of 0069 (SMC sweep->BOS): a fake move at the session open
(killzone) sweeps liquidity beyond a prior extreme, then reverses. We reuse the
audited causal SMC engine (quantlab.smc) and restrict the input to killzone bars
only. The handoff flags high discretion/overfit risk -> the codifiable part is the
sweep->BOS->retest with an asymmetric pivot (0069 lesson), permutation-tested.

Killzones (UTC): London 07:00-10:00, NY 12:00-15:00. Tested on ES, NQ, GC at 5-min.
Cost: CFD spread folded into SmcCosts.spread_bps (index 3 bps RT / gold 4 bps RT).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.smc import run_smc_backtest, SmcCosts


def resample_5m(df: pd.DataFrame) -> pd.DataFrame:
    o = df["Open"].resample("5min").first()
    h = df["High"].resample("5min").max()
    l = df["Low"].resample("5min").min()
    c = df["Close"].resample("5min").last()
    v = df["Volume"].resample("5min").sum()
    out = pd.concat([o, h, l, c, v], axis=1)
    out.columns = ["Open", "High", "Low", "Close", "Volume"]
    return out.dropna()


def killzone(df_utc: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    t = df_utc.index.time
    m = (t >= pd.Timestamp(start).time()) & (t < pd.Timestamp(end).time())
    return df_utc[m]


def run(symbol: str, kz_start: str, kz_end: str, spread_bps_rt: float, label: str):
    df = resample_5m(C.load(symbol))
    kz = killzone(df, kz_start, kz_end)
    costs = SmcCosts(commission_bps=0.0, spread_bps=spread_bps_rt / 2.0,
                     slip_coef=0.0, slip_min_bps=0.0)
    # asymmetric pivot like 0069 (8 back, 4 forward); both directions
    res = run_smc_backtest(kz, direction="both", exit_type="trailing",
                           n=8, forward=4, k=3, buffer_mult=0.3,
                           require_structure=True, costs=costs,
                           periods_per_year=252)
    tr = res["trades"]
    if len(tr) == 0:
        print(f"  {label}: 0 trades"); return None
    mg = res["metrics_gross"]; mn = res["metrics_net"]
    avg_r_g = tr["r_mult_gross"].mean()
    avg_r_n = tr["r_mult_net"].mean()
    win = (tr["r_mult_net"] > 0).mean()
    print(f"  {label:22s}: trades {len(tr):4d}  avgR gross {avg_r_g:+.3f} net {avg_r_n:+.3f}  "
          f"win {win:.3f}  grossSharpe {mg.get('sharpe', float('nan')):6.3f}  "
          f"netSharpe {mn.get('sharpe', float('nan')):6.3f}")
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    print("=== I0072 ICT Judas/Silver-Bullet killzone sweep->BOS (5-min) ===")
    for sym, sp in [("ES", 3.0), ("NQ", 3.0), ("GC", 4.0)]:
        run(sym, "07:00", "10:00", sp, f"{sym} London KZ")
        run(sym, "12:00", "15:00", sp, f"{sym} NY KZ")
