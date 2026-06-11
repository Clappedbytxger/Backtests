"""Strategy 0046 — Copper (HG) Fundamental: China Industrial-Production Surprise (H-HG-01)

Hypothesis (from fundamentals/HYPOTHESES.md, H-HG-01):
    China industrial production accelerating above its recent trend → copper demand
    rises ("Dr. Copper" = China is ~50% of global demand) → price rises over 1–3 months.

This is the FIRST fundamental feature to PASS the IC screen (IC(66d)=+0.12, perm-p=0.046,
correct sign). It therefore earns the full validation battery — but it carries several
red flags that the battery must adjudicate:
    (1) The China IP series (FRED CHNPRINTO01IXPYM, OECD MEI) has NO ALFRED vintages
        (1 print per ref month) → PIT is enforced by a conservative PUBLICATION LAG
        (reference month M known by first day of M+2), not by real vintages.
        Robustness: re-run with a 3-month lag.
    (2) The series is DISCONTINUED (ends 2023-11) → not live-tradeable without a
        replacement; this is a historical study.
    (3) Overlapping 66-day forward returns inflate the naive IC t-stat → the
        permutation test (which permutes the held position) is the honest significance.
    (4) Copper had a massive China-supercycle drift (2000-2011) → a long-biased signal
        can look good from beta. IS/OOS split + permutation + B&H comparison control this.

Cross-check: US INDPRO with GENUINE ALFRED vintages (first-print values + real release
    dates) — does a properly-vintaged growth surprise also predict copper? Generalisation
    test + demonstrates the vintage machinery.

Run:
    .venv/Scripts/python.exe strategies/0046_copper_china_ip/run.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics, trade_stats, run_backtest,
    bootstrap_ci, deflated_sharpe_ratio, permutation_test,
    IBKR_METALS_LIQUID,
)
from quantlab.significance import t_test_mean_return  # noqa: E402
from quantlab.data import get_prices                   # noqa: E402
from quantlab import plotting                          # noqa: E402
from quantlab.fundamental_data import get_fred_vintage  # noqa: E402
from quantlab.ic import score_feature, print_scorecard  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS   = RESULTS / "plots"

# ── Pre-registered parameters ────────────────────────────────────────────────
HG_TICKER     = "HG=F"
HG_NAME       = "Kupfer (Copper-Future)"
CHINA_SERIES  = "CHNPRINTO01IXPYM"   # China total industry production index (OECD MEI)
INDPRO_SERIES = "INDPRO"             # US industrial production (genuine ALFRED vintages)
TREND_WINDOW  = 6                    # months for the trend baseline
LAG_MONTHS    = 2                    # conservative publication lag (no vintages)
LAG_STRESS    = 3                    # robustness: more conservative lag
HOLD_DAYS     = 66                   # 3M (pre-registered target horizon)
IC_HORIZONS   = (22, 66)
SPLIT_YEAR    = 2013                 # IS 2000-2012 (supercycle) / OOS 2013-2023
COST_MODEL    = IBKR_METALS_LIQUID   # ~4 bps RT, liquid copper
N_REGISTERED  = 14
N_LOCAL       = 2                    # primary feature × 2 horizons (per-strategy DSR)
N_PERM        = 2000


def guard_prices(prices, ticker):
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{ticker}: non-positive close (lesson 0005).")
    if int(prices["Close"].groupby(prices.index.year).nunique().min()) < 50:
        raise SystemExit(f"{ticker}: frozen feed (lesson 0025).")
    return prices


def trend_surprise(series: pd.Series, lag_months: int) -> pd.DataFrame:
    """Trend-deviation surprise of a monthly index, PIT-lagged.

    surprise = value - rolling(TREND_WINDOW).mean().shift(1)
    release_date = ref_date + lag_months (conservative publication lag).
    """
    df = pd.DataFrame({"value": series.sort_index()})
    df["surprise"] = df["value"] - df["value"].rolling(TREND_WINDOW).mean().shift(1)
    df["release_date"] = df.index + pd.offsets.MonthBegin(lag_months)
    return df.dropna(subset=["surprise"])


def first_print_series(vintage_df: pd.DataFrame) -> pd.Series:
    """As-known-first value per ref_date from an ALFRED vintage frame."""
    return (vintage_df.sort_values("release_date")
            .groupby("ref_date")["value"].first().sort_index())


def first_print_release(vintage_df: pd.DataFrame) -> pd.Series:
    """The real first-release date per ref_date (genuine ALFRED PIT)."""
    return (vintage_df.sort_values("release_date")
            .groupby("ref_date")["release_date"].first().sort_index())


def build_signal(feat: pd.DataFrame, price_index, hold_days, col="surprise", thresh=0.0):
    """Long for hold_days starting at the release after each surprise > thresh."""
    signal = pd.Series(0.0, index=price_index)
    fire = feat[feat[col] > thresh]
    for rel in fire["release_date"]:
        i = price_index.searchsorted(rel)
        if i >= len(price_index):
            continue
        end = min(i + hold_days, len(price_index) - 1)
        signal.iloc[i:end + 1] = 1.0
    return signal


def evaluate(prices, signal, n_trials=1):
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) > 0 else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                n_trials=max(1, n_trials), returns=rets)
    return {"metrics": compute_metrics(rets), "trades": trade_stats(res["trades"]),
            "exposure": float(res["position"].abs().mean()),
            "psr": dsr["psr_deflated"], "returns": rets, "res": res}


def full_eval(prices, signal, split_year, n_trials):
    split = f"{split_year}-01-01"
    e = evaluate(prices, signal, n_trials=n_trials)
    e_is = evaluate(prices.loc[:split], signal.reindex(prices.loc[:split].index, fill_value=0.0))
    e_oos = evaluate(prices.loc[split:], signal.reindex(prices.loc[split:].index, fill_value=0.0))
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=N_PERM)
    boot = bootstrap_ci(e["returns"], statistic="sharpe", n_boot=N_PERM)
    tt = t_test_mean_return(e["returns"])
    bh = compute_metrics(asset_ret)
    return {"e": e, "e_is": e_is, "e_oos": e_oos, "perm": perm, "boot": boot,
            "tt": tt, "bh": bh}


def _line(label, R, extra=""):
    ts, m = R["e"]["trades"], R["e"]["metrics"]
    print(f"  ── {label} ──")
    print(f"    Sharpe {m['sharpe']:.2f}  CAGR {m['cagr']*100:.1f}%  MaxDD {m['max_drawdown']*100:.1f}%  "
          f"Exp {R['e']['exposure']:.0%}  {extra}")
    print(f"    Trades n={ts['n_trades']}  Win {ts['win_rate']:.0%}  Exp/Trade {ts['expectancy']*100:+.2f}%")
    print(f"    IS Sharpe {R['e_is']['metrics']['sharpe']:.2f} | OOS Sharpe {R['e_oos']['metrics']['sharpe']:.2f} "
          f"| B&H Sharpe {R['bh']['sharpe']:.2f}")
    print(f"    Perm-p={R['perm']['p_value']:.3f}  Boot-CI[{R['boot']['ci_low']:.2f},{R['boot']['ci_high']:.2f}]  "
          f"t-p={R['tt']['p_value']:.3f}  DSR-PSR={R['e']['psr']:.3f}")


def main() -> None:
    print(f"\n{'='*66}")
    print(f"  Strategy 0046 — Copper / China-IP Surprise (H-HG-01)")
    print(f"  FIRST fundamental feature to pass the IC gate → full battery")
    print(f"  IS 2000-{SPLIT_YEAR-1} / OOS {SPLIT_YEAR}-2023  |  long if China-IP > {TREND_WINDOW}m-trend, hold {HOLD_DAYS}d")
    print(f"{'='*66}\n")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # ── 0. Load ──────────────────────────────────────────────────────────────
    print("  [0] Kupfer + FRED-Reihen laden …")
    hg = guard_prices(get_prices(HG_TICKER, start="2000-01-01"), HG_TICKER)
    china_v = get_fred_vintage(CHINA_SERIES, start="2000-01-01")
    china = china_v.set_index("ref_date")["value"].sort_index()
    print(f"    China IP: {len(china)} Monate ({china.index.year.min()}–{china.index.year.max()}), "
          f"Vintages/ref={china_v.groupby('ref_date').size().mean():.1f} (KEINE Revisionen)")

    # ── 1. Primary feature + IC screen ───────────────────────────────────────
    print("\n  [1] China-IP Trend-Surprise (Lag 2M) + IC-Screen …\n")
    feat = trend_surprise(china, LAG_MONTHS)
    sc = score_feature(feat, hg, "surprise", horizons=IC_HORIZONS, n_perm=1000)
    print_scorecard(sc)
    p66 = sc["permutation"][66]["p_value"]
    ic66 = sc["ic_decay"].loc[66, "ic"]
    passes = p66 < 0.10 and ic66 > 0
    print(f"\n  IC(66d)={ic66:+.3f}, perm-p={p66:.3f} → {'PASS ✓' if passes else 'FAIL ✗'}")

    # ── 2. Full backtest (primary) ───────────────────────────────────────────
    print("\n  [2] Volle Validierungsbatterie (Primär, Lag 2M) …\n")
    sig = build_signal(feat, hg.index, HOLD_DAYS)
    R = full_eval(hg, sig, SPLIT_YEAR, N_LOCAL)
    _line("China-IP Surprise (Lag 2M)", R)

    # ── 3. Robustness: lag stress (3M) ───────────────────────────────────────
    print("\n  [3] Robustheit — Lag-Stress (3M Publikations-Lag) …\n")
    feat3 = trend_surprise(china, LAG_STRESS)
    sig3 = build_signal(feat3, hg.index, HOLD_DAYS)
    R3 = full_eval(hg, sig3, SPLIT_YEAR, N_LOCAL)
    _line("China-IP Surprise (Lag 3M)", R3)

    # ── 4. Cross-check: US INDPRO with GENUINE vintages ──────────────────────
    print("\n  [4] Cross-Check — US INDPRO (echte ALFRED-Vintages, First-Print) …\n")
    indpro_v = get_fred_vintage(INDPRO_SERIES, start="2000-01-01")
    indpro_fp = first_print_series(indpro_v)
    indpro_rel = first_print_release(indpro_v)
    feat_us = pd.DataFrame({"value": indpro_fp})
    feat_us["surprise"] = feat_us["value"] - feat_us["value"].rolling(TREND_WINDOW).mean().shift(1)
    feat_us["release_date"] = indpro_rel.reindex(feat_us.index)  # REAL first-release date
    feat_us = feat_us.dropna(subset=["surprise", "release_date"])
    sig_us = build_signal(feat_us, hg.index, HOLD_DAYS)
    R_us = full_eval(hg, sig_us, SPLIT_YEAR, N_LOCAL)
    _line("US-INDPRO Surprise (echte Vintages)", R_us)

    # ── 5. Plots ─────────────────────────────────────────────────────────────
    print("\n  [5] Plots …")
    _make_plots(feat, hg, sc, R, R3, R_us)

    # ── 6. Persist + verdict ─────────────────────────────────────────────────
    print("  [6] Speichern …")
    def slim(R):
        ts, m = R["e"]["trades"], R["e"]["metrics"]
        return {"sharpe": m["sharpe"], "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                "n_trades": ts["n_trades"], "win_rate": ts["win_rate"],
                "expectancy_pct": ts["expectancy"] * 100, "exposure": R["e"]["exposure"],
                "sharpe_is": R["e_is"]["metrics"]["sharpe"], "sharpe_oos": R["e_oos"]["metrics"]["sharpe"],
                "bh_sharpe": R["bh"]["sharpe"], "perm_p": R["perm"]["p_value"],
                "boot_ci": [R["boot"]["ci_low"], R["boot"]["ci_high"]],
                "t_p": R["tt"]["p_value"], "dsr_psr": R["e"]["psr"]}
    summary = {
        "strategy": "0046_copper_china_ip", "hypothesis": "H-HG-01",
        "china_series": CHINA_SERIES, "china_has_vintages": False,
        "series_ends": "2023-11 (discontinued)",
        "lag_months": LAG_MONTHS, "hold_days": HOLD_DAYS, "split_year": SPLIT_YEAR,
        "ic_screen": {str(h): {"ic": float(sc["ic_decay"].loc[h, "ic"]),
                               "p_value": sc["permutation"][h]["p_value"],
                               "n_obs": sc["permutation"][h]["n_obs"]} for h in IC_HORIZONS},
        "primary_lag2": slim(R), "robust_lag3": slim(R3), "crosscheck_indpro": slim(R_us),
        "cost_model": "IBKR_METALS_LIQUID (~4 bps RT)",
        "n_registered": N_REGISTERED, "n_local_tests": N_LOCAL,
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    if not R["e"]["res"]["trades"].empty:
        R["e"]["res"]["trades"].to_csv(RESULTS / "trades.csv")
    print(f"    → {RESULTS}")

    # Verdict logic
    print("\n  ── Verdict ───────────────────────────────────────────────────────")
    crit = {
        "perm p<0.05":     R["perm"]["p_value"] < 0.05,
        "OOS≥0.5·IS":      R["e_oos"]["metrics"]["sharpe"] >= 0.5 * R["e_is"]["metrics"]["sharpe"]
                           and R["e_oos"]["metrics"]["sharpe"] > 0,
        "Boot-KI ohne 0":  R["boot"]["ci_low"] > 0,
        "lag3 robust":     R3["perm"]["p_value"] < 0.10,
        "schlägt B&H":     R["e"]["metrics"]["sharpe"] > R["bh"]["sharpe"],
    }
    for k, ok in crit.items():
        print(f"    [{'✓' if ok else '✗'}] {k}")
    n_ok = sum(crit.values())
    if n_ok >= 4 and crit["perm p<0.05"] and crit["OOS≥0.5·IS"]:
        print(f"\n    ⚠ SCHWACHER LEAD ({n_ok}/5) — erstes Fundamental-Signal; Forward-Test/Ersatzreihe nötig")
    elif crit["perm p<0.05"]:
        print(f"\n    ⚠ GRENZWERTIG ({n_ok}/5) — IC-Gate bestanden, aber Validierung wackelig")
    else:
        print(f"\n    ✗ ABGELEHNT ({n_ok}/5) — IC-Gate war Multiple-Testing-Artefakt")
    print()


def _make_plots(feat, hg, sc, R, R3, R_us):
    import matplotlib.pyplot as plt

    # Feature + price
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))
    s = feat["surprise"]
    ax1.fill_between(s.index, 0, s.values, where=s.values > 0, color="#2a9d8f", alpha=0.6, label="über Trend")
    ax1.fill_between(s.index, 0, s.values, where=s.values <= 0, color="#e76f51", alpha=0.6, label="unter Trend")
    ax1.axhline(0, color="black", lw=0.6); ax1.set_ylabel("China-IP Trend-Surprise"); ax1.legend(fontsize=8)
    ax1.set_title("China Industrieproduktion — Abweichung vom 6M-Trend (PIT-Lag 2M)")
    ax2.plot(hg.index, hg["Close"], color="#bc6c25", lw=0.8); ax2.set_ylabel("HG=F ($/lb)")
    ax2.set_title("Kupfer-Preis (Long-Perioden: China-IP über Trend, grün unterlegt)")
    z = feat.set_index("release_date")["surprise"].reindex(hg.index, method="ffill")
    for i in np.where((z > 0).values)[0]:
        ax2.axvspan(hg.index[i], hg.index[min(i+1, len(hg.index)-1)], color="#2a9d8f", alpha=0.04)
    plt.tight_layout()
    plotting._add_caption(fig,
        "China-IP Trend-Surprise (FRED OECD MEI, KEINE Vintages → konservativer 2M-Publikations-Lag). "
        "Reihe endet 2023-11 (discontinued). Erstes Fundamental-Feature, das den IC-Gate passiert (p=0.046).")
    plotting.savefig(fig, PLOTS / "china_ip_overview.png")
    plt.close(fig)

    # Equity comparison
    fig2 = plotting.plot_equity(
        R["e"]["res"]["equity"], benchmark=R["e"]["res"]["buy_hold"],
        title="0046 Kupfer / China-IP-Surprise vs. Buy & Hold",
        strategy_label="China-IP > Trend (long, hold 66d)", benchmark_label="Kupfer Buy & Hold",
        caption=(f"Netto (IBKR_METALS_LIQUID ~4 bps RT). Perm-p={R['perm']['p_value']:.3f}, "
                 f"DSR-PSR={R['e']['psr']:.3f}. IS/OOS-Split 2013 (China-Superzyklus-Drift-Kontrolle). "
                 f"Lag-3M-Robustheit: perm-p={R3['perm']['p_value']:.3f}; "
                 f"US-INDPRO-Cross-Check perm-p={R_us['perm']['p_value']:.3f}."))
    plotting.savefig(fig2, PLOTS / "equity_vs_bh.png")
    plt.close(fig2)

    # IC decay
    fig3, ax = plt.subplots(figsize=(6, 5))
    decay = sc["ic_decay"]; hs = decay.index.tolist()
    bars = ax.bar(range(len(hs)), decay["ic"].values, color=["#2a9d8f", "#e9c46a"][:len(hs)], alpha=0.85)
    ax.axhline(0, color="black", lw=0.7); ax.set_xticks(range(len(hs)))
    ax.set_xticklabels([f"{h}d" for h in hs]); ax.set_ylabel("Spearman IC")
    ax.set_title("0046 — IC-Decay (China-IP-Surprise → Kupfer)")
    for i, h in enumerate(hs):
        ax.text(i, decay["ic"].values[i] + 0.003, f"p={sc['permutation'][h]['p_value']:.3f}",
                ha="center", fontsize=9)
    plotting._add_caption(fig3, "Einziges Fundamental-Feature mit IC>0 bei p<0.10 (66d). Validierung entscheidet, "
                                "ob echt oder Multiple-Testing-Treffer unter 14 registrierten Hypothesen.")
    plt.tight_layout()
    plotting.savefig(fig3, PLOTS / "ic_decay.png")
    plt.close(fig3)


if __name__ == "__main__":
    main()
