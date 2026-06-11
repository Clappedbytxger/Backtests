"""Strategy 0042 — Sugar #11 (SB) Fundamental: São Paulo Drought + WASDE Surprise

Tests two pre-registered hypotheses from fundamentals/HYPOTHESES.md:

  H-SB-01 (weather): São Paulo precipitation deficit in growth phase (Oct–Mar)
           → USDA production downgrade → SB price ↑ over 1–3 months.
           Feature: monthly precipitation_sum z-score (ERA5, Open-Meteo, keyless).
           Threshold: z < -1.5 σ (pre-registered). Hold: 22 trading days.

  H-SB-03 (WASDE): Monthly USDA S&D revision — negative surprise (downgrade)
           → diffusion over 1 month.
           Feature: current_month_production − prior_month_production (naïve proxy).
           Threshold: surprise < 0 (any downgrade, pre-registered). Hold: 22 days.

Workflow (strictly sequential, no post-hoc parameter search):
  1. IC screen (Spearman rank IC + permutation test, 3 horizons × 2 features)
  2. Full backtest only if any feature clears IC perm-p < 0.10 at the target horizon
  3. Validation battery: permutation, bootstrap CI, IS/OOS split, DSR
  4. Multiple-testing budget: N_local = 6 (2 features × 3 horizons); against
     N_registered = 14 in HYPOTHESES.md

PIT-correctness:
  - Weather release_date = first of following month (all daily data known then)
  - WASDE release_date ≈ 10th of the month (naïve proxy, documented)
  - pit_join() enforces the PIT contract for daily signal alignment

Run:
    .venv/Scripts/python.exe strategies/0042_sugar_sb_fundamental/run.py
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
    IBKR_SOFTS,
)
from quantlab.significance import t_test_mean_return  # noqa: E402
from quantlab.data import get_prices                   # noqa: E402
from quantlab import plotting                          # noqa: E402
from quantlab.fundamental_data import (               # noqa: E402
    get_weather_daily, get_wasde_psd, WASDE_COMMODITY, REGION_COORDS,
)
from quantlab.features import (                       # noqa: E402
    weather_anomaly, wasde_surprise, pit_join,
)
from quantlab.ic import score_feature, print_scorecard  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS   = RESULTS / "plots"

# ── Pre-registered parameters (from HYPOTHESES.md — do NOT tune) ─────────────
TICKER         = "SB=F"
ASSET_NAME     = "Zucker #11 (Sugar-Future)"
SPLIT_YEAR     = 2015          # IS: 2000–2014, OOS: 2015–2025
HOLD_DAYS      = 22            # 1 calendar month (~1M horizon, H-SB-01 and H-SB-03)
IC_HORIZONS    = (5, 22, 66)   # 1W / 1M / 3M
WEATHER_THRESH = -1.5          # σ — pre-registered in H-SB-01
WASDE_THRESH   = 0.0           # any downgrade — pre-registered in H-SB-03
COST_MODEL     = IBKR_SOFTS    # 8 bps RT, 4 bps/side
N_REGISTERED   = 14            # total hypotheses in HYPOTHESES.md
N_LOCAL        = 6             # features × horizons tested here (for DSR)
N_PERM         = 2000


# ── Signal builder ────────────────────────────────────────────────────────────

def build_fundamental_signal(
    feature_df: pd.DataFrame,
    feature_col: str,
    threshold: float,
    hold_days: int,
    price_index: pd.DatetimeIndex,
    direction: float = 1.0,
    condition: str = "below",
) -> pd.Series:
    """Convert release-dated fundamental feature into a daily position signal.

    For each release date where the feature crosses the threshold, the signal
    is set to ``direction`` for ``hold_days`` trading days.  Overlapping
    triggers (consecutive months both in drought) extend the position.

    Args:
        condition: ``"below"`` fires when feature < threshold (drought signal);
                   ``"above"`` fires when feature > threshold.

    Returns:
        pd.Series indexed like price_index, values in {0, direction}.
        The backtest engine shifts this by 1 day (no look-ahead).
    """
    signal = pd.Series(0.0, index=price_index)

    for idx_date in feature_df.index:
        val          = feature_df.loc[idx_date, feature_col]
        release_date = feature_df.loc[idx_date, "release_date"]

        if pd.isna(val) or pd.isna(release_date):
            continue

        triggered = (val < threshold) if condition == "below" else (val > threshold)
        if not triggered:
            continue

        entry_idx = price_index.searchsorted(release_date)
        if entry_idx >= len(price_index):
            continue
        exit_idx = min(entry_idx + hold_days, len(price_index) - 1)
        signal.iloc[entry_idx : exit_idx + 1] = direction

    return signal


# ── Backtest helpers ──────────────────────────────────────────────────────────

def evaluate(prices: pd.DataFrame, signal: pd.Series, n_trials: int = 1) -> dict:
    res  = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    m    = compute_metrics(rets)
    ts   = trade_stats(res["trades"])
    sp   = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) > 0 else 0.0
    dsr  = deflated_sharpe_ratio(
        observed_sharpe=float(sp), n_obs=len(rets),
        n_trials=max(1, n_trials), returns=rets,
    )
    return {
        "metrics":  m,
        "trades":   ts,
        "exposure": float(res["position"].abs().mean()),
        "psr":      dsr["psr_deflated"],
        "returns":  rets,
        "res":      res,
    }


def evaluate_with_split(
    prices: pd.DataFrame,
    signal: pd.Series,
    split_year: int,
    n_trials: int = 1,
) -> dict:
    split = f"{split_year}-01-01"
    e    = evaluate(prices, signal, n_trials=n_trials)
    e_is = evaluate(prices.loc[:split], signal.reindex(prices.loc[:split].index, fill_value=0.0))
    e_oos= evaluate(prices.loc[split:], signal.reindex(prices.loc[split:].index, fill_value=0.0))

    asset_ret = prices["Close"].pct_change().fillna(0.0)
    perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=N_PERM)
    boot = bootstrap_ci(e["returns"], statistic="sharpe", n_boot=N_PERM)
    tt   = t_test_mean_return(e["returns"])
    bh   = compute_metrics(asset_ret)

    return {
        "e": e, "e_is": e_is, "e_oos": e_oos,
        "perm": perm, "boot": boot, "tt": tt, "bh": bh,
        "split": split,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'='*66}")
    print(f"  Strategy 0042 — Sugar SB Fundamental")
    print(f"  H-SB-01 (weather) + H-SB-03 (WASDE)  |  ticker: {TICKER}")
    print(f"  IS 2000–{SPLIT_YEAR-1}  OOS {SPLIT_YEAR}–heute  |  hold={HOLD_DAYS}d")
    print(f"{'='*66}\n")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # ── 0. Load SB prices ────────────────────────────────────────────────────
    print("  [0] Preise laden …")
    prices = get_prices(TICKER, start="2000-01-01")

    # Data quality guards (lessons 0005 + 0025)
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close (guard 0005).")
    yearly_unique = prices["Close"].groupby(prices.index.year).nunique()
    if int(yearly_unique.min()) < 50:
        raise SystemExit(f"{TICKER}: frozen feed (guard 0025).")

    years_avail = f"{prices.index.year.min()}–{prices.index.year.max()}"
    print(f"    SB=F: {len(prices)} Handelstage, {years_avail}, "
          f"Close {prices['Close'].min():.1f}–{prices['Close'].max():.1f} ¢/lb\n")

    # ── 1. Feature H-SB-01: São Paulo Precipitation Anomaly (Open-Meteo) ────
    print("  [1] H-SB-01: Wetter-Feature laden (Open-Meteo, keyless) …")
    lat, lon = REGION_COORDS["sao_paulo_sugarcane"]
    today    = pd.Timestamp.now().strftime("%Y-%m-%d")

    weather_raw = get_weather_daily(
        lat=lat, lon=lon,
        start="1990-01-01", end=today,
        variables=["precipitation_sum"],
    )
    weather_anom = weather_anomaly(
        weather_raw, "precipitation_sum", agg="sum", window_years=20, min_years=5,
    )
    # Filter to growth-phase months (Oct–Mar, CWB cane cycle) to avoid off-season noise
    growth_months = {10, 11, 12, 1, 2, 3}
    weather_anom_gp = weather_anom[weather_anom.index.month.isin(growth_months)].copy()
    n_weather = len(weather_anom_gp.dropna(subset=["precipitation_sum_anomaly"]))
    print(f"    São Paulo Niederschlag-Anomalie: {n_weather} Monate in Wachstumsphase "
          f"({weather_anom_gp.index.year.min()}–{weather_anom_gp.index.year.max()})\n")

    # ── 2. Feature H-SB-03: WASDE Production Surprise (FAS PSD, no key) ────
    print("  [2] H-SB-03: WASDE-Feature laden (USDA FAS PSD) …")
    wasde_loaded = False
    wasde_surp   = None
    try:
        wasde_raw = get_wasde_psd(
            commodity_code=WASDE_COMMODITY["sugar_centrifugal"],
            country_code="0000",     # world total
            start_year=2000,
            attribute="Production",
        )
        if wasde_raw.empty:
            raise ValueError("FAS PSD returned empty DataFrame.")

        wasde_surp = wasde_surprise(wasde_raw, value_col="value")
        wasde_loaded = True
        print(f"    WASDE Produktion-Surprise: {len(wasde_surp)} Monatsdaten "
              f"({wasde_surp.index.year.min()}–{wasde_surp.index.year.max()})\n")
    except Exception as ex:
        print(f"    ⚠  WASDE-Daten nicht verfügbar ({ex}). H-SB-03 wird übersprungen.\n")
        print("    → Fallback: WASDE manuell testen wenn API-Zugang vorhanden.\n")

    # ── 3. IC Screen ─────────────────────────────────────────────────────────
    print("  [3] IC-Screen (Spearman-IC + Permutation, 3 Horizonte) …\n")

    scorecards = {}

    # H-SB-01: negate anomaly so positive IC = drought predicts price rise
    weather_feat_df = weather_anom_gp.copy()
    weather_feat_df["neg_precip_anomaly"] = -weather_feat_df["precipitation_sum_anomaly"]
    sc_weather = score_feature(
        weather_feat_df, prices, "neg_precip_anomaly",
        horizons=IC_HORIZONS, n_perm=500,
    )
    scorecards["H-SB-01 (Niederschlag-Anomalie)"] = sc_weather
    print_scorecard(sc_weather)

    if wasde_loaded:
        # H-SB-03: negate surprise so positive IC = downgrade predicts price rise
        wasde_feat_df = wasde_surp.copy()
        wasde_feat_df["neg_surprise_pct"] = -wasde_feat_df["surprise_pct"].fillna(0.0)
        sc_wasde = score_feature(
            wasde_feat_df, prices, "neg_surprise_pct",
            horizons=IC_HORIZONS, n_perm=500,
        )
        scorecards["H-SB-03 (WASDE-Surprise)"] = sc_wasde
        print_scorecard(sc_wasde)

    # Gate: proceed only if at least one feature has perm p < 0.10 at target horizon
    weather_passes = sc_weather["permutation"].get(HOLD_DAYS, {}).get("p_value", 1.0) < 0.10
    wasde_passes   = (
        wasde_loaded
        and sc_wasde["permutation"].get(HOLD_DAYS, {}).get("p_value", 1.0) < 0.10
    )
    any_passes = weather_passes or wasde_passes

    print(f"\n  IC-Screen Ergebnis:")
    print(f"    H-SB-01 bei {HOLD_DAYS}d: {'PASS ✓' if weather_passes else 'FAIL ✗'} "
          f"(p={sc_weather['permutation'].get(HOLD_DAYS, {}).get('p_value', float('nan')):.3f})")
    if wasde_loaded:
        print(f"    H-SB-03 bei {HOLD_DAYS}d: {'PASS ✓' if wasde_passes else 'FAIL ✗'} "
              f"(p={sc_wasde['permutation'].get(HOLD_DAYS, {}).get('p_value', float('nan')):.3f})")

    if not any_passes:
        print(
            "\n  ⛔  Kein Feature übersteht den IC-Screen bei p<0.10. "
            "Voller Backtest wird nicht ausgeführt — das ist das korrekte Ergebnis.\n"
            "  Verdict: H-SB-01 und H-SB-03 ABGELEHNT auf IC-Ebene.\n"
            "  Kein weiterer Tuning-Versuch (das würde Multiple-Testing-N erhöhen)."
        )
        _save_ic_only(scorecards, wasde_loaded, weather_anom_gp, prices)
        return

    print("\n  → Mindestens ein Feature besteht den Screen. Vollständiger Backtest …\n")

    # ── 4. Signals ───────────────────────────────────────────────────────────
    price_index = prices.index

    sig_weather = build_fundamental_signal(
        weather_anom_gp, "precipitation_sum_anomaly",
        threshold=WEATHER_THRESH, hold_days=HOLD_DAYS,
        price_index=price_index, direction=1.0, condition="below",
    )

    sig_wasde = (
        build_fundamental_signal(
            wasde_surp, "surprise",
            threshold=WASDE_THRESH, hold_days=HOLD_DAYS,
            price_index=price_index, direction=1.0, condition="below",
        )
        if wasde_loaded else pd.Series(0.0, index=price_index)
    )

    # Combined: long when EITHER feature signals (union of drought + WASDE downgrade)
    sig_combined = (sig_weather.clip(0, 1) + sig_wasde.clip(0, 1)).clip(0, 1)

    # ── 5. Backtest + Validation ─────────────────────────────────────────────
    print("  [5] Backtest + Validierungsbatterie …\n")
    results = {}

    features_to_run = [("H-SB-01", sig_weather, "Wetter (Dürre-Signal)")]
    if wasde_loaded:
        features_to_run.append(("H-SB-03", sig_wasde, "WASDE Surprise"))
    if any_passes:
        features_to_run.append(("Combined", sig_combined, "Kombiniert (Wetter ∪ WASDE)"))

    for key, sig, label in features_to_run:
        n_active = int((sig > 0).sum())
        if n_active < 10:
            print(f"    {label}: nur {n_active} aktive Tage — überspringe.")
            continue

        R = evaluate_with_split(prices, sig, SPLIT_YEAR, n_trials=N_LOCAL)
        results[key] = {"label": label, **R}

        ts = R["e"]["trades"]
        m  = R["e"]["metrics"]
        print(
            f"  ── {label} ──\n"
            f"    Gesamt: Sharpe {m['sharpe']:.2f}  CAGR {m['cagr']*100:.1f}%  "
            f"MaxDD {m['max_drawdown']*100:.1f}%  Exposure {R['e']['exposure']:.1%}\n"
            f"    Trades: n={ts['n_trades']}  Win {ts['win_rate']:.0%}  "
            f"Exp {ts['expectancy']*100:+.2f}%  Median {ts['median_return']*100:+.2f}%\n"
            f"    IS:  Sharpe {R['e_is']['metrics']['sharpe']:.2f}  "
            f"Exp {R['e_is']['trades']['expectancy']*100:+.2f}%\n"
            f"    OOS: Sharpe {R['e_oos']['metrics']['sharpe']:.2f}  "
            f"Exp {R['e_oos']['trades']['expectancy']*100:+.2f}%\n"
            f"    Perm-p={R['perm']['p_value']:.3f}  "
            f"Boot-CI=[{R['boot']['ci_low']:.2f}, {R['boot']['ci_high']:.2f}]  "
            f"t-p={R['tt']['p_value']:.3f}  DSR-PSR={R['e']['psr']:.3f}\n"
        )

    if not results:
        print("  Keine Signale mit ausreichenden Trades. Abbruch.")
        return

    # ── 6. Plots ─────────────────────────────────────────────────────────────
    print("  [6] Plots …")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    # Feature overview: weather anomaly time series
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=False)
    ax = axes[0]
    anom_series = weather_anom_gp["precipitation_sum_anomaly"].dropna()
    colors = ["#e63946" if v < WEATHER_THRESH else "#2a9d8f" for v in anom_series]
    ax.bar(anom_series.index, anom_series.values, color=colors, width=25, alpha=0.85)
    ax.axhline(WEATHER_THRESH, color="#e63946", ls="--", lw=1.2, label=f"Threshold {WEATHER_THRESH}σ")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_ylabel("z-Score Niederschlag")
    ax.set_title("São Paulo Zuckerrohr-Gürtel — Niederschlag-Anomalie (Wachstumsphase Okt–Mär)")
    ax.legend(fontsize=8)

    # Signal overlay on price
    ax2 = axes[1]
    close = prices["Close"]
    ax2.plot(close.index, close.values, color="#264653", lw=0.8, label="SB=F Close")
    drought_dates = anom_series[anom_series < WEATHER_THRESH].index
    for rd in drought_dates:
        ax2.axvspan(rd, rd + pd.offsets.MonthBegin(1), color="#e63946", alpha=0.2)
    ax2.set_ylabel("Preis (¢/lb)")
    ax2.set_title("SB=F Preis mit Dürre-Signalperioden (rot)")
    ax2.legend(fontsize=8)

    # Monthly anomaly distribution
    ax3 = axes[2]
    ax3.hist(anom_series.values, bins=30, color="#2a9d8f", alpha=0.8, edgecolor="white")
    ax3.axvline(WEATHER_THRESH, color="#e63946", ls="--", lw=1.5,
                label=f"Threshold {WEATHER_THRESH}σ")
    ax3.set_xlabel("z-Score"); ax3.set_ylabel("Häufigkeit")
    ax3.set_title("Verteilung der monatl. Niederschlag-Anomalie (São Paulo, Wachstumsphase)")
    ax3.legend(fontsize=8)

    plt.tight_layout()
    caption = (
        "ERA5-Niederschlag (Open-Meteo) für den Zuckerrohr-Gürtel São Paulo (lat=-22°, lon=-47°). "
        "Monatliche z-Scores gegen eine rollierend-vergangenheitsbasierte 20-Jahres-Klimatologie "
        "(PIT-korrekt, kein Zukunftsdaten-Leck). Rote Balken = Dürre unter -1.5σ (vorregistrierte "
        "Schwelle H-SB-01). Signalperioden rot unterlegt auf dem SB-Preisverlauf."
    )
    plotting.savefig(fig, PLOTS / "weather_feature_overview.png")
    plt.close(fig)

    # Equity curves for all tested signals
    for key, R in results.items():
        label = R["label"]
        eq = R["e"]["res"]["equity"]
        bh = R["e"]["res"]["buy_hold"]

        fig2 = plotting.plot_equity(
            eq, benchmark=bh,
            title=f"0042 SB Fundamental — {label} vs. Buy & Hold",
            strategy_label=label, benchmark_label="SB=F Buy & Hold",
            caption=(
                f"SB=F, {label}. Hold={HOLD_DAYS} Handelstage nach Signal-Release. "
                f"Kosten: IBKR_SOFTS (4 bps/Seite). Perm-p={R['perm']['p_value']:.3f}. "
                f"IS/OOS-Split: {SPLIT_YEAR}."
            ),
        )
        plotting.savefig(fig2, PLOTS / f"equity_{key.lower().replace(' ', '_')}.png")
        plt.close(fig2)

    # IC summary bar chart
    fig3, axes3 = plt.subplots(1, len(scorecards), figsize=(5 * len(scorecards) + 1, 5))
    if len(scorecards) == 1:
        axes3 = [axes3]

    colors_bar = {"5": "#264653", "22": "#2a9d8f", "66": "#e9c46a"}
    for ax_i, (sc_name, sc) in zip(axes3, scorecards.items()):
        decay = sc["ic_decay"]
        horizons = decay.index.tolist()
        ics = decay["ic"].values
        ps  = [sc["permutation"].get(h, {}).get("p_value", 1.0) for h in horizons]
        xpos = np.arange(len(horizons))
        bars = ax_i.bar(xpos, ics, color=[colors_bar.get(str(h), "#aaa") for h in horizons],
                         alpha=0.85)
        ax_i.axhline(0, color="black", lw=0.7)
        ax_i.set_xticks(xpos)
        ax_i.set_xticklabels([f"{h}d" for h in horizons])
        ax_i.set_ylabel("Spearman IC")
        ax_i.set_title(sc_name, fontsize=9)
        for bar, p in zip(bars, ps):
            ax_i.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                      f"p={p:.2f}", ha="center", va="bottom", fontsize=8)

    fig3.suptitle("0042 SB — IC-Decay über Horizonte (5/22/66 Tage)", fontsize=11, fontweight="bold")
    caption3 = ("Spearman Rank-IC zwischen fundamentalem Feature (drought/WASDE) und Forward-Return "
                "bei 3 Horizonten. p-Werte: Permutationstest (500 Läufe). Positive IC = Feature "
                "sagt Rendite in der richtigen Richtung vorher.")
    plotting._add_caption(fig3, caption3)
    plt.tight_layout()
    plotting.savefig(fig3, PLOTS / "ic_decay_summary.png")
    plt.close(fig3)

    # ── 7. Persist ───────────────────────────────────────────────────────────
    print("  [7] Ergebnisse speichern …")

    def _ic_summary(sc: dict) -> dict:
        decay = sc["ic_decay"]
        return {
            str(h): {
                "ic":      float(decay.loc[h, "ic"]) if h in decay.index else None,
                "p_value": sc["permutation"].get(h, {}).get("p_value"),
                "n_obs":   sc["permutation"].get(h, {}).get("n_obs"),
            }
            for h in IC_HORIZONS
        }

    def _eval_summary(R: dict) -> dict:
        ts = R["e"]["trades"]
        m  = R["e"]["metrics"]
        return {
            "sharpe":          m["sharpe"],
            "cagr":            m["cagr"],
            "max_drawdown":    m["max_drawdown"],
            "n_trades":        ts["n_trades"],
            "win_rate":        ts["win_rate"],
            "expectancy_pct":  ts["expectancy"] * 100,
            "median_ret_pct":  ts["median_return"] * 100,
            "exposure":        R["e"]["exposure"],
            "sharpe_is":       R["e_is"]["metrics"]["sharpe"],
            "expectancy_is":   R["e_is"]["trades"]["expectancy"] * 100,
            "sharpe_oos":      R["e_oos"]["metrics"]["sharpe"],
            "expectancy_oos":  R["e_oos"]["trades"]["expectancy"] * 100,
            "perm_p":          R["perm"]["p_value"],
            "boot_ci":         [R["boot"]["ci_low"], R["boot"]["ci_high"]],
            "t_p":             R["tt"]["p_value"],
            "dsr_psr":         R["e"]["psr"],
        }

    ic_summaries = {name: _ic_summary(sc) for name, sc in scorecards.items()}
    backtest_summaries = {k: {"label": R["label"], **_eval_summary(R)}
                          for k, R in results.items()}

    summary = {
        "strategy":       "0042_sugar_sb_fundamental",
        "hypotheses":     ["H-SB-01", "H-SB-03"],
        "ticker":         TICKER,
        "split_year":     SPLIT_YEAR,
        "hold_days":      HOLD_DAYS,
        "weather_thresh": WEATHER_THRESH,
        "wasde_thresh":   WASDE_THRESH,
        "n_registered":   N_REGISTERED,
        "n_local_tests":  N_LOCAL,
        "cost_model":     "IBKR_SOFTS (4 bps/Seite = 8 bps RT)",
        "ic_screen":      ic_summaries,
        "backtests":      backtest_summaries,
        "wasde_loaded":   wasde_loaded,
    }

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    # Save trades for each signal
    for key, R in results.items():
        trades_df = R["e"]["res"]["trades"]
        if not trades_df.empty:
            trades_df.to_csv(RESULTS / f"trades_{key.lower()}.csv")

    print(f"\n  Ergebnisse gespeichert → {RESULTS}\n")
    print("  ── Zusammenfassung ──────────────────────────────────────────────")
    for key, R in results.items():
        ts = R["e"]["trades"]
        p  = R["perm"]["p_value"]
        verdict = (
            "✓ KANDIDAT" if p < 0.05 and ts["expectancy"] > 0 and ts["median_return"] > 0
            else "⚠ SCHWACH" if p < 0.10
            else "✗ ABGELEHNT"
        )
        print(f"    {R['label']:30s} perm-p={p:.3f}  exp={ts['expectancy']*100:+.2f}%  {verdict}")

    print()


def _save_ic_only(
    scorecards: dict,
    wasde_loaded: bool,
    weather_anom_gp: pd.DataFrame | None = None,
    prices: pd.DataFrame | None = None,
) -> None:
    """Persist IC results and diagnostic plots even when backtest is skipped."""
    import matplotlib.pyplot as plt
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    ic_data = {}
    for name, sc in scorecards.items():
        decay = sc["ic_decay"]
        ic_data[name] = {
            str(h): {
                "ic":      float(decay.loc[h, "ic"]) if h in decay.index else None,
                "p_value": sc["permutation"].get(h, {}).get("p_value"),
                "n_obs":   sc["permutation"].get(h, {}).get("n_obs"),
            }
            for h in IC_HORIZONS
        }

    # IC-Decay Plot
    if scorecards:
        fig, axes = plt.subplots(1, len(scorecards), figsize=(5 * len(scorecards) + 1, 5))
        if len(scorecards) == 1:
            axes = [axes]
        colors_bar = {5: "#264653", 22: "#2a9d8f", 66: "#e9c46a"}
        for ax_i, (sc_name, sc) in zip(axes, scorecards.items()):
            decay = sc["ic_decay"]
            horizons = decay.index.tolist()
            ics = decay["ic"].values
            ps  = [sc["permutation"].get(h, {}).get("p_value", 1.0) for h in horizons]
            xpos = np.arange(len(horizons))
            bars = ax_i.bar(xpos, ics,
                            color=[colors_bar.get(h, "#aaa") for h in horizons], alpha=0.85)
            ax_i.axhline(0, color="black", lw=0.7)
            ax_i.set_xticks(xpos); ax_i.set_xticklabels([f"{h}d" for h in horizons])
            ax_i.set_ylabel("Spearman IC"); ax_i.set_title(sc_name, fontsize=9)
            for bar, p in zip(bars, ps):
                ax_i.text(bar.get_x() + bar.get_width() / 2,
                          bar.get_height() + 0.002,
                          f"p={p:.2f}", ha="center", va="bottom", fontsize=9)
        fig.suptitle("0042 SB — IC-Decay (Rejected: IC ≈ 0)", fontsize=11, fontweight="bold")
        plotting._add_caption(
            fig,
            "IC nahe Null über alle Horizonte. Permutation-p >> 0.05. "
            "Kein Backtest ausgeführt — korrekte Ablehnung auf IC-Ebene."
        )
        plt.tight_layout()
        plotting.savefig(fig, PLOTS / "ic_decay_rejected.png")
        plt.close(fig)

    # Weather anomaly time series plot
    if weather_anom_gp is not None and prices is not None:
        fig2, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=False)
        anom_series = weather_anom_gp["precipitation_sum_anomaly"].dropna()
        colors = ["#e63946" if v < WEATHER_THRESH else "#2a9d8f" for v in anom_series]
        ax1.bar(anom_series.index, anom_series.values, color=colors, width=25, alpha=0.85)
        ax1.axhline(WEATHER_THRESH, color="#e63946", ls="--", lw=1.2,
                    label=f"Threshold {WEATHER_THRESH}σ")
        ax1.axhline(0, color="black", lw=0.6)
        ax1.set_ylabel("z-Score"); ax1.legend(fontsize=8)
        ax1.set_title("São Paulo Niederschlag-Anomalie (Wachstumsphase Okt–Mär)")

        close = prices["Close"]
        ax2.plot(close.index, close.values, color="#264653", lw=0.8)
        ax2.set_ylabel("SB=F (¢/lb)")
        ax2.set_title("SB=F Preis — zur Referenz (Dürre-Perioden rot)")
        for rd in anom_series[anom_series < WEATHER_THRESH].index:
            ax2.axvspan(rd, rd + pd.offsets.MonthBegin(1), color="#e63946", alpha=0.15)
        plt.tight_layout()
        plotting.savefig(fig2, PLOTS / "weather_feature_overview.png")
        plt.close(fig2)

    summary = {
        "strategy":     "0042_sugar_sb_fundamental",
        "status":       "IC_SCREEN_FAILED — no backtest run",
        "wasde_loaded": wasde_loaded,
        "ic_screen":    ic_data,
        "verdict":      "REJECTED — IC ≈ 0 at all horizons for H-SB-01",
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\n  IC-only Ergebnisse gespeichert → {RESULTS}\n")


if __name__ == "__main__":
    main()
