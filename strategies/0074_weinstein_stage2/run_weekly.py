"""Strategy 0074 (weekly variant) — Weinstein Stage-2 on the CANONICAL 30-WEEK MA.

Same strategy, same engine, same universe and battery as ``run.py`` — but on
**weekly bars with the 30-week moving average**, i.e. Weinstein's *original* chart
(``run.py`` was the user's 30-day daily adaptation). Everything that was measured
in trading days is now measured in weeks (base window, volume average, RS, exits),
and all metrics annualize with 52 periods/year instead of 252.

Why this matters: the weekly 30-week MA is far slower, so trades are rarer and
held for months — the regime where transaction cost is negligible and where
Weinstein claimed the edge lives. The two structural controls are unchanged and
remain decisive: (a) equal-weight Buy & Hold of the SAME (survivorship-biased)
universe and (b) the random-timing permutation that isolates entry-timing skill.

Run:  .venv/Scripts/python.exe strategies/0074_weinstein_stage2/run_weekly.py
"""

from __future__ import annotations

import importlib.util
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
from quantlab.metrics import compute_metrics, sharpe_ratio  # noqa: E402
from quantlab.significance import (                 # noqa: E402
    deflated_sharpe_ratio, t_test_mean_return,
)
from quantlab.weinstein import (                    # noqa: E402
    EntryParams, PortfolioConfig, detect_stage2_entries,
    build_orders, build_random_orders, prepare_data, run_portfolio,
)

# Reuse the daily script's universe / variant grid / benchmark helper.
_spec = importlib.util.spec_from_file_location("run0074", Path(__file__).parent / "run.py")
daily = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(daily)

RESULTS = Path(__file__).resolve().parent / "results"
START = "2000-01-01"
OOS_START = pd.Timestamp("2015-01-01")
BENCH = "SPY"
PPY = 52                                            # weekly annualization
UNIVERSE = daily.UNIVERSE
VARIANTS = daily.VARIANTS
CANONICAL = daily.CANONICAL

# Weekly Stage-2 parameters (the daily defaults re-expressed in WEEKS).
WK_PARAMS = EntryParams(
    ma_period=30, base_window=30, min_touches=3, touch_band=0.05,
    vol_window=10, vol_mult=1.5, rs_period=30, ma_cross_lookback=8,
    rs_cross_lookback=12, max_base_range=0.50, max_ma_slope=0.15,
    atr_period=14, stop_mode="support", stop_buffer=0.03,
)


def load_universe_weekly() -> tuple[dict, pd.Series, list]:
    """Weekly OHLCV for the universe + benchmark, with a data-quality screen."""
    bench = get_close(BENCH, start=START, interval="1wk")
    data, dropped = {}, []
    for tk in UNIVERSE:
        try:
            df = get_prices(tk, start=START, interval="1wk")
        except Exception as exc:  # noqa: BLE001
            dropped.append((tk, f"load error: {exc}")); continue
        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if len(df) < 150:                          # ~3 years of weekly bars
            dropped.append((tk, f"too short ({len(df)})")); continue
        zero_frac = float((df["Close"].pct_change().abs() < 1e-9).mean())
        if zero_frac > 0.4:
            dropped.append((tk, f"frozen (zero={zero_frac:.2f})")); continue
        data[tk] = df
    return data, bench, dropped


def split_metrics(ret: pd.Series) -> dict:
    return {
        "full": compute_metrics(ret, periods_per_year=PPY),
        "is": compute_metrics(ret[ret.index < OOS_START], periods_per_year=PPY),
        "oos": compute_metrics(ret[ret.index >= OOS_START], periods_per_year=PPY),
    }


def block_bootstrap_sharpe(ret: pd.Series, block: int = 8, n_boot: int = 3000,
                           seed: int = 42) -> tuple[float, float]:
    r = ret.to_numpy(); m = len(r); rng = np.random.default_rng(seed)
    nb = int(np.ceil(m / block)); out = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, max(m - block, 1), nb)
        samp = np.concatenate([r[s:s + block] for s in starts])[:m]
        out[i] = sharpe_ratio(pd.Series(samp), periods_per_year=PPY)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def random_timing_permutation(frames, real_orders, cfg, prepared,
                              slice_from=None, n_perm=300, seed=42) -> dict:
    counts = {tk: len(v) for tk, v in real_orders.items()}
    real = run_portfolio(frames, real_orders, cfg, prepared=prepared, periods_per_year=PPY)["returns"]
    if slice_from is not None:
        real = real[real.index >= slice_from]
    observed = sharpe_ratio(real, periods_per_year=PPY)
    rng = np.random.default_rng(seed); null = np.empty(n_perm)
    for i in range(n_perm):
        ro = build_random_orders(frames, counts, rng, warmup=35)
        rr = run_portfolio(frames, ro, cfg, prepared=prepared, periods_per_year=PPY)["returns"]
        if slice_from is not None:
            rr = rr[rr.index >= slice_from]
        null[i] = sharpe_ratio(rr, periods_per_year=PPY)
    p = float((np.sum(null >= observed) + 1) / (n_perm + 1))
    return {"observed": float(observed), "p_value": p,
            "null_mean": float(np.nanmean(null)), "null_std": float(np.nanstd(null)),
            "n_perm": n_perm}


