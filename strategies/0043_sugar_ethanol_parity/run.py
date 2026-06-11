"""Strategy 0043 — Sugar #11 (SB) Fundamental: Ethanol-Parity (H-SB-02)

Hypothesis (from fundamentals/HYPOTHESES.md, H-SB-02):
    When ethanol is expensive relative to sugar, Brazilian mills divert cane
    into ethanol production → sugar supply falls over the crush season →
    sugar price rises over 1–3 months.

Data substitution (documented honestly):
    The EIA Weekly Ethanol Price API — the intended source — is geo-blocked in
    this environment (HTTP 403, same wall as USDA in 0042). We substitute the
    ECONOMIC DRIVER of ethanol attractiveness: the **gasoline price**. In Brazil
    hydrous ethanol competes directly with gasoline at the pump (parity ~70% of
    the gasoline price), so the gasoline-to-sugar price ratio IS the mill's
    sugar-vs-ethanol decision variable. This is a PROXY, marked as such.

Features (all free + reachable via yfinance):
    PRIMARY:    RBOB gasoline / sugar parity ratio z-score (RB=F, 252d window)
    CROSS-CHECK: Crude oil / sugar parity z-score (CL=F, longer history,
                 negative-print guarded per lesson 0005)
    PLACEBO:    RBOB / gold parity z-score → predict GOLD returns. Gold has NO
                ethanol-diversion mechanism; if the feature "predicts" gold just
                as well, the sugar result is generic energy/inflation beta, not
                the cane-diversion mechanism.

Prediction: high parity ratio z (energy expensive vs sugar) → long sugar,
            strongest at the 66-day (3M) horizon (slow crush-season response).

Pipeline (strictly sequential, pre-registered, no post-hoc tuning):
    1. IC screen (monthly-sampled feature, Spearman IC + permutation, 3 horizons)
    2. Full backtest only if primary feature clears IC perm-p < 0.10 at 66d
    3. Validation battery: permutation, bootstrap CI, IS/OOS split, DSR
    4. Robustness: crude cross-check + gold placebo (frozen, no refit)

Multiple-testing budget: N_local = 3 (primary feature × 3 horizons), against
N_registered = 14 in HYPOTHESES.md (this is hypothesis #2).

Run:
    .venv/Scripts/python.exe strategies/0043_sugar_ethanol_parity/run.py
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
from quantlab.features import ethanol_premium          # noqa: E402
from quantlab.ic import score_feature, print_scorecard  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS   = RESULTS / "plots"

# ── Pre-registered parameters (from HYPOTHESES.md — do NOT tune) ─────────────
SB_TICKER     = "SB=F"
SB_NAME       = "Zucker #11 (Sugar-Future)"
ENERGY_PRIMARY   = ("RB=F", "RBOB-Benzin")
ENERGY_CROSS     = ("CL=F", "Rohöl (WTI)")
PLACEBO_ASSET    = ("GC=F", "Gold")
SAMPLE_START  = "2007-01-01"   # clean overlapping RBOB era
SPLIT_YEAR    = 2017           # IS 2007–2016, OOS 2017–2026
HOLD_DAYS     = 66             # 3M — slow crush-season supply response (pre-registered)
IC_HORIZONS   = (5, 22, 66)
RATIO_WINDOW  = 252            # 1Y rolling z-score window (pre-registered)
PARITY_THRESH = 1.0            # z > +1.0 = ethanol attractive → long sugar (pre-reg.)
COST_MODEL    = IBKR_SOFTS     # 8 bps RT, 4 bps/side
N_REGISTERED  = 14
N_LOCAL       = 3              # primary feature × 3 horizons (for DSR)
N_PERM        = 2000


# ── Helpers ────────────────────────────────────────────────────────────────────

def guard_prices(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Apply data-quality guards (lessons 0005 + 0025); clip non-positive closes.

    For energy futures with a known negative print (CL=F 2020-04-20), the
    non-positive close is set to NaN and forward-filled so the parity ratio
    is not corrupted across the zero crossing.
    """
    df = prices.copy()
    neg = int((df["Close"] <= 0).sum())
    if neg > 0:
        print(f"    ⚠  {ticker}: {neg} non-positive close(s) (lesson 0005) — "
              f"clipped to NaN + ffill for ratio integrity.")
        df.loc[df["Close"] <= 0, "Close"] = np.nan
        df["Close"] = df["Close"].ffill()
    if int(df["Close"].groupby(df.index.year).nunique().min()) < 50:
        raise SystemExit(f"{ticker}: frozen feed (lesson 0025).")
    return df


