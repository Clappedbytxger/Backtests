"""Strategy 0038 — Index Gap-Fill Fade (intraday, daily OHLC).

First strategy of the prop-edge research program (Prop-Edge-Framework.md,
hypothesis #2: "Gap-Fill-Fade am Open ohne Übernacht-Halten"). It is the only
priority-1/2 prop hypothesis that can be tested with FULL free history, because
it needs nothing but daily OHLC: the overnight gap is Open_t / Close_{t-1} - 1,
the trade is open->close (flat overnight, zero overnight drawdown — exactly the
profile the prop drawdown rules demand), and free daily OHLC for the S&P 500
(SPY, 1993+) and Nasdaq-100 (QQQ, 1999+) goes back decades with hundreds of
candidate days per year — finally real statistical power.

The intended traded instrument is the Micro E-mini (MES/MNQ); SPY/QQQ are used as
the price proxy because the ETF "Open" is the real RTH auction open that captures
the overnight gap (the futures continuous "Open" is the Globex session open and
is NOT suitable for a gap study — see the ES/NQ note in the report). Costs are
modelled with the conservative MES/MNQ intraday preset (~3 bps round-trip).

Hypothesis: overnight gaps mean-revert intraday; fading the gap at the open is a
high-frequency, smooth-equity, prop-compatible edge.

What this script shows, in order:
  A. Cost gate (framework step 2): does the symmetric fade clear the round-trip
     cost gross? -> No.
  B. Look-ahead demonstration (framework's #1 intraday trap): a conditional
     "buy the dip in an uptrend" rule scores Sharpe ~2.8 — but only because the
     trend filter uses the SAME-DAY close, which is unknown at the open. Lagging
     the filter to information available at the open collapses the edge.
  C. Rigorous evaluation of the only look-ahead-free survivor (down-gap fade in a
     downtrend): permutation, IS/OOS split, fat-tail concentration, prop metrics.
     -> fat-tail lottery, permutation-insignificant -> rejected.

Run:
    .venv/Scripts/python.exe strategies/0038_index_gap_fill_fade/run.py
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

from quantlab.costs import MES_INTRADAY, MNQ_INTRADAY  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import sharpe_ratio  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# Conservative round-trip cost as a return fraction. MES/MNQ intraday preset is
# ~1.5 bps/side; a representative micro contract has ~$25-36k notional, so the
# per-side fraction is dominated by the padded slippage+commission bps.
RT_COST = 2 * (MES_INTRADAY.slippage_bps + MES_INTRADAY.regulatory_bps) / 1e4  # 3 bps
assert abs(RT_COST - 0.0003) < 1e-9
MA_LEN = 50  # trend filter lookback


def load(tkr: str) -> pd.DataFrame:
    """Load daily OHLC and guard against frozen/negative-price feeds (lessons 0005/0025)."""
    df = get_prices(tkr, start="1990-01-01", interval="1d")
    close = df["Close"]
    if (close <= 0).any():
        raise ValueError(f"{tkr}: non-positive close present — unusable.")
    yearly_distinct = close.groupby(close.index.year).nunique()
    if (yearly_distinct <= 3).any():
        raise ValueError(f"{tkr}: frozen-feed years detected — unusable.")
    return df


def features(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Gap, open->close return and a LOOK-AHEAD-SAFE trend flag (known at the open)."""
    o, c = df["Open"], df["Close"]
    prev = c.shift(1)
    ma = c.rolling(MA_LEN).mean()
    return {
        "gap": o / prev - 1.0,                 # decided at the open
        "o2c": c / o - 1.0,                    # the trade's PnL driver (open->close)
        "up_lag": prev > ma.shift(1),          # trend through t-1, valid at open of t
        "up_leak": c > ma,                     # WRONG: uses same-day close (look-ahead)
    }


def fade_returns(o2c: pd.Series, mask: pd.Series, direction: int) -> pd.Series:
    """Full-length daily return series: direction*o2c on selected days, 0 otherwise."""
    pos = pd.Series(0.0, index=o2c.index)
    pos[mask.fillna(False)] = direction
    return (pos * o2c).fillna(0.0), pos


