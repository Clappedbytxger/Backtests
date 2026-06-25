"""Strategy 0070 — SMC sweep+BOS as an equal-weight PORTFOLIO (final close-out).

Builds the correctly-reconstructed 0069 engine (asymmetric pivot + structure
filter + pyramiding/max_concurrent) into an equal-weight portfolio and answers
the two questions:
  1. Does it beat Buy & Hold? (per asset + portfolio, gross AND net)
  2. Is it suitable for a funded/prop account? (drawdown + daily-loss + holding)

The portfolio DROPS assets that do not reproduce the video — i.e. GBPUSD (the
6B-future proxy is not GBP/USD spot; it never goes positive). It keeps the four
that reproduce: Gold, Bitcoin, S&P 500, Nasdaq-100.

"netto" = spread + commission, NO slippage (the video's cost method, the fair
comparison). Slippage is reported separately as a stress.

Run:  python strategies/0070_smc_portfolio/portfolio.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402
from quantlab.metrics import compute_metrics, sharpe_ratio, trade_stats  # noqa: E402
from quantlab.significance import (bootstrap_ci, deflated_sharpe_ratio,  # noqa: E402
                                   permutation_test, t_test_mean_return)

SMC0069 = ROOT / "strategies" / "0069_smc_sweep_bos"
_r = importlib.util.spec_from_file_location("smc_run", SMC0069 / "run.py")
run69 = importlib.util.module_from_spec(_r); _r.loader.exec_module(run69)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# Portfolio members. GBPUSD now uses REAL Dukascopy spot (not the 6B proxy) and
# is a modestly-positive low-correlation FX diversifier (it does NOT reproduce the
# video's +131% even on spot, but Trailing makes it +29% and it lowers portfolio DD).
MEMBERS = ["XAUUSD", "BTCUSD", "SPX", "NDX", "GBPUSD"]
PPY = 365  # portfolio runs on a calendar-day grid (BTC is 24/7)


def asset_overrides(a: dict, P: dict) -> dict:
    return dict(n=a.get("n", P["n"]), forward=a.get("forward", P.get("forward")),
                k=P["k"], buffer_mult=a.get("buffer_mult", P["buffer_mult"]),
                atr_period=P["atr_period"],
                max_concurrent=a.get("max_concurrent", P.get("max_concurrent", 1)))


def load(name: str, a: dict, P: dict) -> pd.DataFrame:
    df = run69.LOADERS[name]()
    df = run69._slice_period(df, P["test_start"], P["test_end"])
    return run69.filter_session(df, a["session"])


def net_costs(a: dict) -> SmcCosts:
    c = a["costs"]
    return SmcCosts(commission_bps=c["commission_bps"], spread_bps=c["spread_bps"])


def daily_series(res: dict, col: str) -> pd.Series:
    s = res[col].copy()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    return s


def buy_and_hold_daily(name: str, P: dict) -> pd.Series:
    df = run69.LOADERS[name]()
    df = run69._slice_period(df, P["test_start"], P["test_end"])
    c = df["Close"].copy()
    c.index = pd.DatetimeIndex(c.index).tz_convert("UTC").tz_localize(None).normalize()
    return c.resample("1D").last().dropna().pct_change().fillna(0.0)


def net_exposure(trades: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    dates = pd.DatetimeIndex(idx).tz_localize(None).normalize().unique().sort_values()
    pos = pd.Series(0.0, index=dates)
    if trades.empty:
        return pos
    for _, t in trades.iterrows():
        a = pd.Timestamp(t["entry_time"]).tz_localize(None).normalize()
        b = pd.Timestamp(t["exit_time"]).tz_localize(None).normalize()
        pos.loc[(pos.index >= a) & (pos.index <= b)] += float(t["direction"])
    return pos


def block_bootstrap_sharpe(returns: pd.Series, block: int = 20, n_boot: int = 3000,
                           seed: int = 42) -> tuple[float, float]:
    """Block bootstrap CI for Sharpe — preserves autocorrelation/trade clustering
    (the simple i.i.d. bootstrap overstates significance when concurrent trades
    ride the same trend)."""
    r = returns.to_numpy()
    m = len(r)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(m / block))
    out = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, max(m - block, 1), nb)
        samp = np.concatenate([r[s:s + block] for s in starts])[:m]
        out[i] = sharpe_ratio(pd.Series(samp), periods_per_year=PPY)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def fmt(m: dict, extra: dict | None = None) -> str:
    rod = m["total_return"] / abs(m["max_drawdown"]) if m["max_drawdown"] else float("nan")
    s = (f"Ret {m['total_return']*100:+7.0f}%  CAGR {m['cagr']*100:+6.1f}%  "
         f"Sharpe {m['sharpe']:5.2f}  MaxDD {m['max_drawdown']*100:6.1f}%  Ret/DD {rod:6.2f}")
    return s


def main() -> None:
    cfg = yaml.safe_load((SMC0069 / "config.yaml").read_text())
    P, assets = cfg["params"], cfg["assets"]
    out = {"members": MEMBERS, "per_asset": {}, "portfolio": {}}

    gross_ser, net_ser, bh_ser = {}, {}, {}
    print("=" * 96)
    print("0070 — SMC Sweep+BOS Portfolio (asym. pivot + structure + pyramiding).  "
          "netto = spread+comm (no slippage)")
    print("=" * 96)

    # ---- per asset: SMC gross/net vs Buy & Hold + edge tests ----
    for name in MEMBERS:
        a = assets[name]
        df = load(name, a, P)
        ov = asset_overrides(a, P)
        rg = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                              risk_frac=a["risk_frac"], costs=SmcCosts(), **ov)
        rn = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                              risk_frac=a["risk_frac"], costs=net_costs(a), **ov)
        tr = rn["trades"]
        bh = compute_metrics(buy_and_hold_daily(name, P),
                             periods_per_year=PPY if name == "BTCUSD" else 252)
        mg, mn = rg["metrics_gross"], rn["metrics_net"]
        beats = "JA " if mn["sharpe"] > bh["sharpe"] else "nein"
        print(f"\n--- {name} ({a['direction']}, mc={ov['max_concurrent']}, "
              f"pivot {ov['n']}/{ov['forward']}, buf {ov['buffer_mult']}) ---")
        print(f"  brutto : {fmt(mg)}")
        print(f"  netto  : {fmt(mn)}")
        print(f"  B&H    : Ret {bh['total_return']*100:+7.0f}%  CAGR {bh['cagr']*100:+6.1f}%  "
              f"Sharpe {bh['sharpe']:5.2f}  MaxDD {bh['max_drawdown']*100:6.1f}%   "
              f"-> SMC schlaegt B&H (Sharpe): {beats}")
        # edge tests (net)
        if not tr.empty:
            pos = net_exposure(tr, df.index)
            ac = run69._slice_period(run69.LOADERS[name](), P["test_start"], P["test_end"])["Close"]
            ac.index = pd.DatetimeIndex(ac.index).tz_convert("UTC").tz_localize(None)
            ar = ac.resample("1D").last().dropna().reindex(pos.index).ffill().pct_change().fillna(0.0)
            nd = daily_series(rn, "returns_net")
            com = nd.index.intersection(pos.index)
            perm = permutation_test(nd.reindex(com).fillna(0), ar.reindex(com).fillna(0),
                                    pos.reindex(com).fillna(0), n_perm=2000)
            boot = bootstrap_ci(tr["r_mult_net"].reset_index(drop=True), statistic="mean", n_boot=2000)
            tt = t_test_mean_return(tr["r_mult_net"])
            print(f"  Tests  : trades {len(tr)} | Permutation p={perm['p_value']:.3f} "
                  f"(Null {perm['null_mean']:.2f} vs real {perm['observed']:.2f}) | "
                  f"Boot Ø-R-KI [{boot['ci_low']:+.3f},{boot['ci_high']:+.3f}] | t-p={tt['p_value']:.3f}")
            out["per_asset"][name] = {"gross": mg, "net": mn, "bh": bh,
                                      "perm_p": perm["p_value"], "boot_R": [boot["ci_low"], boot["ci_high"]],
                                      "n_trades": int(len(tr)), "beats_bh": mn["sharpe"] > bh["sharpe"]}
        if name in MEMBERS:
            gross_ser[name] = daily_series(rg, "returns_gross")
            net_ser[name] = daily_series(rn, "returns_net")
            bh_ser[name] = buy_and_hold_daily(name, P)

    # ---- equal-weight portfolio (members only) ----
    def combine(ser: dict) -> pd.Series:
        X = pd.DataFrame(ser).sort_index()
        full = pd.date_range(X.index.min(), X.index.max(), freq="D")
        return X.reindex(full).fillna(0.0).mean(axis=1)

    pg, pn = combine(gross_ser), combine(net_ser)
    pbh = combine(bh_ser)
    mg, mn, mbh = (compute_metrics(pg, periods_per_year=PPY),
                   compute_metrics(pn, periods_per_year=PPY),
                   compute_metrics(pbh, periods_per_year=PPY))

    print("\n" + "=" * 96)
    print(f"GLEICHGEWICHTETES PORTFOLIO (1/{len(MEMBERS)} je Sleeve: {MEMBERS}) — GBP = echtes Spot")
    print("=" * 96)
    print(f"  brutto    : {fmt(mg)}")
    print(f"  netto     : {fmt(mn)}")
    print(f"  B&H (1/4) : {fmt(mbh)}")
    print(f"  -> Portfolio (netto) schlaegt B&H?  Sharpe {mn['sharpe']:.2f} vs {mbh['sharpe']:.2f} "
          f"= {'JA' if mn['sharpe']>mbh['sharpe'] else 'NEIN'}   |   "
          f"Ret/DD {mn['total_return']/abs(mn['max_drawdown']):.2f} vs "
          f"{mbh['total_return']/abs(mbh['max_drawdown']):.2f}")

    # ---- portfolio test battery (net) ----
    lo, hi = block_bootstrap_sharpe(pn)
    tt = t_test_mean_return(pn)
    pps = pn.mean() / pn.std(ddof=1) if pn.std(ddof=1) > 0 else 0.0
    # honest n_trials: per-asset pivot/buffer/mc scan was sizeable; use 40
    dsr = deflated_sharpe_ratio(pps, len(pn), 40, returns=pn)
    mid = pn.index[len(pn) // 2]
    is_s = compute_metrics(pn[pn.index <= mid], periods_per_year=PPY)["sharpe"]
    oos_s = compute_metrics(pn[pn.index > mid], periods_per_year=PPY)["sharpe"]
    worst_day = pn.min()
    # longest underwater stretch (days)
    eq = (1 + pn).cumprod(); dd = eq / eq.cummax() - 1
    uw = (dd < -1e-9).astype(int)
    longest = (uw * (uw.groupby((uw != uw.shift()).cumsum()).cumcount() + 1)).max()
    pnl_sorted = np.sort(pn[pn > 0].to_numpy())
    top5 = pnl_sorted[-5:].sum() / pn[pn > 0].sum() if (pn > 0).any() else float("nan")

    print("\n  --- Test-Batterie (Portfolio, netto) ---")
    print(f"  Block-Bootstrap Sharpe 95%-KI: [{lo:+.2f}, {hi:+.2f}]  (i.i.d.-Bootstrap überschätzt; "
          f"Block hält Trade-Korrelation)")
    print(f"  t-Test mean daily return p={tt['p_value']:.4f}  |  Deflated Sharpe (n_trials=40)={dsr['psr_deflated']:.3f}")
    print(f"  IS/OOS Sharpe (erste/zweite Hälfte): {is_s:.2f} / {oos_s:.2f}")
    # cost sensitivity at portfolio level
    print("  Kosten-Sensitivität (Portfolio CAGR): "
          f"brutto {mg['cagr']*100:+.1f}%  |  netto(sp+co) {mn['cagr']*100:+.1f}%")

    # ---- funded-account assessment ----
    print("\n  --- Funded-/Prop-Account-Eignung (netto) ---")
    avg_hold = {}
    for name in MEMBERS:
        a = assets[name]; df = load(name, a, P)
        rn = run_smc_backtest(df, direction=a["direction"], exit_type=a["exit"],
                              risk_frac=a["risk_frac"], costs=net_costs(a), **asset_overrides(a, P))
        tr = rn["trades"]
        bars = {"M5": 12, "H1": 24, "M15": 26}[a["timeframe"]]  # ~bars/active-day proxy
        avg_hold[name] = tr["holding_days"].mean() / bars if not tr.empty else float("nan")
    PROP_MAXDD, PROP_DAILY = 0.10, 0.05
    scale_to_fit = PROP_MAXDD / abs(mn["max_drawdown"])
    print(f"  Portfolio-MaxDD (netto): {mn['max_drawdown']*100:.1f}%  vs. typ. Prop-Limit {PROP_MAXDD*100:.0f}% "
          f"-> {'PASST' if abs(mn['max_drawdown'])<=PROP_MAXDD else 'BREACH (zu groß)'}")
    print(f"  Schlechtester Tag (netto): {worst_day*100:.1f}%  vs. typ. Tages-Limit {PROP_DAILY*100:.0f}% "
          f"-> {'ok' if abs(worst_day)<=PROP_DAILY else 'BREACH'}")
    print(f"  Längste Unterwasser-Phase: {int(longest)} Tage  |  Top-5-Tage = {top5*100:.0f}% des Gewinns")
    print(f"  Ø Haltedauer (Tage): " + ", ".join(f"{k} {v:.1f}" for k, v in avg_hold.items())
          + "  -> hält ÜBER NACHT (kein Flat-Overnight-Scalper)")
    print(f"  Um auf {PROP_MAXDD*100:.0f}% MaxDD zu passen: Risiko ×{scale_to_fit:.2f} "
          f"-> Portfolio-CAGR ~{mn['cagr']*scale_to_fit*100:+.1f}% (lineares Down-Sizing)")

    out["portfolio"] = {"gross": mg, "net": mn, "bh": mbh,
                        "block_boot_sharpe_ci": [lo, hi], "ttest_p": tt["p_value"],
                        "dsr": dsr["psr_deflated"], "is_sharpe": is_s, "oos_sharpe": oos_s,
                        "worst_day": float(worst_day), "longest_underwater_days": int(longest),
                        "top5_share": float(top5), "avg_hold_days": avg_hold,
                        "beats_bh_sharpe": bool(mn["sharpe"] > mbh["sharpe"]),
                        "prop_maxdd_scale": float(scale_to_fit)}

    # ---- plot ----
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot((1 + pg).cumprod(), label=f"SMC Portfolio brutto (Ret {mg['total_return']*100:+.0f}%)", color="#1f77b4")
    ax.plot((1 + pn).cumprod(), label=f"SMC Portfolio netto (Ret {mn['total_return']*100:+.0f}%)", color="#2ca02c")
    ax.plot((1 + pbh).cumprod(), label=f"Buy & Hold (1/4) (Ret {mbh['total_return']*100:+.0f}%)", color="#7f7f7f", ls="--")
    ax.set_yscale("log"); ax.set_ylabel("Equity (log, Start=1)")
    ax.set_title("0070 SMC Sweep+BOS — gleichgewichtetes Portfolio (Gold/BTC/SPX/NDX) vs Buy & Hold\n"
                 f"netto Sharpe {mn['sharpe']:.2f} vs B&H {mbh['sharpe']:.2f} | MaxDD {mn['max_drawdown']*100:.0f}% "
                 f"(Prop-Limit 10% -> Risiko x{scale_to_fit:.2f})")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(RESULTS / "portfolio_equity.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nGespeichert: {RESULTS/'portfolio_equity.png'} + metrics.json")


if __name__ == "__main__":
    main()
