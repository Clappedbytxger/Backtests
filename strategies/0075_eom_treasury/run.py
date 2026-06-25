"""Strategy 0075 — End-of-Month Treasury Returns (Hartley & Schwarz).

Idea I0010 from the new `D:\\Backtest Ideas` handoff (source #s03/#s18). Claim
(Hartley/Schwarz, "Predictable End-of-Month Treasury Returns"): Treasury excess
returns are abnormally high in the LAST 1-2 trading days of the month, strongest
on the very last day, with the effect growing with maturity (2y barely, 10y
~20 bps/month / Sharpe ~1, 30y two-day position ~4.5% p.a.). Structural,
flow-based cause (publication-resistant): bond-index duration extension at
month-end (Bloomberg Agg rebalances on the last calendar day) plus window
dressing — index trackers and life insurers are FORCED to buy duration at the
turn, a predictable demand shock.

This is the bond analogue of the confirmed equity edge 0050 (turn-of-the-month):
~24 trades/year, 1-2 day hold capturing tens of bps — so the IBKR cost is far
from binding (unlike the intraday cost-wall rejects 0049/0051).

Pre-registration (anti data-mining): the headline window is the canonical
Hartley/Schwarz 2-day position — be long the LAST trading day + the FIRST
trading day of the next month — fixed BEFORE looking at results. Because the
engine shifts the decision-time signal by one bar, the decision days are the
last two trading days of the month (``turn_of_month_signal(before=2, after=0)``),
which the engine holds over {last day, first day of next month}. A 4x4 window
grid is reported only as a robustness plateau; the Deflated Sharpe is charged
the full 16-cell search width.

The KEY test is the drift-trap permutation (lesson 0016/0017/0050): Treasuries
had a 40-year bull market AND a 2022 crash, so being long duration on random
days is itself a (regime-dependent) bet. The permutation shuffles the held days
to random same-count timing — it asks whether the month-END TIMING carries, not
merely being long duration.

Placebo (structural confirmation): the paper predicts NO effect at the short end
(2y). We run the same window on SHY (1-3y) — it should be ~flat while IEF/TLT
fire. A generic "any month-end" artifact would light up SHY too.

Data (all free, dividend-adjusted = total return ~ the paper's excess return):
  * IEF  — iShares 7-10y Treasury (2002+), the ~10y headline instrument.
  * TLT  — iShares 20+y Treasury (2002+), long end (paper: stronger).
  * SHY  — iShares 1-3y Treasury (2002+), short-end placebo (paper: ~null).
  * ZN=F — 10y T-Note continuous future, longer-history cross-check ONLY, with
           an explicit roll-artifact caveat (lesson 0028/0029: continuous
           futures roll quarterly near month-end → flagged, not headline).

Run:
    .venv/Scripts/python.exe strategies/0075_eom_treasury/run.py
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

from quantlab.costs import IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.seasonal import turn_of_month_signal  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# Pre-registered canonical window (Hartley/Schwarz 2-day EOM position):
# decisions on the last 2 trading days -> engine holds {last day, first day next}.
BEFORE, AFTER = 2, 0
OOS_START = "2014-01-01"   # IS 2002-2013 / OOS 2014-2026 (OOS contains the 2022 crash)
ANN = np.sqrt(252)


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def run_window(prices: pd.DataFrame, before: int, after: int, cost=IBKR_LIQUID_ETF) -> dict:
    sig = turn_of_month_signal(prices.index, days_before_end=before, days_after_start=after)
    return run_backtest(prices, sig, cost_model=cost)


def held_diagnostic(prices: pd.DataFrame, before: int, after: int) -> dict:
    """Mean return on the actually-HELD EOM days vs the rest of the month.

    Consistent with what the strategy earns: we read the engine's shifted
    ``position`` (the held mask), not the raw signal.
    """
    bt = run_window(prices, before, after)
    pos = bt["position"]
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    held = pos > 0
    eom_ret = asset_ret[held]
    rest_ret = asset_ret[~held]
    eom_total = (1 + eom_ret).prod() - 1
    rest_total = (1 + rest_ret).prod() - 1
    denom = eom_total + rest_total
    return {
        "eom_day_mean_bps": float(eom_ret.mean() * 1e4),
        "rest_day_mean_bps": float(rest_ret.mean() * 1e4),
        "eom_days": int(held.sum()),
        "rest_days": int((~held).sum()),
        "eom_total_return_pct": float(eom_total * 100),
        "rest_total_return_pct": float(rest_total * 100),
        "share_of_gain_on_eom_pct": float(eom_total / denom * 100) if denom else float("nan"),
        "held_frac": float(held.mean()),
        "eom_returns": eom_ret,
    }


def cross_market(prices: pd.DataFrame, label: str) -> dict:
    bt = run_window(prices, BEFORE, AFTER)
    gross, pos = bt["gross_returns"], bt["position"]
    net = bt["returns"]
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    perm = permutation_test(gross, asset_ret, pos, n_perm=5000, metric="sharpe")
    diag = held_diagnostic(prices, BEFORE, AFTER)
    boot = bootstrap_ci(diag["eom_returns"], statistic="mean", n_boot=5000)
    return {
        "label": label,
        "span": f"{prices.index.min().date()}..{prices.index.max().date()}",
        "net_sharpe": net_sharpe(net),
        "gross_sharpe": net_sharpe(gross),
        "bh_sharpe": net_sharpe(asset_ret),
        "eom_day_mean_bps": diag["eom_day_mean_bps"],
        "rest_day_mean_bps": diag["rest_day_mean_bps"],
        "permutation_p": perm["p_value"],
        "boot_eom_mean_bps_ci": [boot["ci_low"] * 1e4, boot["ci_high"] * 1e4],
        "n_eom_days": diag["eom_days"],
    }


def main() -> None:
    out: dict = {"idea_id": "I0010", "window": {"before": BEFORE, "after": AFTER},
                 "oos_start": OOS_START}

    # ---- load data ----
    ief = get_prices("IEF", start="2002-01-01")
    tlt = get_prices("TLT", start="2002-01-01")
    shy = get_prices("SHY", start="2002-01-01")
    print(f"IEF {ief.index.min().date()}..{ief.index.max().date()} ({len(ief)} days)")
    print(f"TLT {tlt.index.min().date()}..{tlt.index.max().date()} ({len(tlt)} days)")
    print(f"SHY {shy.index.min().date()}..{shy.index.max().date()} ({len(shy)} days)\n")

    # ---- headline backtest on IEF (10y), IBKR ETF cost ----
    bt = run_window(ief, BEFORE, AFTER)
    pos = bt["position"]
    asset_ret = ief["Close"].pct_change().fillna(0.0)
    gross, net = bt["gross_returns"], bt["returns"]

    m_gross = compute_metrics(gross)
    m_net = compute_metrics(net)
    ts = trade_stats(bt["trades"])
    bh = compute_metrics(asset_ret)
    days_in = float((pos > 0).mean())

    print(f"=== IEF (10y) headline, hold last{BEFORE}->first ({days_in*100:.1f}% of days long) ===")
    print(f"{'':16}{'Sharpe':>8}{'CAGR':>9}{'MaxDD':>9}")
    print(f"{'gross':16}{m_gross['sharpe']:8.2f}{m_gross['cagr']*100:8.1f}%{m_gross['max_drawdown']*100:8.1f}%")
    print(f"{'net (ETF 2bps)':16}{m_net['sharpe']:8.2f}{m_net['cagr']*100:8.1f}%{m_net['max_drawdown']*100:8.1f}%")
    print(f"{'buy & hold':16}{bh['sharpe']:8.2f}{bh['cagr']*100:8.1f}%{bh['max_drawdown']*100:8.1f}%")
    print(f"trades: {ts['n_trades']}, win {ts['win_rate']*100:.1f}%, "
          f"expectancy {ts['expectancy']*100:+.3f}%/trade, avg hold {ts['avg_holding_days']:.1f}d")

    out["ief_headline"] = {"days_long_frac": days_in, "gross": m_gross, "net": m_net,
                           "buy_hold": bh, "trades": ts}

    # ---- diagnostic: held EOM days vs rest ----
    diag = held_diagnostic(ief, BEFORE, AFTER)
    print(f"\nEOM-held mean {diag['eom_day_mean_bps']:+.2f}bps vs rest {diag['rest_day_mean_bps']:+.2f}bps "
          f"({diag['eom_days']} vs {diag['rest_days']} days)")
    print(f"compounded: EOM days +{diag['eom_total_return_pct']:.0f}% vs rest +{diag['rest_total_return_pct']:.0f}% "
          f"-> {diag['share_of_gain_on_eom_pct']:.0f}% of the gain on {days_in*100:.0f}% of days")
    out["diagnostic"] = {k: v for k, v in diag.items() if k != "eom_returns"}

    # ---- IS / OOS / recent (net) ----
    splits = {
        "IS 2002-2013": net[net.index < OOS_START],
        "OOS 2014-2026": net[net.index >= OOS_START],
        "recent 2018-2026": net[net.index >= "2018-01-01"],
        "2022 crash year": net[(net.index >= "2022-01-01") & (net.index < "2023-01-01")],
    }
    print("\nIS/OOS (net, Sharpe):")
    out["is_oos_net"] = {}
    for name, r in splits.items():
        s = {"net_sharpe": net_sharpe(r), "gross_sharpe": net_sharpe(gross[r.index]),
             "net_cagr_pct": float(compute_metrics(r)["cagr"] * 100)}
        out["is_oos_net"][name] = s
        print(f"  {name:18}: net {s['net_sharpe']:+.2f}  gross {s['gross_sharpe']:+.2f}  "
              f"CAGR {s['net_cagr_pct']:+.1f}%")

    # ---- significance battery (drift-trap permutation is the key test) ----
    n_trials = 16  # 4x4 window grid scanned below
    perm = permutation_test(gross, asset_ret, pos, n_perm=5000, metric="sharpe")
    boot = bootstrap_ci(net[net != 0.0], statistic="sharpe", n_boot=5000)
    tt = t_test_mean_return(pd.Series(diag["eom_returns"].values))
    pp_sharpe = float(gross.mean() / gross.std()) if gross.std() else float("nan")
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=len(gross),
                                n_trials=n_trials, returns=gross)
    print(f"\npermutation (gross Sharpe vs random same-count timing, n=5000): p = {perm['p_value']:.4f}")
    print(f"bootstrap net Sharpe 95% CI (active days): [{boot['ci_low']:+.2f}, {boot['ci_high']:+.2f}]")
    print(f"t-test EOM-day mean return > 0: t={tt['t_stat']:+.2f} p={tt['p_value']:.4f}")
    print(f"deflated Sharpe (n_trials={n_trials}): PSR_deflated = {dsr['psr_deflated']:.3f}")
    out["significance"] = {"permutation": perm, "bootstrap_net": boot,
                           "t_test_eom_day": tt, "deflated_sharpe": dsr, "n_trials": n_trials}

    # ---- robustness grid: before 1-4 x after 0-3 (plateau, NOT selection) ----
    print("\nRobustness grid — net Sharpe by (before last-N x after first-M):")
    grid = {}
    print("            after=0    1      2      3")
    for b in (1, 2, 3, 4):
        row = []
        for a in (0, 1, 2, 3):
            sh = net_sharpe(run_window(ief, b, a)["returns"])
            grid[f"b{b}_a{a}"] = float(sh)
            row.append(sh)
        print(f"before={b}    " + "  ".join(f"{v:+.2f}" for v in row))
    out["robustness_grid_net_sharpe"] = grid

    # ---- cross-market: TLT (long, stronger), SHY (short, placebo) ----
    print("\nCross-market (same window, permutation = drift-trap filter):")
    cm = {"IEF_10y": cross_market(ief, "IEF (10y)"),
          "TLT_long": cross_market(tlt, "TLT (20y+)"),
          "SHY_short_placebo": cross_market(shy, "SHY (1-3y placebo)")}
    for k, c in cm.items():
        print(f"  {c['label']:22}: EOM {c['eom_day_mean_bps']:+.2f}bps vs rest {c['rest_day_mean_bps']:+.2f}bps, "
              f"perm p={c['permutation_p']:.4f}, EOM-mean CI [{c['boot_eom_mean_bps_ci'][0]:+.2f},{c['boot_eom_mean_bps_ci'][1]:+.2f}]bps")
    out["cross_market"] = cm

    # ---- longer-history cross-check on ZN=F (with roll caveat) ----
    try:
        zn = get_prices("ZN=F", start="2000-01-01")
        if (zn["Close"] <= 0).any():
            raise ValueError("non-positive future price")
        c_zn = cross_market(zn, "ZN=F (10y future)")
        zn_feats_ret = zn["Close"].pct_change().fillna(0.0)
        by_dec = (zn_feats_ret[run_window(zn, BEFORE, AFTER)["position"] > 0]
                  .groupby(lambda d: (d.year // 5) * 5).mean() * 1e4)
        c_zn["eom_mean_bps_by_5y"] = {str(int(k)): float(v) for k, v in by_dec.items()}
        out["zn_future_crosscheck"] = c_zn
        print(f"\nZN=F (2000+, ROLL-CAVEAT): EOM {c_zn['eom_day_mean_bps']:+.2f}bps, perm p={c_zn['permutation_p']:.4f}")
        print("  EOM-mean (bps) by 5y: " + "  ".join(f"{k}={v:+.1f}" for k, v in c_zn["eom_mean_bps_by_5y"].items()))
    except Exception as e:  # noqa: BLE001
        out["zn_future_crosscheck"] = {"error": str(e)}
        print(f"\nZN=F cross-check skipped: {e}")

    # ---- plots ----
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    eq = (1 + net).cumprod()
    ax[0].plot(eq.index, eq.values, color="navy", label="EOM (net)")
    ax[0].plot(ief.index, (1 + asset_ret).cumprod().values, color="grey", alpha=0.8, label="IEF B&H")
    ax[0].set_title(f"IEF (10y): EOM-Treasury net vs buy&hold\n({days_in*100:.0f}% of days invested)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    labels = ["IEF\n(10y)", "TLT\n(20y+)", "SHY\n(1-3y)"]
    eom_bars = [cm["IEF_10y"]["eom_day_mean_bps"], cm["TLT_long"]["eom_day_mean_bps"], cm["SHY_short_placebo"]["eom_day_mean_bps"]]
    rest_bars = [cm["IEF_10y"]["rest_day_mean_bps"], cm["TLT_long"]["rest_day_mean_bps"], cm["SHY_short_placebo"]["rest_day_mean_bps"]]
    x = np.arange(3)
    ax[1].bar(x - 0.2, eom_bars, 0.4, color="navy", label="EOM-held days")
    ax[1].bar(x + 0.2, rest_bars, 0.4, color="lightgrey", label="rest of month")
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_xticks(x); ax[1].set_xticklabels(labels)
    ax[1].set_ylabel("mean daily return (bps)")
    ax[1].set_title("Effect grows with maturity; SHY placebo ~flat")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3, axis="y")
    mat = np.array([[grid[f"b{b}_a{a}"] for a in (0, 1, 2, 3)] for b in (1, 2, 3, 4)])
    vmax = max(abs(mat.min()), abs(mat.max()))
    im = ax[2].imshow(mat, cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax[2].set_xticks(range(4)); ax[2].set_xticklabels([0, 1, 2, 3]); ax[2].set_xlabel("after first-M days")
    ax[2].set_yticks(range(4)); ax[2].set_yticklabels([1, 2, 3, 4]); ax[2].set_ylabel("before last-N days")
    for (i, j), v in np.ndenumerate(mat):
        ax[2].text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8)
    ax[2].add_patch(plt.Rectangle((AFTER - 0.5, BEFORE - 1 - 0.5), 1, 1, fill=False, edgecolor="blue", lw=2))
    ax[2].set_title("Net Sharpe plateau (blue = pre-registered)")
    fig.colorbar(im, ax=ax[2], fraction=0.046)
    fig.tight_layout()
    fig.savefig(RESULTS / "eom_treasury.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    bt["trades"].to_csv(RESULTS / "trades.csv", index=False)

    # ---- verdict line (data-driven) ----
    ief_c, shy_c = cm["IEF_10y"], cm["SHY_short_placebo"]
    passes = (perm["p_value"] < 0.05
              and ief_c["boot_eom_mean_bps_ci"][0] > 0
              and out["is_oos_net"]["OOS 2014-2026"]["net_sharpe"] > 0
              and shy_c["permutation_p"] > 0.05)  # placebo should be null
    print("\nVerdict:", "LEAD/testing — EOM timing survives the drift-trap permutation; placebo null."
          if passes else "see REPORT — battery mixed, judge per criterion.")


if __name__ == "__main__":
    main()