def monthly_feature_df(daily_z: pd.Series, col: str = "ratio_z") -> pd.DataFrame:
    """Resample a daily z-score feature to month-end for a clean IC screen.

    Daily overlapping forward returns inflate the IC's effective sample. Sampling
    the feature at month-ends gives near-non-overlapping observations for the 22d
    horizon (and only ~3x overlap at 66d), consistent with the 0042 approach.

    Returns a feature_df indexed by ref_date (month-end) with a release_date
    column (= next day; the value is a same-day market price, known at close).
    """
    m = daily_z.resample("ME").last().dropna()
    df = pd.DataFrame({col: m})
    df.index.name = "ref_date"
    df["release_date"] = df.index + pd.Timedelta(days=1)
    return df


def build_parity_signal(
    daily_z: pd.Series,
    threshold: float,
    hold_days: int,
    price_index: pd.DatetimeIndex,
    direction: float = 1.0,
) -> pd.Series:
    """Long when parity z-score crosses above threshold; hold ``hold_days``.

    The signal is decided at each day's close from data known that day; the
    backtest engine shifts it by 1 day (no look-ahead). Overlapping triggers
    (a sustained high-parity regime) keep the position on.
    """
    z = daily_z.reindex(price_index).ffill()
    signal = pd.Series(0.0, index=price_index)
    above = z > threshold
    entry_positions = np.where(above.values)[0]
    for i in entry_positions:
        end = min(i + hold_days, len(price_index) - 1)
        signal.iloc[i:end + 1] = direction
    return signal


def evaluate(prices: pd.DataFrame, signal: pd.Series, n_trials: int = 1) -> dict:
    res  = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    m    = compute_metrics(rets)
    ts   = trade_stats(res["trades"])
    sp   = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) > 0 else 0.0
    dsr  = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                 n_trials=max(1, n_trials), returns=rets)
    return {"metrics": m, "trades": ts, "exposure": float(res["position"].abs().mean()),
            "psr": dsr["psr_deflated"], "returns": rets, "res": res}


