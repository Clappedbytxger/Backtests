"""Strategy 0074 — Stan Weinstein Stage-2 breakout (daily adaptation).

Faithful build of the user's spec (Weinstein, *Secrets for Profiting in Bull and
Bear Markets*), traded on individual US stocks, daily chart:

  Entry: a stock breaks above its 30-day MA out of a Stage-1 trading range whose
  resistance was tested >= 3 times, on volume above its trailing average, with
  Mansfield relative strength crossing from negative to positive.

  Exits tested: MA-stop (the book's canonical sell), 1R trailing, chandelier ATR
  trailing, and partial-profit-plus-trail. Pyramiding (adding to winners) on/off.
  Multiple positions held simultaneously (shared-equity portfolio engine).

Two structural caveats, handled head-on (not buried):

* **Survivorship bias.** yfinance only serves *today's* survivors, which inflates
  any long breakout strategy. So the verdict does NOT rest on the headline CAGR.
  The decisive controls are (a) equal-weight Buy & Hold of the SAME universe and
  (b) a random-timing permutation that keeps the universe + trade count but
  shuffles WHEN we enter. Both isolate genuine Stage-2 *timing* skill from beta
  and survivorship — the lab's hard-won "is it just long-the-survivors?" test.
* **30-day vs 30-week.** Weinstein's canonical MA is 30 *weekly*; the user asked
  for 30 *daily*. We build exactly the daily version and say so.

Run:  .venv/Scripts/python.exe strategies/0074_weinstein_stage2/run.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402

from quantlab.data import get_prices, get_close     # noqa: E402
from quantlab.metrics import compute_metrics, sharpe_ratio, trade_stats  # noqa: E402
from quantlab.significance import (                 # noqa: E402
    bootstrap_ci, deflated_sharpe_ratio, t_test_mean_return,
)
from quantlab.weinstein import (                    # noqa: E402
    EntryParams, PortfolioConfig, detect_stage2_entries,
    build_orders, build_random_orders, prepare_data, run_portfolio,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

START = "2000-01-01"
OOS_START = pd.Timestamp("2015-01-01")   # IS <= 2014, OOS 2015-2026
BENCH = "SPY"

# ~110 liquid US large/mid caps across sectors. SURVIVORSHIP-BIASED on membership
# (today's survivors) — see module docstring; the controls below neutralize it.
UNIVERSE = [
    # mega / tech
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "ADBE", "CRM",
    "ORCL", "CSCO", "INTC", "AMD", "QCOM", "TXN", "IBM", "AVGO", "MU", "AMAT",
    "NOW", "INTU", "ADI", "LRCX", "KLAC",
    # financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "AXP", "BLK", "SCHW",
    "SPGI", "CB", "MMC", "AIG", "MET", "TRV",
    # health care
    "JNJ", "UNH", "PFE", "MRK", "ABT", "TMO", "DHR", "BMY", "AMGN", "GILD",
    "MDT", "CVS", "ELV", "ISRG", "SYK", "BDX",
    # consumer
    "PG", "KO", "PEP", "WMT", "COST", "HD", "LOW", "MCD", "NKE", "SBUX", "TGT",
    "MDLZ", "CL", "MO", "PM", "EL", "YUM", "DG",
    # industrials / materials / energy
    "CAT", "DE", "HON", "GE", "MMM", "BA", "UPS", "UNP", "RTX", "LMT", "GD",
    "EMR", "ITW", "ETN", "PH", "XOM", "CVX", "COP", "SLB", "EOG", "PSX",
    "LIN", "APD", "SHW", "NEM", "FCX",
    # comms / utilities / re
    "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS", "NEE", "DUK", "SO", "D",
    "AMT", "PLD", "SPG",
]


def load_universe() -> tuple[dict, pd.Series, list]:
    """Download (cached) OHLCV for the universe + benchmark, with a data-quality
    screen (the 0025 lesson: drop frozen / too-short feeds before backtesting)."""
    bench = get_close(BENCH, start=START)
    data, dropped = {}, []
    for tk in UNIVERSE:
        try:
            df = get_prices(tk, start=START)
        except Exception as exc:  # noqa: BLE001
            dropped.append((tk, f"load error: {exc}")); continue
        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if len(df) < 750:
            dropped.append((tk, f"too short ({len(df)})")); continue
        ret = df["Close"].pct_change()
        zero_frac = float((ret.abs() < 1e-9).mean())
        distinct_per_yr = df["Close"].groupby(df.index.year).nunique().median()
        if zero_frac > 0.4 or distinct_per_yr < 60:
            dropped.append((tk, f"frozen (zero={zero_frac:.2f}, distinct/yr={distinct_per_yr:.0f})"))
            continue
        data[tk] = df
    return data, bench, dropped


def build_signal_frames(data: dict, bench: pd.Series, params: EntryParams) -> dict:
    """Attach the Stage-2 detection columns to each ticker's OHLCV frame."""
    frames = {}
    for tk, df in data.items():
        det = detect_stage2_entries(df, bench, params)
        frames[tk] = df.join(det)
    return frames


