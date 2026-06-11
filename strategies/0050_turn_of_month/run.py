"""Strategy 0050 — Turn-of-the-Month (Lakonishok & Smidt 1988).

Paper-edge #5 from the prop research list. Claim: the last trading day of the
month plus the first few trading days of the next month earn a disproportionate
share of the equity-index return. Structural, flow-based cause (so it should be
publication-resistant): month-end salary / pension-fund inflows, systematic
index rebalancing and 401(k) contributions concentrate buying pressure at the
turn of the month.

Why this is the right fit for the account: unlike the intraday paper-edge #1
(0049, killed by the 3 bps cost wall), this is ~12 trades/year with a ~4-day
hold capturing tens of bps — so the IBKR cost is far from binding. The user
trades **Interactive Brokers**; the capital-efficient instrument for a small
(~2000 EUR) account on an S&P-500 window is the **Micro E-mini S&P 500 future
(MES)** -> `MES_INTRADAY` cost (3 bps round-trip). We ALSO report net under the
SPY-ETF IBKR cost as a stricter cross-check.

Pre-registration (anti data-mining): the headline window is the canonical
Lakonishok-Smidt definition — last 1 + first 3 trading days — fixed BEFORE
looking at results. A 4x4 window grid is reported only as a *robustness plateau*,
and the Deflated Sharpe is charged the full 16-cell search width.

Data:
  * SPY (1993+, dividend-adjusted) — the tradable instrument, primary net test.
  * ^GSPC (S&P 500 index, 1927+) — long-history power + sub-period stability.

Look-ahead audit: `turn_of_month_signal` is purely calendar-based (trading-day-
of-month), fully known in advance; `run_backtest` additionally applies a T+1
shift. No price information enters the signal.

Run:
    .venv/Scripts/python.exe strategies/0050_turn_of_month/run.py
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

from quantlab.costs import IBKR_LIQUID_ETF, MES_INTRADAY  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.seasonal import add_calendar_features, turn_of_month_signal  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# Pre-registered canonical window (Lakonishok-Smidt): last 1 + first 3 trading days.
BEFORE, AFTER = 1, 3
OOS_START = "2010-01-01"   # IS 1993-2009 / OOS 2010-2026 (SPY)
ANN = np.sqrt(252)


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def run_window(prices: pd.DataFrame, before: int, after: int, cost) -> dict:
    sig = turn_of_month_signal(prices.index, days_before_end=before, days_after_start=after)
    return run_backtest(prices, sig, cost_model=cost)


def main() -> None:
    out: dict = {"window": {"before": BEFORE, "after": AFTER}, "oos_start": OOS_START}

    # ---- load data ----
    spy = get_prices("SPY", start="1993-01-01")
    gspc = get_prices("^GSPC", start="1927-01-01")
    print(f"SPY  {spy.index.min().date()}..{spy.index.max().date()}  ({len(spy)} days)")
    print(f"GSPC {gspc.index.min().date()}..{gspc.index.max().date()}  ({len(gspc)} days)\n")

    # ---- headline backtest on SPY, two IBKR cost models ----
    bt_mes = run_window(spy, BEFORE, AFTER, MES_INTRADAY)     # MES micro future (account fit)
    bt_etf = run_window(spy, BEFORE, AFTER, IBKR_LIQUID_ETF)  # SPY ETF (stricter cross-check)
    pos = bt_mes["position"]
    asset_ret = spy["Close"].pct_change().fillna(0.0)
    gross = bt_mes["gross_returns"]
    net_mes, net_etf = bt_mes["returns"], bt_etf["returns"]

    m_gross = compute_metrics(gross)
    m_mes = compute_metrics(net_mes)
    m_etf = compute_metrics(net_etf)
    ts = trade_stats(bt_mes["trades"])
    bh = compute_metrics(asset_ret)
    days_in = float((pos > 0).mean())

    print(f"=== SPY headline, window last{BEFORE}+first{AFTER} ({days_in*100:.1f}% of days long) ===")
    print(f"{'':14}{'Sharpe':>8}{'CAGR':>9}{'MaxDD':>9}")
    print(f"{'gross':14}{m_gross['sharpe']:8.2f}{m_gross['cagr']*100:8.1f}%{m_gross['max_drawdown']*100:8.1f}%")
    print(f"{'net (MES 3bps)':14}{m_mes['sharpe']:8.2f}{m_mes['cagr']*100:8.1f}%{m_mes['max_drawdown']*100:8.1f}%")
    print(f"{'net (SPY ETF)':14}{m_etf['sharpe']:8.2f}{m_etf['cagr']*100:8.1f}%{m_etf['max_drawdown']*100:8.1f}%")
    print(f"{'buy & hold':14}{bh['sharpe']:8.2f}{bh['cagr']*100:8.1f}%{bh['max_drawdown']*100:8.1f}%")
    print(f"trades: {ts['n_trades']}, win {ts['win_rate']*100:.1f}%, "
          f"expectancy {ts['expectancy']*100:+.2f}%/trade, avg hold {ts['avg_holding_days']:.1f}d")

    out["spy_headline"] = {
        "days_long_frac": days_in, "gross": m_gross, "net_mes": m_mes,
        "net_etf": m_etf, "buy_hold": bh, "trades": ts,
    }

    # ---- diagnostic: TOM days vs rest-of-month days ----
    feats = add_calendar_features(spy.index)
    in_win = ((feats["tdom_from_end"] < BEFORE) | (feats["tdom"] <= AFTER)).values
    tom_ret = asset_ret[in_win]
    rest_ret = asset_ret[~in_win]
    tom_total = (1 + tom_ret).prod() - 1
    rest_total = (1 + rest_ret).prod() - 1
    diag = {
        "tom_day_mean_bps": float(tom_ret.mean() * 1e4),
        "rest_day_mean_bps": float(rest_ret.mean() * 1e4),
        "tom_days": int(in_win.sum()), "rest_days": int((~in_win).sum()),
        "tom_total_return_pct": float(tom_total * 100),
        "rest_total_return_pct": float(rest_total * 100),
        "share_of_gain_on_tom_pct": float(tom_total / (tom_total + rest_total) * 100),
    }
    print(f"\nTOM-day mean {diag['tom_day_mean_bps']:+.2f}bps vs rest {diag['rest_day_mean_bps']:+.2f}bps "
          f"({diag['tom_days']} vs {diag['rest_days']} days)")
    print(f"compounded: TOM days +{diag['tom_total_return_pct']:.0f}% vs rest +{diag['rest_total_return_pct']:.0f}% "
          f"-> {diag['share_of_gain_on_tom_pct']:.0f}% of the index gain sits on {days_in*100:.0f}% of days")
    out["diagnostic"] = diag

    # ---- IS / OOS / recent (net MES) ----
    splits = {
        "IS 1993-2009": net_mes[net_mes.index < OOS_START],
        "OOS 2010-2026": net_mes[net_mes.index >= OOS_START],
        "recent 2015-2026": net_mes[net_mes.index >= "2015-01-01"],
    }
    print("\nIS/OOS (net MES, Sharpe):")
    out["is_oos_net_mes"] = {}
    for name, r in splits.items():
        gr = gross[r.index]
        s = {"net_sharpe": net_sharpe(r), "gross_sharpe": net_sharpe(gr),
             "net_cagr_pct": float(compute_metrics(r)["cagr"] * 100)}
        out["is_oos_net_mes"][name] = s
        print(f"  {name:18}: net {s['net_sharpe']:+.2f}  gross {s['gross_sharpe']:+.2f}  "
              f"CAGR {s['net_cagr_pct']:+.1f}%")

    # ---- significance battery (the drift-trap filter is the key test) ----
    n_trials = 16  # 4x4 window grid scanned below
    perm = permutation_test(gross, asset_ret, pos, n_perm=5000, metric="sharpe")
    boot = bootstrap_ci(net_mes[net_mes != 0.0], statistic="sharpe", n_boot=5000)
    # difference-in-means: are TOM-day returns > non-TOM-day returns?
    tt_diff = t_test_mean_return(pd.Series(tom_ret.values))
    pp_sharpe = float(gross.mean() / gross.std()) if gross.std() else float("nan")
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=len(gross),
                                n_trials=n_trials, returns=gross)
    print(f"\npermutation (gross Sharpe vs random same-count timing, n=5000): p = {perm['p_value']:.4f}")
    print(f"bootstrap net-MES Sharpe 95% CI (active days): [{boot['ci_low']:+.2f}, {boot['ci_high']:+.2f}]")
    print(f"t-test TOM-day mean return > 0: t={tt_diff['t_stat']:+.2f} p={tt_diff['p_value']:.4f}")
    print(f"deflated Sharpe (n_trials={n_trials}): PSR_deflated = {dsr['psr_deflated']:.3f}")
    out["significance"] = {"permutation": perm, "bootstrap_net_mes": boot,
                           "t_test_tom_day": tt_diff, "deflated_sharpe": dsr,
                           "n_trials": n_trials}

    # ---- robustness grid 4x4 (plateau check, NOT selection) ----
    print("\nRobustness grid — net-MES Sharpe by (before x after) trading days:")
    grid = {}
    print("        after=1   2      3      4")
    for b in (1, 2, 3, 4):
        row = []
        for a in (1, 2, 3, 4):
            bt = run_window(spy, b, a, MES_INTRADAY)
            sh = net_sharpe(bt["returns"])
            grid[f"b{b}_a{a}"] = float(sh)
            row.append(sh)
        print(f"before={b}  " + "  ".join(f"{v:+.2f}" for v in row))
    out["robustness_grid_net_mes_sharpe"] = grid

    # ---- long-history cross-check on ^GSPC (1927+), gross + permutation ----
    bt_g = run_window(gspc, BEFORE, AFTER, MES_INTRADAY)
    g_pos, g_gross = bt_g["position"], bt_g["gross_returns"]
    g_asset = gspc["Close"].pct_change().fillna(0.0)
    g_perm = permutation_test(g_gross, g_asset, g_pos, n_perm=5000, metric="sharpe")
    print(f"\n^GSPC 1927-2026 long-history: gross Sharpe {net_sharpe(g_gross):+.2f}, "
          f"permutation p = {g_perm['p_value']:.4f}")
    # per-decade TOM-day mean (does it decay?)
    g_feats = add_calendar_features(gspc.index)
    g_in = ((g_feats["tdom_from_end"] < BEFORE) | (g_feats["tdom"] <= AFTER)).values
    g_tom = g_asset[g_in]
    by_decade = (g_tom.groupby((g_tom.index.year // 10) * 10).mean() * 1e4)
    out["gspc_long"] = {"gross_sharpe": net_sharpe(g_gross), "permutation": g_perm,
                        "tom_day_mean_bps_by_decade": {str(int(k)): float(v) for k, v in by_decade.items()}}
    print("  TOM-day mean (bps) by decade: " +
          "  ".join(f"{int(k)}s={v:+.1f}" for k, v in by_decade.items()))

    # ---- plots ----
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    # (1) equity: TOM net vs B&H (log)
    eq = (1 + net_mes).cumprod()
    ax[0].semilogy(eq.index, eq.values, color="seagreen", label="TOM (net MES)")
    ax[0].semilogy(spy.index, (1 + asset_ret).cumprod().values, color="grey", alpha=0.8, label="SPY B&H")
    ax[0].set_title(f"SPY: turn-of-month net vs buy&hold\n({days_in*100:.0f}% of days invested)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    # (2) mean daily return: TOM vs rest
    ax[1].bar(["TOM days", "rest of month"], [diag["tom_day_mean_bps"], diag["rest_day_mean_bps"]],
              color=["seagreen", "lightgrey"], edgecolor="k")
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_ylabel("mean daily return (bps)")
    ax[1].set_title("The index gain concentrates at the turn\n(rest-of-month ≈ flat)")
    ax[1].grid(alpha=0.3, axis="y")
    # (3) robustness heatmap
    mat = np.array([[grid[f"b{b}_a{a}"] for a in (1, 2, 3, 4)] for b in (1, 2, 3, 4)])
    im = ax[2].imshow(mat, cmap="RdYlGn", vmin=-max(abs(mat.min()), abs(mat.max())),
                      vmax=max(abs(mat.min()), abs(mat.max())))
    ax[2].set_xticks(range(4)); ax[2].set_xticklabels([1, 2, 3, 4]); ax[2].set_xlabel("first N days")
    ax[2].set_yticks(range(4)); ax[2].set_yticklabels([1, 2, 3, 4]); ax[2].set_ylabel("last N days")
    for (i, j), v in np.ndenumerate(mat):
        ax[2].text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8)
    ax[2].add_patch(plt.Rectangle((AFTER - 1 - 0.5, BEFORE - 1 - 0.5), 1, 1, fill=False, edgecolor="blue", lw=2))
    ax[2].set_title("Net-MES Sharpe plateau (blue = pre-registered)")
    fig.colorbar(im, ax=ax[2], fraction=0.046)
    fig.tight_layout()
    fig.savefig(RESULTS / "turn_of_month.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    bt_mes["trades"].to_csv(RESULTS / "trades.csv", index=False)

    # ---- verdict line (data-driven) ----
    passes = (perm["p_value"] < 0.05 and m_mes["sharpe"] > bh["sharpe"]
              and out["is_oos_net_mes"]["OOS 2010-2026"]["net_sharpe"] > 0
              and boot["ci_low"] > 0)
    print("\nVerdict:", "LEAD/testing — survives the battery net of IBKR cost."
          if passes else "see REPORT — battery mixed, judge per criterion.")


if __name__ == "__main__":
    main()
