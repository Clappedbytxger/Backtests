"""Strategy 0045 — Cotton (CT) Fundamental: NASS Crop-Condition Δ (H-CT-01)

Hypothesis (from fundamentals/HYPOTHESES.md, H-CT-01):
    Drought/heat in West Texas → USDA NASS weekly crop condition (good+excellent %)
    falls → yield estimate down → cotton price rises over 1W–1M. Position when the
    week-over-week deterioration is sharp (Δ < -5 percentage points, pre-registered).

First test of the REPORT-SURPRISE / PIT class with real USDA data:
    This is the class that is the only one that has ever worked in the catalog
    (corn-WASDE 0032: 78% of the edge on 6 report days). Crop condition is the
    higher-frequency cousin — a weekly, point-in-time observation. The question:
    does the *incremental* weekly condition change carry a tradeable surprise, or
    is this most-watched US ag report continuously priced in (efficient)?

Data (now reachable — see CLAUDE.md lesson 2026-06-07): USDA NASS QuickStats,
    free key in gitignored .nass.key, cached to Parquet. Cotton, Texas (FIPS 48,
    the largest US cotton state, ~40% of production, the West-Texas drought belt).

PIT-correctness:
    NASS Crop Progress releases Monday 16:00 ET; week_ending = preceding Sunday;
    release_date = Sunday + 1 (Monday). The engine shifts the signal +1 day, so the
    effective entry is the day after release — no look-ahead.
    Cross-season Δ (late-Nov → next April) is dropped (gap-to-prior > 14 days): only
    genuine within-season week-over-week changes count.

Tests (mirrors 0044): continuous IC screen → event study on the -5pp threshold →
    net-of-cost threshold backtest with the full validation battery.

Run:
    .venv/Scripts/python.exe strategies/0045_cotton_crop_condition/run.py
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
from quantlab.fundamental_data import get_nass_crop_condition  # noqa: E402
from quantlab.features import crop_condition_delta     # noqa: E402
from quantlab.ic import score_feature, print_scorecard  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS   = RESULTS / "plots"

# ── Pre-registered parameters (from HYPOTHESES.md — do NOT tune) ─────────────
CT_TICKER     = "CT=F"
CT_NAME       = "Baumwolle (Cotton-Future)"
NASS_COMMODITY = "COTTON"
NASS_STATE    = "48"            # Texas FIPS — largest US cotton state / West-Texas belt
NASS_REGION   = "Texas (FIPS 48)"
DELTA_THRESH  = -5.0           # percentage points WoW — pre-registered deterioration
HOLD_DAYS     = 22             # 1M horizon (pre-registered)
IC_HORIZONS   = (5, 10, 22)    # ~1W to ~1M (weekly feature)
MAX_GAP_DAYS  = 14             # drop cross-season Δ (keep consecutive reporting weeks)
SPLIT_YEAR    = 2013
COST_MODEL    = IBKR_SOFTS     # liquid soft, 8 bps RT
N_REGISTERED  = 14
N_LOCAL       = 3              # feature × 3 horizons
N_PERM        = 2000


def guard_prices(prices, ticker):
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{ticker}: non-positive close (lesson 0005).")
    if int(prices["Close"].groupby(prices.index.year).nunique().min()) < 50:
        raise SystemExit(f"{ticker}: frozen feed (lesson 0025).")
    return prices


def build_signal(events, hold_days, price_index):
    """Long for ``hold_days`` after each deterioration event's release_date."""
    signal = pd.Series(0.0, index=price_index)
    for rel in events["release_date"]:
        i = price_index.searchsorted(rel)
        if i >= len(price_index):
            continue
        end = min(i + hold_days, len(price_index) - 1)
        signal.iloc[i:end + 1] = 1.0
    return signal


def event_study(events, close, horizons=(5, 22)):
    def fwd(rel, d):
        idx = close.index[close.index >= rel]
        if len(idx) == 0:
            return np.nan
        p = close.index.get_loc(idx[0])
        if p + d >= len(close):
            return np.nan
        return close.iloc[p + d] / close.iloc[p] - 1.0
    rows = []
    for ts in events.index:
        rel = events.loc[ts, "release_date"]
        rows.append({"week_ending": ts.strftime("%Y-%m-%d"),
                     "delta_pp": float(events.loc[ts, "pct_good_excellent_delta"]),
                     **{f"ret_{h}d": fwd(rel, h) for h in horizons}})
    df = pd.DataFrame(rows)
    summ = {}
    for h in horizons:
        r = df[f"ret_{h}d"].dropna().values
        summ[h] = {"mean": float(np.mean(r)) if len(r) else np.nan,
                   "median": float(np.median(r)) if len(r) else np.nan,
                   "win_rate": float((r > 0).mean()) if len(r) else np.nan,
                   "n": int(len(r))}
    return {"table": df, "summary": summ}


def evaluate(prices, signal, n_trials=1):
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) > 0 else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                n_trials=max(1, n_trials), returns=rets)
    return {"metrics": compute_metrics(rets), "trades": trade_stats(res["trades"]),
            "exposure": float(res["position"].abs().mean()),
            "psr": dsr["psr_deflated"], "returns": rets, "res": res}