def evaluate_with_split(prices, signal, split_year, n_trials=1) -> dict:
    split = f"{split_year}-01-01"
    e     = evaluate(prices, signal, n_trials=n_trials)
    e_is  = evaluate(prices.loc[:split], signal.reindex(prices.loc[:split].index, fill_value=0.0))
    e_oos = evaluate(prices.loc[split:], signal.reindex(prices.loc[split:].index, fill_value=0.0))
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=N_PERM)
    boot = bootstrap_ci(e["returns"], statistic="sharpe", n_boot=N_PERM)
    tt   = t_test_mean_return(e["returns"])
    bh   = compute_metrics(asset_ret)
    return {"e": e, "e_is": e_is, "e_oos": e_oos, "perm": perm,
            "boot": boot, "tt": tt, "bh": bh, "split": split}


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'='*66}")
    print(f"  Strategy 0043 — Sugar SB Fundamental: Ethanol-Parität (H-SB-02)")
    print(f"  Proxy: Benzin/Zucker-Parität (EIA-Ethanol geoblockt)")
    print(f"  IS 2007–{SPLIT_YEAR-1}  OOS {SPLIT_YEAR}–heute  |  hold={HOLD_DAYS}d  z>{PARITY_THRESH}")
    print(f"{'='*66}\n")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # ── 0. Load + guard ──────────────────────────────────────────────────────
    print("  [0] Preise laden + Daten-Guards …")
    sb = guard_prices(get_prices(SB_TICKER, start=SAMPLE_START), SB_TICKER)
    rb = guard_prices(get_prices(ENERGY_PRIMARY[0], start=SAMPLE_START), ENERGY_PRIMARY[0])
    cl = guard_prices(get_prices(ENERGY_CROSS[0],   start="2000-01-01"), ENERGY_CROSS[0])
    gc = guard_prices(get_prices(PLACEBO_ASSET[0],  start=SAMPLE_START), PLACEBO_ASSET[0])
    print(f"    SB {sb.index.year.min()}–{sb.index.year.max()} | "
          f"RB {rb.index.year.min()}–{rb.index.year.max()} | "
          f"CL {cl.index.year.min()}–{cl.index.year.max()} | "
          f"GC {gc.index.year.min()}–{gc.index.year.max()}\n")

    # ── 1. Build parity features ─────────────────────────────────────────────
    print("  [1] Paritäts-Features bauen (Ratio z-Score, 252d) …")
    # PRIMARY: RBOB / sugar
    prem_rb = ethanol_premium(rb["Close"], sb["Close"], window=RATIO_WINDOW)
    z_rb    = prem_rb["ratio_z"]
    # CROSS-CHECK: crude / sugar (longer history)
    prem_cl = ethanol_premium(cl["Close"], sb["Close"], window=RATIO_WINDOW)
    z_cl    = prem_cl["ratio_z"]
    # PLACEBO: RBOB / gold (predict gold)
    prem_gc = ethanol_premium(rb["Close"], gc["Close"], window=RATIO_WINDOW)
    z_gc    = prem_gc["ratio_z"]
    print(f"    RBOB/Zucker: {len(z_rb)} Tage | Crude/Zucker: {len(z_cl)} | "
          f"RBOB/Gold (Placebo): {len(z_gc)}\n")

    # ── 2. IC screen (primary) ───────────────────────────────────────────────
    print("  [2] IC-Screen (monatlich gesampelt, Perm 500) …\n")
    feat_rb = monthly_feature_df(z_rb, "ratio_z")
    sc_rb   = score_feature(feat_rb, sb, "ratio_z", horizons=IC_HORIZONS, n_perm=500)
    print_scorecard(sc_rb)

    p_target = sc_rb["permutation"].get(HOLD_DAYS, {}).get("p_value", 1.0)
    passes = p_target < 0.10
    print(f"\n  IC-Screen (RBOB/Zucker) bei {HOLD_DAYS}d: "
          f"{'PASS ✓' if passes else 'FAIL ✗'} (perm-p={p_target:.3f})")

    scorecards = {"H-SB-02 RBOB/Zucker": sc_rb}

    if not passes:
        # Still run the cross-check + placebo IC for the record, then stop.
        print("\n  Cross-Check + Placebo IC (zur Dokumentation, kein Backtest):\n")
        feat_cl = monthly_feature_df(z_cl, "ratio_z")
        sc_cl   = score_feature(feat_cl, sb, "ratio_z", horizons=IC_HORIZONS, n_perm=500)
        print_scorecard(sc_cl)
        feat_gc = monthly_feature_df(z_gc, "ratio_z")
        sc_gc   = score_feature(feat_gc, gc, "ratio_z", horizons=IC_HORIZONS, n_perm=500)
        print_scorecard(sc_gc)
        scorecards["Crude/Zucker (Cross)"] = sc_cl
        scorecards["RBOB/Gold (Placebo)"]  = sc_gc

        placebo_p = sc_gc["permutation"].get(HOLD_DAYS, {}).get("p_value", 1.0)
        print(
            "\n  ⛔  Primär-Feature übersteht den IC-Screen bei p<0.10 NICHT. "
            "Kein Backtest — korrekte Ablehnung auf IC-Ebene.\n"
            "  Verdict: H-SB-02 ABGELEHNT. Kein Tuning (würde Multiple-Testing-N erhöhen).\n"
            f"  Methodik-Hinweis: Gold-Placebo bei {HOLD_DAYS}d perm-p={placebo_p:.3f} "
            f"({'SIGNIFIKANT' if placebo_p < 0.05 else 'sauber'}) — "
            "der Placebo erfasst generische Energie-Makro-Effekte, das Zucker-Ziel nicht."
        )
        print("\n  [Plots] …")
        _make_plots(scorecards, {}, z_rb, sb)
        _save_results(scorecards, backtests={}, passed=False,
                      extra={"z_rb": z_rb, "sb": sb})
        return

    # ── 3. Full backtest (primary) ───────────────────────────────────────────
    print("\n  → IC-Screen bestanden. Vollständiger Backtest …\n")
    sig_rb = build_parity_signal(z_rb, PARITY_THRESH, HOLD_DAYS, sb.index)
    R_rb   = evaluate_with_split(sb, sig_rb, SPLIT_YEAR, n_trials=N_LOCAL)

    # ── 4. Robustness: crude cross-check + gold placebo (frozen rule) ────────
    print("  [4] Robustheit: Crude-Cross-Check + Gold-Placebo (eingefroren) …\n")
    sig_cl = build_parity_signal(z_cl, PARITY_THRESH, HOLD_DAYS, sb.index)
    R_cl   = evaluate_with_split(sb, sig_cl, SPLIT_YEAR)
    sig_gc = build_parity_signal(z_gc, PARITY_THRESH, HOLD_DAYS, gc.index)
    R_gc   = evaluate_with_split(gc, sig_gc, SPLIT_YEAR)

    backtests = {
        "RBOB_sugar":  {"label": "RBOB/Zucker (primär)",   **R_rb},
        "crude_sugar": {"label": "Crude/Zucker (Cross)",   **R_cl},
        "rbob_gold":   {"label": "RBOB/Gold (Placebo)",    **R_gc},
    }

    def report_line(tag, R):
        ts, m = R["e"]["trades"], R["e"]["metrics"]
        print(
            f"  ── {R['label']} ──\n"
            f"    Sharpe {m['sharpe']:.2f}  CAGR {m['cagr']*100:.1f}%  MaxDD {m['max_drawdown']*100:.1f}%  "
            f"Exp {R['e']['exposure']:.0%}\n"
            f"    Trades n={ts['n_trades']}  Win {ts['win_rate']:.0%}  "
            f"Exp/Trade {ts['expectancy']*100:+.2f}%  Median {ts['median_return']*100:+.2f}%\n"
            f"    IS Sharpe {R['e_is']['metrics']['sharpe']:.2f} | OOS Sharpe {R['e_oos']['metrics']['sharpe']:.2f}\n"
            f"    Perm-p={R['perm']['p_value']:.3f}  Boot-CI[{R['boot']['ci_low']:.2f},{R['boot']['ci_high']:.2f}]  "
            f"DSR-PSR={R['e']['psr']:.3f}\n"
        )

    for tag, R in backtests.items():
        report_line(tag, R)

    # ── 5. Plots ─────────────────────────────────────────────────────────────
    print("  [5] Plots …")
    _make_plots(scorecards, backtests, z_rb, sb)

    # ── 6. Persist ───────────────────────────────────────────────────────────
    print("  [6] Speichern …")
    _save_results(scorecards, backtests, passed=True, extra={"z_rb": z_rb, "sb": sb})

    # ── 7. Verdict ───────────────────────────────────────────────────────────
    print("\n  ── Verdict ───────────────────────────────────────────────────────")
    rb_p   = R_rb["perm"]["p_value"]
    rb_exp = R_rb["e"]["trades"]["expectancy"]
    rb_med = R_rb["e"]["trades"]["median_return"]
    gc_p   = R_gc["perm"]["p_value"]
    placebo_clean = gc_p >= 0.10   # placebo should NOT be significant
    is_oos_ok = (R_rb["e_oos"]["metrics"]["sharpe"] >=
                 0.5 * R_rb["e_is"]["metrics"]["sharpe"])

    if rb_p < 0.05 and rb_exp > 0 and rb_med > 0 and placebo_clean and is_oos_ok:
        verdict = "✓ KANDIDAT — echter Edge, Placebo sauber, OOS hält"
    elif rb_p < 0.05 and not placebo_clean:
        verdict = "⚠ VERDÄCHTIG — signifikant, aber Gold-Placebo auch → generische Energie-Beta"
    elif rb_p < 0.10:
        verdict = "⚠ SCHWACH — grenzwertig, mehr Daten/Forward-Test nötig"
    else:
        verdict = "✗ ABGELEHNT — kein signifikanter Netto-Edge"
    print(f"    RBOB/Zucker perm-p={rb_p:.3f}  exp={rb_exp*100:+.2f}%  "
          f"median={rb_med*100:+.2f}%")
    print(f"    Gold-Placebo perm-p={gc_p:.3f} ({'sauber' if placebo_clean else 'KONTAMINIERT'})")
    print(f"    {verdict}\n")