def split_metrics(ret: pd.Series, label: str) -> dict:
    """compute_metrics on the full / IS / OOS slices of a daily return series."""
    is_r = ret[ret.index < OOS_START]
    oos_r = ret[ret.index >= OOS_START]
    return {
        "label": label,
        "full": compute_metrics(ret),
        "is": compute_metrics(is_r),
        "oos": compute_metrics(oos_r),
    }


def equal_weight_bh(data: dict, calendar: pd.DatetimeIndex) -> pd.Series:
    """Daily-rebalanced equal-weight Buy & Hold of the SAME universe (the
    survivorship-matched benchmark: holding all these survivors equally)."""
    closes = pd.DataFrame({tk: df["Close"] for tk, df in data.items()})
    closes = closes.reindex(calendar).ffill(limit=5)
    rets = closes.pct_change()
    return rets.mean(axis=1, skipna=True).fillna(0.0)


def block_bootstrap_sharpe(ret: pd.Series, block: int = 20, n_boot: int = 3000,
                           seed: int = 42) -> tuple[float, float]:
    """Block-bootstrap 95% CI for the annualized Sharpe (preserves the
    autocorrelation from concurrent trades riding the same trend)."""
    r = ret.to_numpy()
    m = len(r)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(m / block))
    out = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, max(m - block, 1), nb)
        samp = np.concatenate([r[s:s + block] for s in starts])[:m]
        out[i] = sharpe_ratio(pd.Series(samp))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def random_timing_permutation(frames: dict, real_orders: dict, cfg: PortfolioConfig,
                              prepared, slice_from=None, n_perm: int = 300,
                              seed: int = 42) -> dict:
    """Null = same #entries per ticker at RANDOM bars, same exit logic. p = share
    of random books whose Sharpe >= the real strategy's (over the same slice)."""
    counts = {tk: len(v) for tk, v in real_orders.items()}
    real = run_portfolio(frames, real_orders, cfg, prepared=prepared)["returns"]
    if slice_from is not None:
        real = real[real.index >= slice_from]
    observed = sharpe_ratio(real)
    rng = np.random.default_rng(seed)
    null = np.empty(n_perm)
    for i in range(n_perm):
        ro = build_random_orders(frames, counts, rng)
        rr = run_portfolio(frames, ro, cfg, prepared=prepared)["returns"]
        if slice_from is not None:
            rr = rr[rr.index >= slice_from]
        null[i] = sharpe_ratio(rr)
    p = float((np.sum(null >= observed) + 1) / (n_perm + 1))
    return {"observed": float(observed), "p_value": p,
            "null_mean": float(np.nanmean(null)), "null_std": float(np.nanstd(null)),
            "n_perm": n_perm}


# ── exit/pyramiding variants scanned (n_trials for the Deflated Sharpe) ──────
VARIANTS = [
    ("ma",          dict(exit_mode="ma")),
    ("trail1r",     dict(exit_mode="trail1r")),
    ("chandelier",  dict(exit_mode="chandelier")),
    ("partial",     dict(exit_mode="partial")),
    ("ma+pyramid",         dict(exit_mode="ma", pyramid=True, max_adds=2)),
    ("trail1r+pyramid",    dict(exit_mode="trail1r", pyramid=True, max_adds=2)),
    ("chandelier+pyramid", dict(exit_mode="chandelier", pyramid=True, max_adds=2)),
    ("partial+pyramid",    dict(exit_mode="partial", pyramid=True, max_adds=2)),
]
CANONICAL = "ma"   # Weinstein's pre-registered sell rule = the headline config


def fmt(m: dict) -> str:
    rod = m["total_return"] / abs(m["max_drawdown"]) if m["max_drawdown"] else float("nan")
    return (f"CAGR {m['cagr']*100:+6.1f}%  Sharpe {m['sharpe']:5.2f}  "
            f"MaxDD {m['max_drawdown']*100:6.1f}%  Ret/DD {rod:5.2f}")