def trade_series(o2c: pd.Series, mask: pd.Series, direction: int) -> pd.Series:
    """Per-trade gross returns (active days only)."""
    return (direction * o2c)[mask.fillna(False)].dropna()


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def main() -> None:
    out: dict = {"cost_rt": RT_COST, "ma_len": MA_LEN, "instruments": {}}

    # ---------------------------------------------------------------- A. cost gate
    section("A. COST GATE — symmetric gap-fill fade (fade every gap, exit at close)")
    print("Fade direction = -sign(gap); per-trade gross vs net at 3 bps round-trip.\n")
    for tkr in ["SPY", "QQQ", "ES=F", "NQ=F"]:
        df = load(tkr)
        f = features(df)
        gap, o2c = f["gap"], f["o2c"]
        beta_o2c = o2c.mean() * 1e4
        row = {"beta_o2c_bps": float(beta_o2c)}
        print(f"{tkr:6} ({df.index[0].date()}..{df.index[-1].date()})  "
              f"unconditional open->close drift = {beta_o2c:5.2f} bps "
              f"(always-long beta, Sharpe {sharpe_ratio(o2c.dropna()):.2f})")
        for thr in [0.0, 0.0025, 0.005]:
            mask = gap.abs() >= thr
            tr = trade_series(o2c, mask, 1) * np.sign(-gap[mask])  # net of sign handled below
            # cleaner: position = -sign(gap)
            pos = -np.sign(gap).where(mask, 0.0)
            trr = (pos * o2c)[mask].dropna()
            g = trr.mean() * 1e4
            net = (trr.mean() - RT_COST) * 1e4
            print(f"    thr={thr*100:4.2f}%  n={int(mask.sum()):5d}  "
                  f"gross/tr={g:6.2f}bps  net/tr={net:6.2f}bps  "
                  f"Sharpe(full)={sharpe_ratio((pos*o2c).fillna(0).dropna()):5.2f}")
            row[f"sym_thr_{thr}"] = {"n": int(mask.sum()), "gross_bps": float(g), "net_bps": float(net)}
        out["instruments"][tkr] = row
    print("\n=> Verdict A: gross edge (~1-2 bps on the ETFs, negative on the futures'\n"
          "   Globex open) never clears the 3 bps round-trip. Cost is the binding\n"
          "   constraint — the BTC 0012-0015 lesson, again.")

    # ----------------------------------------------------- B. look-ahead demonstration
    section("B. LOOK-AHEAD TRAP — 'buy the dip in an uptrend' (the framework's #1 trap)")
    df = load("SPY")
    f = features(df)
    gap, o2c = f["gap"], f["o2c"]
    thr = 0.0025
    dn = gap <= -thr
    leak_ret, _ = fade_returns(o2c, dn & f["up_leak"], +1)   # uses same-day close
    safe_ret, safe_pos = fade_returns(o2c, dn & f["up_lag"], +1)  # lagged, valid at open
    leak_tr = trade_series(o2c, dn & f["up_leak"], +1)
    safe_tr = trade_series(o2c, dn & f["up_lag"], +1)
    print(f"SPY, down-gap (<= -{thr*100:.2f}%) faded long, ONLY in an uptrend:\n")
    print(f"  WITH look-ahead (trend = close_t > MA_t, close_t unknown at open):")
    print(f"     n={len(leak_tr)}  net/tr={(leak_tr.mean()-RT_COST)*1e4:6.2f}bps  "
          f"win={(leak_tr>0).mean()*100:.0f}%  Sharpe(active)={sharpe_ratio(leak_tr):.2f}")
    print(f"  LOOK-AHEAD-SAFE (trend = close_(t-1) > MA_(t-1), known at open):")
    print(f"     n={len(safe_tr)}  net/tr={(safe_tr.mean()-RT_COST)*1e4:6.2f}bps  "
          f"win={(safe_tr>0).mean()*100:.0f}%  Sharpe(active)={sharpe_ratio(safe_tr):.2f}")
    print("\n=> Verdict B: the entire headline edge was look-ahead. `close_t > MA` is\n"
          "   mechanically correlated with a positive open->close (a day that closes\n"
          "   high relative to its average probably rose from the open), so the long\n"
          "   pre-selected up-days. Lagging the filter to open-time information\n"
          "   collapses Sharpe 2.8 -> ~0. Textbook framework Teil 3, step 3.")
    out["lookahead_demo"] = {
        "leak_net_bps": float((leak_tr.mean() - RT_COST) * 1e4),
        "leak_sharpe_active": float(sharpe_ratio(leak_tr)),
        "safe_net_bps": float((safe_tr.mean() - RT_COST) * 1e4),
        "safe_sharpe_active": float(sharpe_ratio(safe_tr)),
    }

    # ------------------------------------ C. rigorous eval of look-ahead-free survivor
    section("C. SURVIVOR — look-ahead-free down-gap fade in a DOWNtrend (long)")
    print("The only cell with positive net after fixing look-ahead. Full battery.\n")
    n_trials = 60  # thresholds x directions x trend conditions x 2 instruments scanned
    survivors = {}
    for tkr, gthr in [("SPY", 0.004), ("QQQ", 0.004)]:
        df = load(tkr)
        f = features(df)
        gap, o2c = f["gap"], f["o2c"]
        mask = (gap <= -gthr) & (~f["up_lag"])
        gross, pos = fade_returns(o2c, mask, +1)
        tr = trade_series(o2c, mask, +1)
        n = len(tr)
        mid = df.index[len(df) // 2]
        is_tr, oos_tr = tr[tr.index < mid], tr[tr.index >= mid]
        tot, top5 = tr.sum(), tr.sort_values(ascending=False).head(5).sum()
        perm = permutation_test(gross.dropna(), o2c.fillna(0.0), pos, n_perm=5000, metric="mean")
        net_series = gross.copy()
        net_series[mask.fillna(False)] -= RT_COST
        boot = bootstrap_ci(net_series.dropna(), statistic="sharpe", n_boot=5000)
        sh_full = sharpe_ratio(net_series.dropna())
        dsr = deflated_sharpe_ratio(sh_full / np.sqrt(252), len(net_series.dropna()),
                                    n_trials=n_trials, returns=net_series.dropna())
        tt = t_test_mean_return(tr - RT_COST)
        print(f"--- {tkr}: down-gap <= -{gthr*100:.2f}% in downtrend, long, exit at close")
        print(f"    n={n}  net/tr={(tr.mean()-RT_COST)*1e4:6.2f}bps  "
              f"median/tr={tr.median()*1e4:6.2f}bps  win={(tr>0).mean()*100:.0f}%")
        print(f"    Sharpe(active)={sharpe_ratio(tr):.2f}  Sharpe(full-time,net)={sh_full:.2f}")
        print(f"    IS net/tr={(is_tr.mean()-RT_COST)*1e4:6.2f}bps  "
              f"OOS net/tr={(oos_tr.mean()-RT_COST)*1e4:6.2f}bps")
        print(f"    top-5 days = {top5/tot*100:.0f}% of total gross profit  (FAT-TAIL CHECK)")
        print(f"    permutation p (mean vs random timing) = {perm['p_value']:.3f}")
        print(f"    bootstrap Sharpe 95% CI = [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]")
        print(f"    Deflated Sharpe (N={n_trials}) = {dsr['psr_deflated']:.2f}   "
              f"t-test p={tt['p_value']:.3f}")
        # worst single day & longest losing streak (prop metrics)
        worst = tr.min() * 100
        signs = (tr > 0).astype(int)
        streak = lose = 0
        for s in signs:
            lose = lose + 1 if s == 0 else 0
            streak = max(streak, lose)
        print(f"    worst trade day = {worst:.2f}%  longest losing streak = {streak} trades")
        survivors[tkr] = {
            "gap_thr": gthr, "n": n,
            "net_per_trade_bps": float((tr.mean() - RT_COST) * 1e4),
            "median_per_trade_bps": float(tr.median() * 1e4),
            "win_rate": float((tr > 0).mean()),
            "sharpe_active": float(sharpe_ratio(tr)),
            "sharpe_full_net": float(sh_full),
            "is_net_bps": float((is_tr.mean() - RT_COST) * 1e4),
            "oos_net_bps": float((oos_tr.mean() - RT_COST) * 1e4),
            "top5_pct_of_profit": float(top5 / tot * 100),
            "perm_p": float(perm["p_value"]),
            "bootstrap_sharpe_ci": [boot["ci_low"], boot["ci_high"]],
            "dsr": float(dsr["psr_deflated"]),
            "t_test_p": float(tt["p_value"]),
            "worst_day_pct": float(worst),
            "longest_losing_streak": int(streak),
        }
        if tkr == "QQQ":
            tr.to_frame("gross_return").assign(net_return=tr - RT_COST).to_csv(
                RESULTS / "trades.csv")
    out["survivor"] = survivors

    # ----------------------------------------------------------------- plots
    # money shot: look-ahead vs look-ahead-free equity (SPY survivor cell)
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    (1 + leak_ret).cumprod().plot(ax=ax[0], color="crimson", label="with look-ahead")
    (1 + safe_ret).cumprod().plot(ax=ax[0], color="steelblue", label="look-ahead-safe")
    ax[0].set_title("Look-ahead vs corrected: 'buy dip in uptrend' (SPY)")
    ax[0].set_ylabel("equity (gross, active days)")
    ax[0].legend(); ax[0].grid(alpha=0.3)
    # o2c mean by gap bucket, split by lagged trend (the real, weak structure)
    df = load("SPY"); f = features(df)
    gap, o2c, up = f["gap"], f["o2c"], f["up_lag"]
    buckets = pd.cut(gap, [-1, -0.01, -0.005, -0.0025, 0, 0.0025, 0.005, 0.01, 1])
    grp_up = (o2c[up].groupby(buckets[up]).mean() * 1e4)
    grp_dn = (o2c[~up].groupby(buckets[~up]).mean() * 1e4)
    x = np.arange(len(grp_up))
    ax[1].bar(x - 0.2, grp_up.values, 0.4, label="uptrend (prev close > MA)", color="seagreen")
    ax[1].bar(x + 0.2, grp_dn.values, 0.4, label="downtrend", color="indianred")
    ax[1].set_xticks(x); ax[1].set_xticklabels([str(i) for i in grp_up.index], rotation=45, fontsize=7)
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_title("Mean open->close (bps) by gap bucket x trend (SPY, look-ahead-safe)")
    ax[1].set_ylabel("mean open->close (bps)")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "gap_fade_analysis.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2))
    section("DONE — results written to results/")
    print("Verdict: REJECTED. Symmetric fade fails the cost gate; the spectacular\n"
          "conditional edge was pure look-ahead; the look-ahead-free survivor is a\n"
          "fat-tail lottery (top-5 days > 100% of profit), permutation-insignificant,\n"
          "IS/OOS-unstable, and economically a falling-knife catch — the worst possible\n"
          "prop profile (violates consistency AND risks the daily DD limit).")


if __name__ == "__main__":
    main()
