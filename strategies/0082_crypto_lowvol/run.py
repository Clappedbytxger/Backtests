"""Strategy 0082 — Crypto Low-Vol / BAB cross-section.

Idea I0025 from the `D:\\Backtest Ideas` handoff (#s08 BAB + 0058-0061 crypto infra).
In equities, low-vol/low-beta earns higher risk-adjusted returns. Hypothesis: in
the retail-driven, leverage-hungry crypto market the high-vol "lottery" overcrowding
is even stronger -> long low-vol coins / short high-vol coins has a positive net
hedge-return.

Uses the survivorship-free PIT universe from 0058 (CMC weekly top-150 incl. dead
coins, Binance daily incl. delisted pairs). Critical guards:
  * Liquidity floor: $5M median dollar-volume BEFORE ranking (lesson 0059).
  * **Pegged guard (lesson 0060): require trailing 60d vol >= 10% ann.** — without
    it, near-zero-vol stablecoins dominate the low-vol LONG leg and the test is
    meaningless (the exact trap that bit the live book in 0060).
  * Monthly rebalance, buffered membership via quintiles, inverse-vol weights.

Signal = -realized_vol (low vol -> long). Tested with the cross_sectional engine
(rank L/S + cross-sectional permutation) + long-only-low-vol vs the universe.

Run:
    .venv/Scripts/python.exe strategies/0082_crypto_lowvol/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import quantlab.crypto_xsection as cx  # noqa: E402
from quantlab.cross_sectional import run_cross_sectional, cross_sectional_permutation_test  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import bootstrap_ci  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(365)  # crypto trades 365 days
VOL_LB = 60
LIQ_FLOOR = 5e6
PEG_VOL_FLOOR = 0.10   # annualised; below = treated as pegged/stable -> excluded
OOS_START = "2022-01-01"


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def main() -> None:
    out: dict = {"idea_id": "I0025", "vol_lookback": VOL_LB, "liq_floor": LIQ_FLOOR,
                 "peg_vol_floor": PEG_VOL_FLOOR}

    uni = cx.build_universe(top_n=150)
    panels = cx.get_price_panels(uni)
    close = panels["close"]
    ret = panels["ret"]
    dvol = panels["dollar_volume"]
    member = panels["membership_daily"]
    print(f"universe: {close.shape[1]} pairs, {close.index.min().date()}..{close.index.max().date()}")

    # trailing realised vol (annualised) and median dollar volume
    vol = ret.rolling(VOL_LB).std() * ANN
    dvol_med = dvol.rolling(21).median()

    # eligibility: member that day, liquid, and NOT pegged (vol >= floor)
    eligible = member & (dvol_med >= LIQ_FLOOR) & (vol >= PEG_VOL_FLOOR) & vol.notna()
    n_elig = eligible.sum(axis=1)
    print(f"median eligible names/day: {int(n_elig.median())}")
    out["median_eligible"] = int(n_elig.median())

    # signal = -vol where eligible, else NaN (excluded from ranking)
    signal = (-vol).where(eligible)

    # ---- L/S quintile (low-vol long, high-vol short) ----
    res = run_cross_sectional(close, signal, rebalance="ME", quantile=0.20,
                              long_short=True, cost_bps_per_side=20.0, min_names=10)
    net = res["returns"]
    m_ls = compute_metrics(net)
    perm = cross_sectional_permutation_test(close, signal, n_perm=1000, metric="sharpe",
                                            rebalance="ME", quantile=0.20, long_short=True,
                                            cost_bps_per_side=20.0, min_names=10)
    monthly = (1 + net).resample("ME").prod() - 1
    boot = bootstrap_ci(monthly[monthly != 0], statistic="mean", n_boot=5000)
    print(f"\n=== Low-vol L/S quintile (net, 20bps/side) ===")
    print(f"  Sharpe {m_ls['sharpe']:+.2f}, CAGR {m_ls['cagr']*100:+.1f}%, MaxDD {m_ls['max_drawdown']*100:.0f}%")
    print(f"  perm p={perm['p_value']:.3f}, monthly hedge-return CI [{boot['ci_low']*100:+.2f}%, {boot['ci_high']*100:+.2f}%]")
    out["ls_quintile"] = {"sharpe": m_ls["sharpe"], "cagr_pct": float(m_ls["cagr"]*100),
                          "maxdd_pct": float(m_ls["max_drawdown"]*100), "perm_p": perm["p_value"],
                          "monthly_ci_pct": [boot["ci_low"]*100, boot["ci_high"]*100]}

    # ---- long-only low-vol vs the (eligible) universe ----
    lo = run_cross_sectional(close, signal, rebalance="ME", quantile=0.20,
                             long_short=False, cost_bps_per_side=20.0, min_names=10)
    bench = ret.where(eligible).mean(axis=1)
    out["long_only"] = {"low_vol_sharpe": net_sharpe(lo["returns"]),
                        "eligible_universe_sharpe": net_sharpe(bench)}
    print(f"long-only low-vol Sharpe {net_sharpe(lo['returns']):+.2f} vs eligible-universe {net_sharpe(bench):+.2f}")

    # ---- IS/OOS for the L/S ----
    out["is_oos_ls"] = {nm: net_sharpe(net[msk]) for nm, msk in
                        [("IS 2017-2021", net.index < OOS_START), ("OOS 2022-2026", net.index >= OOS_START)]}
    print(f"L/S IS/OOS Sharpe: IS {out['is_oos_ls']['IS 2017-2021']:+.2f} / OOS {out['is_oos_ls']['OOS 2022-2026']:+.2f}")

    # ---- plot ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].plot((1 + net).cumprod(), color="teal", label="low-vol L/S")
    ax[0].plot((1 + lo["returns"]).cumprod(), color="green", alpha=0.7, label="long-only low-vol")
    ax[0].plot((1 + bench.fillna(0)).cumprod(), color="grey", alpha=0.6, label="eligible universe EW")
    ax[0].set_yscale("log"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    ax[0].set_title("Crypto low-vol: L/S vs long-only vs universe")
    ax[1].plot(n_elig.index, n_elig.values, color="purple")
    ax[1].set_title(f"Eligible names/day (liq>${LIQ_FLOOR/1e6:.0f}M, vol>{PEG_VOL_FLOOR:.0%})")
    ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "crypto_lowvol.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    passes = (perm["p_value"] < 0.05 and boot["ci_low"] > 0 and m_ls["sharpe"] > 0)
    print("\nVerdict:", "LEAD/testing — low-vol hedge-return survives." if passes
          else "see REPORT — low-vol edge weak/insignificant net of cost.")


if __name__ == "__main__":
    main()