def main() -> None:
    print("=" * 92)
    print("0074 (WEEKLY) — Weinstein Stage-2 on the CANONICAL 30-WEEK MA")
    print("=" * 92)

    data, bench, dropped = load_universe_weekly()
    print(f"Universe (weekly): {len(data)}/{len(UNIVERSE)} (dropped {[d[0] for d in dropped]})")

    frames = {tk: df.join(detect_stage2_entries(df, bench, WK_PARAMS)) for tk, df in data.items()}
    n_signals = sum(int(f["signal"].sum()) for f in frames.values())
    print(f"Stage-2 weekly signals: {n_signals}  (MA{WK_PARAMS.ma_period}wk, "
          f"base{WK_PARAMS.base_window}wk, touches>={WK_PARAMS.min_touches}, vol>{WK_PARAMS.vol_mult}x)")

    prepared = prepare_data(frames); calendar = prepared[1]
    real_orders = build_orders(frames)

    # ---- variant scan ----
    print("\n--- Exit-/Pyramiding-Varianten (wöchentlich, netto IBKR) ---")
    print(f"{'Variante':<20} {'IS Shrp':>8} {'OOS Shrp':>9} {'OOS CAGR':>9} "
          f"{'OOS MaxDD':>9} {'Trades':>7} {'Win%':>6}")
    variant_out = {}; trial_sharpes = []
    for name, kw in VARIANTS:
        cfg = PortfolioConfig(**kw)
        res = run_portfolio(frames, real_orders, cfg, prepared=prepared, periods_per_year=PPY)
        sm = split_metrics(res["returns"]); ts = res["trade_stats"]
        variant_out[name] = {"is": sm["is"], "oos": sm["oos"], "full": sm["full"],
                             "trade_stats": ts, "n_trades": res["n_trades"]}
        r = res["returns"]
        trial_sharpes.append(r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else 0.0)
        print(f"{name:<20} {sm['is']['sharpe']:>8.2f} {sm['oos']['sharpe']:>9.2f} "
              f"{sm['oos']['cagr']*100:>8.1f}% {sm['oos']['max_drawdown']*100:>8.1f}% "
              f"{res['n_trades']:>7} {ts['win_rate']*100:>5.1f}")

    # ---- headline (canonical MA-exit) ----
    cfg = PortfolioConfig(exit_mode=CANONICAL)
    res = run_portfolio(frames, real_orders, cfg, prepared=prepared, periods_per_year=PPY)
    ret = res["returns"]; res["trades"].to_csv(RESULTS / "trades_weekly.csv", index=False)
    sm = split_metrics(ret); ts = res["trade_stats"]
    print(f"\n=== HEADLINE WEEKLY (kanonisch: 30-Wochen-MA-Exit, kein Pyramiding) ===")
    print(f"  Full: {daily.fmt(sm['full'])}")
    print(f"  IS  : {daily.fmt(sm['is'])}")
    print(f"  OOS : {daily.fmt(sm['oos'])}")
    print(f"  Trades {res['n_trades']}, Win {ts['win_rate']*100:.1f}%, "
          f"PF {ts['profit_factor']:.2f}, Payoff {ts['payoff_ratio']:.2f}, "
          f"Ø Halt {ts['avg_holding_days']:.0f} Geschäftstage (~{ts['avg_holding_days']/5:.0f} Wo)")

    # ---- benchmarks ----
    ew = daily.equal_weight_bh(data, calendar)
    spy_ret = bench.reindex(calendar).ffill().pct_change().fillna(0.0)
    m_ew = split_metrics(ew); m_spy = split_metrics(spy_ret)
    beats_ew = sm["oos"]["sharpe"] > m_ew["oos"]["sharpe"]
    print("\n--- Survivorship-/Beta-Kontrollen (gleiche Periode, OOS) ---")
    print(f"  Strategie : {daily.fmt(sm['oos'])}")
    print(f"  EW-B&H    : {daily.fmt(m_ew['oos'])}  <- Survivorship-Benchmark")
    print(f"  SPY       : {daily.fmt(m_spy['oos'])}")
    print(f"  -> schlägt EW-B&H (OOS-Sharpe)? {'JA' if beats_ew else 'NEIN'}")

    # ---- battery ----
    print("\n--- Test-Batterie (Headline weekly) ---")
    perm_full = random_timing_permutation(frames, real_orders, cfg, prepared, None, 300)
    perm_oos = random_timing_permutation(frames, real_orders, cfg, prepared, OOS_START, 300, 7)
    print(f"  Random-Timing-Perm (full): real {perm_full['observed']:.2f} vs Null "
          f"{perm_full['null_mean']:.2f}±{perm_full['null_std']:.2f}, p={perm_full['p_value']:.4f}")
    print(f"  Random-Timing-Perm (OOS) : real {perm_oos['observed']:.2f} vs Null "
          f"{perm_oos['null_mean']:.2f}±{perm_oos['null_std']:.2f}, p={perm_oos['p_value']:.4f}")
    lo, hi = block_bootstrap_sharpe(ret[ret.index >= OOS_START])
    tt = t_test_mean_return(ret[ret.index >= OOS_START])
    pps = ret.mean() / ret.std(ddof=1) if ret.std(ddof=1) > 0 else 0.0
    dsr = deflated_sharpe_ratio(pps, len(ret), len(VARIANTS), returns=ret,
                                trial_sharpes=np.array(trial_sharpes))
    print(f"  Block-Bootstrap Sharpe 95%-KI (OOS): [{lo:+.2f}, {hi:+.2f}]")
    print(f"  t-Test mean weekly return (OOS): p={tt['p_value']:.4f}")
    print(f"  Deflated Sharpe (n_trials={len(VARIANTS)}): {dsr['psr_deflated']:.3f}")

    # ---- plot ----
    eq = res["equity"]
    ew_eq = (1 + ew).cumprod() * cfg.start_equity
    spy_eq = (1 + spy_ret).cumprod() * cfg.start_equity
    fig, ax = plt.subplots(figsize=(11.5, 6))
    ax.plot(eq.index, eq.values, label=f"Weinstein 30-Wochen ({CANONICAL}) "
            f"(CAGR {sm['full']['cagr']*100:+.1f}%)", color="#1f77b4", lw=1.7)
    ax.plot(ew_eq.index, ew_eq.values, label=f"EW-B&H gleiches Universum "
            f"(CAGR {m_ew['full']['cagr']*100:+.1f}%)", color="#d62728", lw=1.3, alpha=0.8)
    ax.plot(spy_eq.index, spy_eq.values, label=f"S&P 500 (SPY) "
            f"(CAGR {m_spy['full']['cagr']*100:+.1f}%)", color="#7f7f7f", lw=1.1, ls="--")
    ax.axvline(OOS_START, color="black", lw=0.8, ls=":", alpha=0.6)
    ax.set_yscale("log"); ax.set_ylabel("Kontowert (log, Start 100k)")
    ax.set_title("0074 Weinstein 30-WOCHEN-MA (Original) vs Survivorship-Benchmark & S&P 500")
    ax.legend(fontsize=9); ax.grid(alpha=0.3, which="both"); fig.tight_layout()
    fig.savefig(RESULTS / "equity_weekly.png", dpi=120); plt.close(fig)

    out = {
        "variant": "weekly_30week_MA", "universe_n": len(data), "n_signals": int(n_signals),
        "params": WK_PARAMS.__dict__, "periods_per_year": PPY,
        "headline": {"full": sm["full"], "is": sm["is"], "oos": sm["oos"],
                     "trade_stats": ts, "n_trades": res["n_trades"]},
        "variants": variant_out,
        "benchmarks": {"ew_bh": m_ew, "spy": m_spy},
        "beats_ew_oos_sharpe": bool(beats_ew),
        "tests": {"perm_full": perm_full, "perm_oos": perm_oos,
                  "block_boot_sharpe_oos_ci": [lo, hi], "ttest_oos_p": tt["p_value"],
                  "dsr": dsr},
    }
    (RESULTS / "metrics_weekly.json").write_text(json.dumps(out, indent=2, default=float),
                                                 encoding="utf-8")
    print(f"\nSaved: {RESULTS/'metrics_weekly.json'}, trades_weekly.csv, equity_weekly.png")


if __name__ == "__main__":
    main()