def main() -> None:
    print("=" * 92)
    print("0074 — Weinstein Stage-2 Breakout (daily 30-day MA), individual US stocks")
    print("=" * 92)

    data, bench, dropped = load_universe()
    print(f"Universe loaded: {len(data)}/{len(UNIVERSE)} tickers "
          f"(dropped {len(dropped)}: {[d[0] for d in dropped]})")

    params = EntryParams()
    frames = build_signal_frames(data, bench, params)
    n_signals = sum(int(f["signal"].sum()) for f in frames.values())
    print(f"Stage-2 signals across universe: {n_signals}  "
          f"(EntryParams: MA{params.ma_period}, base{params.base_window}, "
          f"touches>={params.min_touches}, vol>{params.vol_mult}x, stop={params.stop_mode})")

    prepared = prepare_data(frames)
    calendar = prepared[1]
    base_cfg = PortfolioConfig()
    real_orders = build_orders(frames)

    # ---- 1) variant scan (full / IS / OOS) ----
    print("\n--- Exit-/Pyramiding-Varianten (netto IBKR-Kosten) ---")
    print(f"{'Variante':<20} {'IS Sharpe':>9} {'OOS Sharpe':>10} {'OOS CAGR':>9} "
          f"{'OOS MaxDD':>9} {'Trades':>7} {'Win%':>6}")
    variant_out = {}
    trial_sharpes = []
    for name, kw in VARIANTS:
        cfg = PortfolioConfig(**kw)
        res = run_portfolio(frames, real_orders, cfg, prepared=prepared)
        sm = split_metrics(res["returns"], name)
        ts = res["trade_stats"]
        variant_out[name] = {
            "is": sm["is"], "oos": sm["oos"], "full": sm["full"],
            "trade_stats": ts, "n_trades": res["n_trades"],
        }
        # per-period (non-annualized) Sharpe of the full series for honest DSR
        r = res["returns"]
        trial_sharpes.append(r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else 0.0)
        print(f"{name:<20} {sm['is']['sharpe']:>9.2f} {sm['oos']['sharpe']:>10.2f} "
              f"{sm['oos']['cagr']*100:>8.1f}% {sm['oos']['max_drawdown']*100:>8.1f}% "
              f"{res['n_trades']:>7} {ts['win_rate']*100:>5.1f}")

    # ---- 2) headline = canonical MA-exit, no pyramiding (pre-registered) ----
    cfg = PortfolioConfig(exit_mode=CANONICAL)
    res = run_portfolio(frames, real_orders, cfg, prepared=prepared)
    ret = res["returns"]
    res["trades"].to_csv(RESULTS / "trades.csv", index=False)
    sm = split_metrics(ret, CANONICAL)
    ts = res["trade_stats"]
    print(f"\n=== HEADLINE (kanonisch: {CANONICAL}-Exit, kein Pyramiding) ===")
    print(f"  Full : {fmt(sm['full'])}")
    print(f"  IS   : {fmt(sm['is'])}")
    print(f"  OOS  : {fmt(sm['oos'])}")
    print(f"  Trades {res['n_trades']}, Win {ts['win_rate']*100:.1f}%, "
          f"Profit-Faktor {ts['profit_factor']:.2f}, Payoff {ts['payoff_ratio']:.2f}, "
          f"Ø Halt {ts['avg_holding_days']:.0f}d")

    # ---- 3) benchmarks: same-universe equal-weight B&H + SPY ----
    ew = equal_weight_bh(data, calendar)
    spy_ret = bench.reindex(calendar).ffill().pct_change().fillna(0.0)
    m_ew = split_metrics(ew, "EW-B&H")
    m_spy = split_metrics(spy_ret, "SPY")
    print("\n--- Survivorship-/Beta-Kontrollen (gleiche Periode) ---")
    print(f"  Strategie (OOS): {fmt(sm['oos'])}")
    print(f"  EW-B&H same universe (OOS): {fmt(m_ew['oos'])}  <- Survivorship-Benchmark")
    print(f"  SPY B&H (OOS): {fmt(m_spy['oos'])}")
    beats_ew = sm["oos"]["sharpe"] > m_ew["oos"]["sharpe"]
    print(f"  -> schlägt Strategie das EW-Survivor-B&H (OOS-Sharpe)?  "
          f"{'JA' if beats_ew else 'NEIN'}")

    # ---- 4) significance battery (headline) ----
    print("\n--- Test-Batterie (Headline) ---")
    # random-timing permutation, full period and OOS
    perm_full = random_timing_permutation(frames, real_orders, cfg, prepared,
                                          slice_from=None, n_perm=300)
    perm_oos = random_timing_permutation(frames, real_orders, cfg, prepared,
                                         slice_from=OOS_START, n_perm=300, seed=7)
    print(f"  Random-Timing-Permutation (full): real Sharpe {perm_full['observed']:.2f} "
          f"vs Null {perm_full['null_mean']:.2f}±{perm_full['null_std']:.2f}, "
          f"p={perm_full['p_value']:.4f}")
    print(f"  Random-Timing-Permutation (OOS) : real Sharpe {perm_oos['observed']:.2f} "
          f"vs Null {perm_oos['null_mean']:.2f}±{perm_oos['null_std']:.2f}, "
          f"p={perm_oos['p_value']:.4f}")
    lo, hi = block_bootstrap_sharpe(ret[ret.index >= OOS_START])
    tt = t_test_mean_return(ret[ret.index >= OOS_START])
    pps = ret.mean() / ret.std(ddof=1) if ret.std(ddof=1) > 0 else 0.0
    dsr = deflated_sharpe_ratio(pps, len(ret), len(VARIANTS),
                                returns=ret, trial_sharpes=np.array(trial_sharpes))
    print(f"  Block-Bootstrap Sharpe 95%-KI (OOS): [{lo:+.2f}, {hi:+.2f}]")
    print(f"  t-Test mean daily return (OOS): p={tt['p_value']:.4f}")
    print(f"  Deflated Sharpe (n_trials={len(VARIANTS)}): {dsr['psr_deflated']:.3f}")

    # ---- 5) plots ----
    eq = res["equity"]
    ew_eq = (1 + ew).cumprod() * cfg.start_equity
    spy_eq = (1 + spy_ret).cumprod() * cfg.start_equity
    fig, ax = plt.subplots(figsize=(11.5, 6))
    ax.plot(eq.index, eq.values, label=f"Weinstein Stage-2 ({CANONICAL}) "
            f"(CAGR {sm['full']['cagr']*100:+.1f}%)", color="#1f77b4", lw=1.7)
    ax.plot(ew_eq.index, ew_eq.values, label=f"EW-B&H gleiches Universum "
            f"(CAGR {m_ew['full']['cagr']*100:+.1f}%)", color="#d62728", lw=1.3, alpha=0.8)
    ax.plot(spy_eq.index, spy_eq.values, label=f"S&P 500 (SPY) "
            f"(CAGR {m_spy['full']['cagr']*100:+.1f}%)", color="#7f7f7f", lw=1.1, ls="--")
    ax.axvline(OOS_START, color="black", lw=0.8, ls=":", alpha=0.6)
    ax.set_yscale("log"); ax.set_ylabel("Kontowert (log, Start 100k)")
    ax.set_title("0074 Weinstein Stage-2 vs. Survivorship-Benchmark (EW-B&H gleiches Universum) "
                 "und S&P 500\nSurvivorship-Bias hebt ALLE drei — der Test ist die Differenz, "
                 "nicht das Niveau")
    ax.legend(fontsize=9); ax.grid(alpha=0.3, which="both"); fig.tight_layout()
    fig.savefig(RESULTS / "equity_vs_benchmarks.png", dpi=120); plt.close(fig)

    # variant comparison bar (OOS Sharpe)
    fig, ax = plt.subplots(figsize=(10, 5))
    names = [v[0] for v in VARIANTS]
    oos_sh = [variant_out[n]["oos"]["sharpe"] for n in names]
    ax.bar(names, oos_sh, color=["#2a9d8f" if s > 0 else "#b0b0b0" for s in oos_sh])
    ax.axhline(m_ew["oos"]["sharpe"], color="#d62728", ls="--", lw=1.2,
               label=f"EW-Survivor-B&H OOS-Sharpe {m_ew['oos']['sharpe']:.2f}")
    ax.set_ylabel("OOS-Sharpe"); ax.set_title("0074 — OOS-Sharpe je Exit-/Pyramiding-Variante "
                  "gegen die Survivorship-Messlatte")
    ax.legend(); plt.xticks(rotation=30, ha="right"); fig.tight_layout()
    fig.savefig(RESULTS / "variants_oos_sharpe.png", dpi=120); plt.close(fig)

    # ---- 6) persist metrics ----
    out = {
        "universe_n": len(data), "dropped": dropped, "n_signals": int(n_signals),
        "params": params.__dict__, "oos_start": str(OOS_START.date()),
        "headline_config": CANONICAL,
        "headline": {"full": sm["full"], "is": sm["is"], "oos": sm["oos"],
                     "trade_stats": ts, "n_trades": res["n_trades"]},
        "variants": variant_out,
        "benchmarks": {"ew_bh": {"is": m_ew["is"], "oos": m_ew["oos"], "full": m_ew["full"]},
                       "spy": {"is": m_spy["is"], "oos": m_spy["oos"], "full": m_spy["full"]}},
        "beats_ew_oos_sharpe": bool(beats_ew),
        "tests": {"perm_full": perm_full, "perm_oos": perm_oos,
                  "block_boot_sharpe_oos_ci": [lo, hi], "ttest_oos_p": tt["p_value"],
                  "dsr": dsr},
    }
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=float),
                                          encoding="utf-8")
    print(f"\nSaved: {RESULTS/'metrics.json'}, trades.csv, 2 plots")


if __name__ == "__main__":
    main()