def main() -> None:
    print(f"\n{'='*66}")
    print(f"  Strategy 0045 — Cotton Crop-Condition Δ (H-CT-01)")
    print(f"  NASS {NASS_REGION}  |  long if WoW Δ(good+excellent) < {DELTA_THRESH}pp")
    print(f"  First REAL-DATA test of the report-surprise/PIT class (NASS live)")
    print(f"{'='*66}\n")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # ── 0. Load ──────────────────────────────────────────────────────────────
    print("  [0] Preise + NASS Crop-Condition laden …")
    ct = guard_prices(get_prices(CT_TICKER, start="2000-01-01"), CT_TICKER)
    close = ct["Close"]
    nass = get_nass_crop_condition(NASS_COMMODITY, NASS_STATE, 2000, 2025)

    # ── 1. Feature: within-season WoW deterioration ──────────────────────────
    print("  [1] Feature: WoW-Δ Good/Excellent (nur konsekutive Saison-Wochen) …")
    cc = crop_condition_delta(nass, "pct_good_excellent")
    gap = cc.index.to_series().diff().dt.days
    cc = cc[gap <= MAX_GAP_DAYS].copy()
    cc["deterioration"] = -cc["pct_good_excellent_delta"]   # worse crop = bullish signal
    n_weeks = len(cc)
    print(f"    {n_weeks} in-season Wochen-Deltas ({cc.index.year.min()}–{cc.index.year.max()})\n")

    # ── 2. Continuous IC screen ──────────────────────────────────────────────
    print("  [2] Kontinuierlicher IC-Screen …\n")
    sc = score_feature(cc, ct, "deterioration", horizons=IC_HORIZONS, n_perm=1000)
    print_scorecard(sc)
    p22 = sc["permutation"][22]["p_value"]
    ic22 = sc["ic_decay"].loc[22, "ic"]
    ic_passes = p22 < 0.10 and ic22 > 0
    print(f"\n  IC bei 22d: IC={ic22:+.3f}, perm-p={p22:.3f} → "
          f"{'PASS' if ic_passes else 'FAIL ✗'}")

    # ── 3. Event study on the -5pp threshold (pre-registered) ────────────────
    print(f"\n  [3] Event-Study: Forward-Returns nach Δ < {DELTA_THRESH}pp …\n")
    events = cc[cc["pct_good_excellent_delta"] < DELTA_THRESH].copy()
    es = event_study(events, close, horizons=(5, 22))
    for h, s in es["summary"].items():
        print(f"    {h:>2}d: mean={s['mean']*100:+.2f}%  median={s['median']*100:+.2f}%  "
              f"win={s['win_rate']:.0%}  n={s['n']}")
    n_events = len(events)
    median_22 = es["summary"][22]["median"]

    # ── 4. Net-of-cost threshold backtest ────────────────────────────────────
    print(f"\n  [4] Netto-Backtest (long {HOLD_DAYS}d nach jedem Event, n={n_events}) …\n")
    signal = build_signal(events, HOLD_DAYS, ct.index)
    e = evaluate(ct, signal, n_trials=N_LOCAL)
    asset_ret = close.pct_change().fillna(0.0)
    perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=N_PERM)
    boot = bootstrap_ci(e["returns"], statistic="sharpe", n_boot=N_PERM)
    tt = t_test_mean_return(e["returns"])
    ts, m = e["trades"], e["metrics"]
    trades_df = e["res"]["trades"]
    median_trade = float(trades_df["pnl"].median()) if not trades_df.empty else float("nan")
    print(f"    Sharpe {m['sharpe']:.2f}  CAGR {m['cagr']*100:.1f}%  MaxDD {m['max_drawdown']*100:.1f}%  "
          f"Exp {e['exposure']:.0%}")
    print(f"    Trades n={ts['n_trades']}  Win {ts['win_rate']:.0%}  "
          f"Exp/Trade {ts['expectancy']*100:+.2f}%  Median/Trade {median_trade*100:+.2f}%")
    print(f"    Perm-p={perm['p_value']:.3f}  Boot-CI[{boot['ci_low']:.2f},{boot['ci_high']:.2f}]  "
          f"t-p={tt['p_value']:.3f}  DSR-PSR={e['psr']:.3f}")

    # ── 5. Plots ─────────────────────────────────────────────────────────────
    print("\n  [5] Plots …")
    _make_plots(cc, events, close, es, sc)

    # ── 6. Persist + verdict ─────────────────────────────────────────────────
    print("  [6] Speichern …")
    summary = {
        "strategy": "0045_cotton_crop_condition",
        "hypothesis": "H-CT-01 (NASS crop-condition Δ)",
        "region": NASS_REGION, "delta_thresh_pp": DELTA_THRESH, "hold_days": HOLD_DAYS,
        "n_weeks": n_weeks, "n_events": n_events,
        "continuous_ic": {str(h): {"ic": float(sc["ic_decay"].loc[h, "ic"]),
                                   "p_value": sc["permutation"][h]["p_value"],
                                   "n_obs": sc["permutation"][h]["n_obs"]}
                          for h in IC_HORIZONS},
        "event_study": {str(h): s for h, s in es["summary"].items()},
        "net_backtest": {"sharpe": m["sharpe"], "cagr": m["cagr"],
                         "max_drawdown": m["max_drawdown"], "n_trades": ts["n_trades"],
                         "win_rate": ts["win_rate"], "expectancy_pct": ts["expectancy"] * 100,
                         "median_trade_pct": median_trade * 100, "perm_p": perm["p_value"],
                         "t_p": tt["p_value"], "boot_ci": [boot["ci_low"], boot["ci_high"]],
                         "dsr_psr": e["psr"]},
        "cost_model": "IBKR_SOFTS (4 bps/side)",
        "n_registered": N_REGISTERED, "n_local_tests": N_LOCAL,
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    es["table"].to_csv(RESULTS / "events.csv", index=False)
    if not trades_df.empty:
        trades_df.to_csv(RESULTS / "trades.csv")
    print(f"    → {RESULTS}")

    print("\n  ── Verdict ───────────────────────────────────────────────────────")
    print(f"    Kont. IC(22d): {ic22:+.3f} (p={p22:.3f}) → {'Signal' if ic_passes else 'kein Signal'}")
    print(f"    Event-Study Median(22d): {median_22*100:+.2f}%  (Win {es['summary'][22]['win_rate']:.0%}, n={n_events})")
    if not ic_passes and not (median_22 > 0 and perm["p_value"] < 0.05):
        print(f"    ✗ ABGELEHNT — kein IC-Signal und Event-Study leer (Münzwurf)")
    elif median_22 > 0 and perm["p_value"] < 0.05:
        print(f"    ⚠ LEAD — näher prüfen")
    else:
        print(f"    ✗ ABGELEHNT")
    print()


def _make_plots(cc, events, close, es, sc):
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))
    d = cc["pct_good_excellent_delta"].dropna()
    colors = ["#c1121f" if v < DELTA_THRESH else "#a8c686" for v in d]
    ax1.bar(d.index, d.values, color=colors, width=8, alpha=0.9)
    ax1.axhline(DELTA_THRESH, color="#c1121f", ls="--", lw=1.2, label=f"Event Δ<{DELTA_THRESH}pp")
    ax1.axhline(0, color="black", lw=0.5)
    ax1.set_ylabel("WoW Δ Good+Excellent (pp)"); ax1.legend(fontsize=8)
    ax1.set_title(f"Baumwolle {NASS_REGION} — wöchentl. Crop-Condition-Änderung (NASS, in-season)")

    ax2.plot(close.index, close.values, color="#6d6875", lw=0.8)
    ax2.set_ylabel("CT=F (¢/lb)")
    ax2.set_title("Baumwoll-Preis mit Deterioration-Events (rot) + 22-Tage-Haltefenster")
    for rel in events["release_date"]:
        i = close.index.searchsorted(rel)
        if i < len(close.index):
            end = min(i + HOLD_DAYS, len(close.index) - 1)
            ax2.axvspan(close.index[i], close.index[end], color="#c1121f", alpha=0.12)
    plt.tight_layout()
    plotting._add_caption(fig,
        "NASS wöchentliche Baumwoll-Crop-Condition Texas (PIT: Release Mo 16:00 ET, Entry Folgetag). "
        f"Rote Balken: WoW-Verschlechterung < {DELTA_THRESH}pp (vorab-registrierte Schwelle). "
        "Kreuz-Saison-Δ entfernt (nur konsekutive Reporting-Wochen).")
    plotting.savefig(fig, PLOTS / "crop_condition_overview.png")
    plt.close(fig)

    # IC decay
    fig2, ax = plt.subplots(figsize=(7, 5))
    decay = sc["ic_decay"]; hs = decay.index.tolist()
    ics = decay["ic"].values
    ps = [sc["permutation"][h]["p_value"] for h in hs]
    xp = np.arange(len(hs))
    bars = ax.bar(xp, ics, color=["#264653", "#2a9d8f", "#e9c46a"][:len(hs)], alpha=0.85)
    ax.axhline(0, color="black", lw=0.7); ax.set_xticks(xp)
    ax.set_xticklabels([f"{h}d" for h in hs]); ax.set_ylabel("Spearman IC")
    ax.set_title("0045 Baumwolle — IC-Decay (Crop-Condition Δ → Forward-Return)")
    for b, p in zip(bars, ps):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + (0.002 if b.get_height() >= 0 else -0.006),
                f"p={p:.2f}", ha="center", va="bottom" if b.get_height() >= 0 else "top", fontsize=9)
    plotting._add_caption(fig2,
        "IC nahe Null über alle Horizonte → die wöchentliche Crop-Condition-Änderung ist laufend "
        "eingepreist (effizienter, meistbeobachteter US-Ag-Report). Kein Surprise wie beim diskreten WASDE (0032).")
    plt.tight_layout()
    plotting.savefig(fig2, PLOTS / "ic_decay.png")
    plt.close(fig2)


if __name__ == "__main__":
    main()
