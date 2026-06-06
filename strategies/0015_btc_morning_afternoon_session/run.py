"""Strategy 0015 — Does the morning's direction predict the afternoon's? (BTC)

Question (pre-registered, ONE hypothesis, not a parameter scan):
    On BTC/USDT, does the sign of the *morning* session return (00:00 -> 14:00
    UTC) carry information about the *afternoon* session return (14:00 -> 24:00
    UTC)? 14 UTC is the US cash-equity / macro open and the intraday volatility
    peak found in 0012.

    Two economic stories, both plausible -> we let the data (in-sample) decide
    which sign, then validate the locked rule out-of-sample:
      * CONTINUATION: Asian/European positioning + order flow built up before the
        US open keeps pushing once US desks pile in (momentum/auto-correlation).
      * REVERSAL: liquidity providers and US mean-reversion flows fade the
        overnight move (the "American reversal").

Design / discipline:
    * Sessions defined by the OPEN price at the boundary hours (price "at" 00:00,
      "at" 14:00, "at" 24:00 = Close of the 23:00 bar). Decision is made at 14:00
      using the morning return M (fully known); the position is held only over the
      afternoon (14:00 -> 24:00). Look-ahead is therefore structurally impossible.
    * IS 2017-08..2022-12 measures the M->A relationship and LOCKS the sign
      (continuation if corr>0, else reversal). n_trials = 2 (the sign choice).
    * OOS 2023-01.. judges only the locked rule, net of Bitget cost.
    * Cost: Bitget perp taker 6bps + 2bps slippage = 8bps/side, one round-trip
      per traded day = 16 bps.
    * Significance: t-test, permutation vs random timing, bootstrap CI, Deflated
      Sharpe. Robustness: magnitude buckets, per-year stability, other split hours
      (descriptive only — 14 UTC stays the pre-registered headline).

Run:
    .venv/Scripts/python.exe strategies/0015_btc_morning_afternoon_session/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.costs import BITGET_PERP_TAKER  # noqa: E402
from quantlab.crypto_data import get_crypto_ohlcv  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
PLOTS = RESULTS / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)

IS_END = "2022-12-31"
OOS_START = "2023-01-01"
DPY = 365
SPLIT_HOUR = 14  # pre-registered
N_TRIALS = 2  # continuation vs reversal — the only free choice


def session_frame(px: pd.DataFrame, split_hour: int = SPLIT_HOUR) -> pd.DataFrame:
    """Per-UTC-day morning/afternoon returns, open-anchored at the boundaries.

    M = Open[split_hour] / Open[00:00] - 1        (morning, fully known at split)
    A = Close[23:00]     / Open[split_hour] - 1   (afternoon, strictly after split)
    Only full days that contain all three reference bars are kept.
    """
    idx = px.index
    o00 = px.loc[idx.hour == 0, "Open"]
    osplit = px.loc[idx.hour == split_hour, "Open"]
    c23 = px.loc[idx.hour == 23, "Close"]
    o00.index = o00.index.normalize()
    osplit.index = osplit.index.normalize()
    c23.index = c23.index.normalize()
    df = pd.DataFrame({"open_00": o00, "open_split": osplit, "close_23": c23}).dropna()
    df["M"] = df["open_split"] / df["open_00"] - 1.0
    df["A"] = df["close_23"] / df["open_split"] - 1.0
    return df


def relationship(df: pd.DataFrame) -> dict:
    """Descriptive M->A relationship: correlation, slope, conditional means."""
    M, A = df["M"].values, df["A"].values
    pear = float(np.corrcoef(M, A)[0, 1])
    spear = float(stats.spearmanr(M, A).statistic)
    beta = float(np.cov(M, A, ddof=1)[0, 1] / np.var(M, ddof=1))
    up, dn = df["M"] > 0, df["M"] < 0
    same = np.sign(df["A"]) == np.sign(df["M"])
    return {
        "pearson": pear, "spearman": spear, "ols_beta": beta,
        "n_days": int(len(df)),
        "up_days": int(up.sum()), "afternoon_mean_given_up": float(df.loc[up, "A"].mean()),
        "afternoon_pos_share_given_up": float((df.loc[up, "A"] > 0).mean()),
        "down_days": int(dn.sum()), "afternoon_mean_given_down": float(df.loc[dn, "A"].mean()),
        "afternoon_pos_share_given_down": float((df.loc[dn, "A"] > 0).mean()),
        "sign_agreement": float(same.mean()),
    }


def strategy_returns(df: pd.DataFrame, direction: int, cost_rt: float) -> pd.DataFrame:
    """Locked rule: position = direction * sign(M), held the afternoon.

    direction = +1 -> continuation, -1 -> reversal. One round-trip per traded day.
    """
    pos = direction * np.sign(df["M"])
    gross = pos * df["A"]
    net = gross - cost_rt * (pos != 0)
    return pd.DataFrame({"position": pos, "gross": gross, "net": net}, index=df.index)


def magnitude_buckets(df: pd.DataFrame, direction: int) -> pd.DataFrame:
    """Afternoon continuation strength by tercile of |morning move|."""
    absM = df["M"].abs()
    q = pd.qcut(absM, 3, labels=["klein", "mittel", "gross"])
    rows = []
    for label in ["klein", "mittel", "gross"]:
        sub = df[q == label]
        pos = direction * np.sign(sub["M"])
        rows.append({
            "bucket": label, "n": int(len(sub)),
            "mean_signed_afternoon": float((pos * sub["A"]).mean()),
            "sign_agreement": float((np.sign(sub["A"]) == np.sign(sub["M"])).mean()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    px = get_crypto_ohlcv("BTC/USDT", timeframe="1h")
    px = px[["Open", "High", "Low", "Close", "Volume"]].astype(float)

    cost_side = BITGET_PERP_TAKER.cost_fraction_per_side(float(px["Close"].mean()))
    cost_rt = 2.0 * cost_side
    print(f"Bitget cost: {cost_rt*1e4:.1f} bps round-trip per traded day.")

    df = session_frame(px)
    is_df = df.loc[:IS_END]
    oos_df = df.loc[OOS_START:]

    # --- IS: measure relationship, LOCK direction ---
    is_rel = relationship(is_df)
    direction = 1 if is_rel["pearson"] >= 0 else -1
    dir_name = "Continuation" if direction == 1 else "Reversal"
    print(f"\n=== IS (..{IS_END}) M->A relationship, {is_rel['n_days']} days ===")
    print(f"  Pearson {is_rel['pearson']:+.4f}  Spearman {is_rel['spearman']:+.4f}"
          f"  OLS beta {is_rel['ols_beta']:+.3f}")
    print(f"  Morning UP   -> afternoon mean {is_rel['afternoon_mean_given_up']:+.4%}"
          f"  ({is_rel['afternoon_pos_share_given_up']:.1%} positive, n={is_rel['up_days']})")
    print(f"  Morning DOWN -> afternoon mean {is_rel['afternoon_mean_given_down']:+.4%}"
          f"  ({is_rel['afternoon_pos_share_given_down']:.1%} positive, n={is_rel['down_days']})")
    print(f"  Sign agreement {is_rel['sign_agreement']:.1%}"
          f"  ->  LOCKED DIRECTION: {dir_name} (pos = {direction:+d} * sign(M))")

    # --- OOS: validate the locked rule ---
    oos_rel = relationship(oos_df)
    sr = strategy_returns(oos_df, direction, cost_rt)
    net, gross, pos = sr["net"], sr["gross"], sr["position"]
    m_net = compute_metrics(net, periods_per_year=DPY)
    m_gross = compute_metrics(gross, periods_per_year=DPY)
    # Benchmarks: always-long the afternoon, and full-day buy & hold.
    bench_aft = compute_metrics(oos_df["A"], periods_per_year=DPY)
    bh_full = compute_metrics(oos_df["close_23"] / oos_df["open_00"] - 1.0, periods_per_year=DPY)

    tt_net = t_test_mean_return(net)
    tt_gross = t_test_mean_return(gross)
    perm = permutation_test(gross, oos_df["A"], pos, n_perm=5000, metric="sharpe")
    boot = bootstrap_ci(net, statistic="sharpe", n_boot=5000)
    pp_sharpe = float(net.mean() / net.std(ddof=1))
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=int(net.shape[0]),
                                n_trials=N_TRIALS, returns=net)

    print(f"\n=== OOS ({OOS_START}..) relationship, {oos_rel['n_days']} days ===")
    print(f"  Pearson {oos_rel['pearson']:+.4f}  Spearman {oos_rel['spearman']:+.4f}"
          f"  Sign agreement {oos_rel['sign_agreement']:.1%}")
    print(f"\n=== OOS locked rule ({dir_name}), net of {cost_rt*1e4:.0f}bps/day ===")
    print(f"  CAGR {m_net['cagr']:+.1%}  Sharpe {m_net['sharpe']:+.2f}  MaxDD {m_net['max_drawdown']:.1%}"
          f"  | gross Sharpe {m_gross['sharpe']:+.2f}")
    print(f"  Benchmark always-long afternoon: Sharpe {bench_aft['sharpe']:+.2f} CAGR {bench_aft['cagr']:+.1%}")
    print(f"  Full-day Buy&Hold: Sharpe {bh_full['sharpe']:+.2f} CAGR {bh_full['cagr']:+.1%}")
    print(f"  t-test mean net ret: t={tt_net['t_stat']:+.2f} p={tt_net['p_value']:.4f}"
          f"  | gross t={tt_gross['t_stat']:+.2f} p={tt_gross['p_value']:.4f}")
    print(f"  Permutation (gross, vs random timing) p={perm['p_value']:.4f}")
    print(f"  Bootstrap net Sharpe 95% CI [{boot['ci_low']:+.2f}; {boot['ci_high']:+.2f}]")
    print(f"  Deflated Sharpe (n_trials={N_TRIALS}): {dsr['psr_deflated']:.3f}")

    # --- Robustness ---
    buckets = magnitude_buckets(oos_df, direction)
    print("\n  OOS magnitude buckets (|morning move|):")
    for _, r in buckets.iterrows():
        print(f"    {r['bucket']:>6}: signed-afternoon mean {r['mean_signed_afternoon']:+.4%}"
              f"  sign-agreement {r['sign_agreement']:.1%}  (n={int(r['n'])})")

    per_year = (oos_df.assign(agree=(np.sign(oos_df["A"]) == np.sign(oos_df["M"])).astype(int),
                              signed=direction * np.sign(oos_df["M"]) * oos_df["A"])
                .groupby(oos_df.index.year)
                .agg(sign_agreement=("agree", "mean"), mean_signed=("signed", "mean"),
                     n=("A", "size")))
    print("\n  OOS per-year stability:")
    for yr, r in per_year.iterrows():
        print(f"    {yr}: sign-agreement {r['sign_agreement']:.1%}  signed-mean {r['mean_signed']:+.4%}  (n={int(r['n'])})")

    split_scan = {}
    for h in [8, 10, 12, 14, 16, 18, 20]:
        d = session_frame(px, h)
        d_is, d_oos = d.loc[:IS_END], d.loc[OOS_START:]
        split_scan[h] = {
            "is_pearson": relationship(d_is)["pearson"],
            "oos_pearson": relationship(d_oos)["pearson"],
            "oos_sign_agreement": relationship(d_oos)["sign_agreement"],
        }
    print("\n  Split-hour scan (descriptive, 14 is the pre-registered headline):")
    for h, v in split_scan.items():
        print(f"    {h:>2}:00  IS r {v['is_pearson']:+.3f}  OOS r {v['oos_pearson']:+.3f}"
              f"  OOS sign-agree {v['oos_sign_agreement']:.1%}")

    # --- Persist ---
    out = {
        "split_hour": SPLIT_HOUR, "locked_direction": dir_name, "direction_int": direction,
        "n_trials": N_TRIALS, "cost_round_trip_bps": cost_rt * 1e4,
        "is_relationship": is_rel, "oos_relationship": oos_rel,
        "oos_net": m_net, "oos_gross": m_gross,
        "benchmark_afternoon_long": bench_aft, "benchmark_buy_hold_full": bh_full,
        "t_test_net": tt_net, "t_test_gross": tt_gross,
        "permutation": perm, "bootstrap_net": boot, "deflated_sharpe": dsr,
        "magnitude_buckets": buckets.to_dict("records"),
        "per_year": per_year.reset_index().rename(columns={"index": "year"}).to_dict("records"),
        "split_hour_scan": split_scan,
    }
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=float))
    df.to_csv(RESULTS / "session_returns.csv")

    # --- Plots ---
    fig, ax = plt.subplots(figsize=(12, 6))
    eq_net = (1.0 + net).cumprod()
    eq_aft = (1.0 + oos_df["A"]).cumprod()
    ax.plot(eq_net.index, eq_net.values, label=f"{dir_name}-Regel (netto)", lw=1.6)
    ax.plot(eq_aft.index, eq_aft.values, label="Immer long Nachmittag", lw=1.1, color="#888")
    ax.axhline(1.0, color="#ccc", lw=0.8)
    ax.set_title(f"0015 Morgen->Nachmittag {dir_name} OOS — Split {SPLIT_HOUR} UTC")
    ax.set_ylabel("Equity (Start=1)")
    ax.legend()
    fig.subplots_adjust(bottom=0.2)
    fig.text(0.5, 0.02,
             f"OOS-Kapitalkurve der gelockten {dir_name}-Regel (Position = Vorzeichen "
             f"der Morgenbewegung) netto nach {cost_rt*1e4:.0f}bps/Tag vs. stures "
             "Long-Halten der Nachmittags-Session.",
             ha="center", fontsize=8.5, style="italic", color="#444")
    fig.savefig(PLOTS / "oos_equity.png", dpi=130)

    fig2, ax2 = plt.subplots(figsize=(7, 6))
    ax2.scatter(is_df["M"] * 100, is_df["A"] * 100, s=6, alpha=0.25, label="IS-Tage")
    xs = np.linspace(is_df["M"].min(), is_df["M"].max(), 50)
    ax2.plot(xs * 100, (is_rel["ols_beta"] * xs) * 100, color="crimson", lw=1.5,
             label=f"OLS beta {is_rel['ols_beta']:+.2f}")
    ax2.axhline(0, color="#ccc", lw=0.8); ax2.axvline(0, color="#ccc", lw=0.8)
    ax2.set_xlabel("Morgen-Return 00->14 UTC (%)")
    ax2.set_ylabel("Nachmittag-Return 14->24 UTC (%)")
    ax2.set_title("Morgen- vs. Nachmittags-Return (In-Sample)")
    ax2.legend()
    fig2.subplots_adjust(bottom=0.16)
    fig2.text(0.5, 0.02, "Jeder Punkt = ein Tag. Eine positive Steigung = Continuation, "
              "negative = Reversal. Flach/Wolke = kein Zusammenhang.",
              ha="center", fontsize=8.5, style="italic", color="#444")
    fig2.savefig(PLOTS / "is_scatter.png", dpi=130)

    print(f"\nSaved artefacts -> {RESULTS}")


if __name__ == "__main__":
    main()