# ── Persistence + plotting ─────────────────────────────────────────────────────

def _ic_summary(sc: dict) -> dict:
    decay = sc["ic_decay"]
    return {str(h): {"ic": float(decay.loc[h, "ic"]) if h in decay.index else None,
                     "p_value": sc["permutation"].get(h, {}).get("p_value"),
                     "n_obs": sc["permutation"].get(h, {}).get("n_obs")}
            for h in IC_HORIZONS}


def _eval_summary(R: dict) -> dict:
    ts, m = R["e"]["trades"], R["e"]["metrics"]
    return {"sharpe": m["sharpe"], "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "n_trades": ts["n_trades"], "win_rate": ts["win_rate"],
            "expectancy_pct": ts["expectancy"] * 100, "median_ret_pct": ts["median_return"] * 100,
            "exposure": R["e"]["exposure"], "sharpe_is": R["e_is"]["metrics"]["sharpe"],
            "sharpe_oos": R["e_oos"]["metrics"]["sharpe"], "perm_p": R["perm"]["p_value"],
            "boot_ci": [R["boot"]["ci_low"], R["boot"]["ci_high"]],
            "t_p": R["tt"]["p_value"], "dsr_psr": R["e"]["psr"]}


def _save_results(scorecards, backtests, passed, extra=None) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {
        "strategy": "0043_sugar_ethanol_parity",
        "hypothesis": "H-SB-02 (Ethanol-Parität, Energie-Proxy)",
        "status": "BACKTESTED" if passed else "IC_SCREEN_FAILED",
        "data_note": "EIA ethanol geo-blocked → gasoline/crude proxy (yfinance)",
        "primary_feature": "RBOB/sugar parity ratio z-score (252d)",
        "sample_start": SAMPLE_START, "split_year": SPLIT_YEAR,
        "hold_days": HOLD_DAYS, "parity_thresh": PARITY_THRESH,
        "ratio_window": RATIO_WINDOW, "cost_model": "IBKR_SOFTS (4 bps/side)",
        "n_registered": N_REGISTERED, "n_local_tests": N_LOCAL,
        "ic_screen": {name: _ic_summary(sc) for name, sc in scorecards.items()},
        "backtests": {k: {"label": R["label"], **_eval_summary(R)}
                      for k, R in backtests.items()},
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    for k, R in backtests.items():
        td = R["e"]["res"]["trades"]
        if not td.empty:
            td.to_csv(RESULTS / f"trades_{k}.csv")
    print(f"    → {RESULTS}")


def _make_plots(scorecards, backtests, z_rb, sb) -> None:
    import matplotlib.pyplot as plt

    # Feature overview: parity z-score + sugar price with signal regions
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))
    z_plot = z_rb.dropna()
    ax1.plot(z_plot.index, z_plot.values, color="#264653", lw=0.7)
    ax1.axhline(PARITY_THRESH, color="#e63946", ls="--", lw=1.2,
                label=f"Threshold z>{PARITY_THRESH}")
    ax1.axhline(0, color="black", lw=0.5)
    ax1.fill_between(z_plot.index, PARITY_THRESH, z_plot.values,
                     where=z_plot.values > PARITY_THRESH, color="#e63946", alpha=0.3)
    ax1.set_ylabel("RBOB/Zucker Ratio z-Score"); ax1.legend(fontsize=8)
    ax1.set_title("Benzin-zu-Zucker Paritäts-z-Score (hoch = Ethanol attraktiv → Mühlen diversifizieren)")

    close = sb["Close"]
    ax2.plot(close.index, close.values, color="#2a9d8f", lw=0.8)
    ax2.set_ylabel("SB=F (¢/lb)"); ax2.set_title("SB=F Preis (Signal-Perioden rot)")
    z_aligned = z_rb.reindex(sb.index).ffill()
    for i in np.where((z_aligned > PARITY_THRESH).values)[0]:
        ax2.axvspan(sb.index[i], sb.index[min(i + 1, len(sb.index) - 1)],
                    color="#e63946", alpha=0.05)
    plt.tight_layout()
    plotting._add_caption(fig,
        "RBOB-Benzin/Zucker-Paritäts-Ratio (252d rollierender z-Score, PIT-korrekt). Proxy für "
        "die brasilianische Mühlen-Entscheidung Zucker-vs-Ethanol (EIA-Ethanol geoblockt). "
        "Rot: z > +1.0 = Ethanol attraktiv → Hypothese: Zucker-Angebot sinkt → Preis steigt.")
    plotting.savefig(fig, PLOTS / "parity_feature_overview.png")
    plt.close(fig)

    # IC decay summary across all scorecards
    if scorecards:
        fig2, axes = plt.subplots(1, len(scorecards), figsize=(5 * len(scorecards) + 1, 5))
        if len(scorecards) == 1:
            axes = [axes]
        cmap = {5: "#264653", 22: "#2a9d8f", 66: "#e9c46a"}
        for ax, (name, sc) in zip(axes, scorecards.items()):
            decay = sc["ic_decay"]; hs = decay.index.tolist()
            ics = decay["ic"].values
            ps = [sc["permutation"].get(h, {}).get("p_value", 1.0) for h in hs]
            xp = np.arange(len(hs))
            bars = ax.bar(xp, ics, color=[cmap.get(h, "#aaa") for h in hs], alpha=0.85)
            ax.axhline(0, color="black", lw=0.7); ax.set_xticks(xp)
            ax.set_xticklabels([f"{h}d" for h in hs]); ax.set_ylabel("Spearman IC")
            ax.set_title(name, fontsize=9)
            for b, p in zip(bars, ps):
                ax.text(b.get_x() + b.get_width() / 2,
                        b.get_height() + (0.003 if b.get_height() >= 0 else -0.01),
                        f"p={p:.2f}", ha="center",
                        va="bottom" if b.get_height() >= 0 else "top", fontsize=8)
        fig2.suptitle("0043 SB Ethanol-Parität — IC-Decay über Horizonte", fontsize=11, fontweight="bold")
        plotting._add_caption(fig2,
            "Spearman Rank-IC Paritäts-z-Score → Forward-Return (5/22/66d), monatlich gesampelt. "
            "Placebo (RBOB/Gold) muss insignifikant bleiben, sonst ist der Effekt generische Energie-Beta.")
        plt.tight_layout()
        plotting.savefig(fig2, PLOTS / "ic_decay_summary.png")
        plt.close(fig2)

    # Equity curves
    for k, R in backtests.items():
        eq = R["e"]["res"]["equity"]; bh = R["e"]["res"]["buy_hold"]
        fig3 = plotting.plot_equity(
            eq, benchmark=bh,
            title=f"0043 — {R['label']} vs. Buy & Hold",
            strategy_label=R["label"], benchmark_label="Buy & Hold",
            caption=(f"Hold={HOLD_DAYS}d nach z>{PARITY_THRESH}. Kosten IBKR_SOFTS (4 bps/Seite). "
                     f"Perm-p={R['perm']['p_value']:.3f}. IS/OOS-Split {SPLIT_YEAR}."))
        plotting.savefig(fig3, PLOTS / f"equity_{k}.png")
        plt.close(fig3)


if __name__ == "__main__":
    main()
