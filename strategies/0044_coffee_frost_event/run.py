"""Strategy 0044 — Coffee (KC) Fundamental: Realized-Frost Event Study (H-KC-01)

Hypothesis (from fundamentals/HYPOTHESES.md, H-KC-01):
    A frost / extreme-cold event in the Brazilian arabica belt (Minas Gerais,
    Jun–Aug) physically damages the crop → yield loss → price rises. We do NOT
    predict frost (lesson 0027: you cannot time a surprise); we position AFTER a
    realized cold event and ride the slow diffusion (1–3 months).

Difference from strategy 0027 (which is REJECTED):
    0027 used a fixed CALENDAR window (15 Jul – 28 Aug) every year — sitting long
    in a volatile window hoping a shock lands. This strategy uses ACTUAL ERA5
    temperature data to detect realized cold anomalies and only positions after
    one occurs. That is the targeted, event-conditioned version of the idea.

Coordinate validation (done before this run):
    The arabica frost belt is Sul de Minas (-21.5, -45.5), the heart of current
    production. At this ERA5 grid cell the three coldest-night anomalies in the
    record are 1994 (z-2.4), 2021 (z-2.3), 2000 (z-1.8) — EXACTLY the three known
    severe Brazilian coffee frost/cold years. So the ERA5 anomaly genuinely tracks
    real frost damage here (the originally-registered -19.5/-43.5 cell has a warm
    bias and never drops below 2.3 C — it cannot see frost).

Data limitation (documented):
    ERA5 grid cells (~25 km) smooth out the local valley cold-pockets where frost
    actually forms, so an ABSOLUTE temperature threshold is unreliable. We use the
    ANOMALY (z-score vs rolling past climatology of the monthly coldest night),
    which is robust to the grid warm bias.

Tests:
    1. Continuous IC screen: monthly coldest-night cold-anomaly → KC forward return
       (all Jun–Aug months). Tests whether "colder than usual" predicts price.
    2. EVENT STUDY (primary for this sparse hypothesis): forward returns after each
       z < -2 sigma cold event. Apply lesson 0027 criteria: median must be positive
       (no fat-tail lottery), and with so few events demand p < 0.01.
    3. Net-of-cost threshold backtest with the full validation battery (flagged
       underpowered: n_events is tiny).

Run:
    .venv/Scripts/python.exe strategies/0044_coffee_frost_event/run.py
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
from quantlab.fundamental_data import get_weather_daily  # noqa: E402
from quantlab.features import weather_anomaly          # noqa: E402
from quantlab.ic import score_feature, print_scorecard  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS   = RESULTS / "plots"

# ── Pre-registered parameters (from HYPOTHESES.md — do NOT tune) ─────────────
KC_TICKER     = "KC=F"
KC_NAME       = "Arabica-Kaffee (Coffee-Future)"
FROST_COORD   = (-21.5, -45.5)     # Sul de Minas — validated frost belt
FROST_REGION  = "Sul de Minas (-21.5, -45.5)"
FROST_MONTHS  = (6, 7, 8)          # Jun–Aug Brazilian winter
FROST_Z       = -2.0               # sigma — pre-registered extreme-cold threshold
HOLD_DAYS     = 66                 # 3M diffusion (pre-registered)
IC_HORIZONS   = (5, 22, 66)
CLIM_WINDOW   = 20                 # rolling climatology years
SPLIT_YEAR    = 2013               # IS 2000–2012 / OOS 2013–2026 (matches 0027)
COST_MODEL    = IBKR_SOFTS         # liquid soft, 8 bps RT
N_REGISTERED  = 14
N_LOCAL       = 3                  # feature × 3 horizons
N_PERM        = 2000


def guard_prices(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{ticker}: non-positive close (lesson 0005).")
    if int(prices["Close"].groupby(prices.index.year).nunique().min()) < 50:
        raise SystemExit(f"{ticker}: frozen feed (lesson 0025).")
    return prices


def build_frost_signal(events: pd.DataFrame, hold_days: int,
                       price_index: pd.DatetimeIndex) -> pd.Series:
    """Long KC for ``hold_days`` after each frost event's release_date.

    Entry is at the first trading day on/after release_date (= month-end + 1,
    i.e. the cold month's coldest night is fully known). Engine shifts +1 day.
    """
    signal = pd.Series(0.0, index=price_index)
    for rel in events["release_date"]:
        i = price_index.searchsorted(rel)
        if i >= len(price_index):
            continue
        end = min(i + hold_days, len(price_index) - 1)
        signal.iloc[i:end + 1] = 1.0
    return signal


def event_study(events: pd.DataFrame, close: pd.Series,
                anom: pd.Series, horizons=(22, 66, 132)) -> dict:
    """Forward returns after each frost event (the core test for a sparse signal)."""
    def fwd(entry, days):
        idx = close.index[close.index >= entry]
        if len(idx) == 0:
            return np.nan
        pos = close.index.get_loc(idx[0])
        if pos + days >= len(close):
            return np.nan
        return close.iloc[pos + days] / close.iloc[pos] - 1.0

    rows = []
    for d in events.index:
        rel = events.loc[d, "release_date"]
        rows.append({
            "event": f"{d.year}-{d.month:02d}",
            "z": float(anom.loc[d]),
            **{f"ret_{h}d": fwd(rel, h) for h in horizons},
        })
    df = pd.DataFrame(rows)
    summary = {}
    for h in horizons:
        r = df[f"ret_{h}d"].dropna().values
        summary[h] = {
            "mean": float(np.mean(r)) if len(r) else np.nan,
            "median": float(np.median(r)) if len(r) else np.nan,
            "win_rate": float((r > 0).mean()) if len(r) else np.nan,
            "n": int(len(r)),
        }
    return {"table": df, "summary": summary}


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
    print(f"  Strategy 0044 — Coffee Frost Event Study (H-KC-01)")
    print(f"  Region: {FROST_REGION}  |  frost: z<{FROST_Z}σ in Jun–Aug")
    print(f"  Position AFTER realized cold event, hold {HOLD_DAYS}d (diffusion)")
    print(f"{'='*66}\n")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # ── 0. Load ──────────────────────────────────────────────────────────────
    print("  [0] Preise + Wetter laden …")
    kc = guard_prices(get_prices(KC_TICKER, start="2000-01-01"), KC_TICKER)
    close = kc["Close"]
    w = get_weather_daily(*FROST_COORD, start="1990-01-01", end="2026-06-07",
                          variables=["temperature_2m_min"])

    # ── 1. Feature: monthly coldest-night cold anomaly ───────────────────────
    print("  [1] Feature: monatliche Kältenacht-Anomalie (agg=min, 20J Klimatologie) …")
    anom_df = weather_anomaly(w, "temperature_2m_min", agg="min",
                              window_years=CLIM_WINDOW, min_years=5)
    ja = anom_df[anom_df.index.month.isin(FROST_MONTHS)].copy()
    ja["cold_signal"] = -ja["temperature_2m_min_anomaly"]   # colder = more bullish
    anom = ja["temperature_2m_min_anomaly"]

    # ── 2. Coordinate validation (known frost years) ─────────────────────────
    season_min = anom.groupby(anom.index.year).min()  # most-negative anomaly per year
    top3 = season_min.sort_values().head(3)
    print(f"    Koordinaten-Validierung — kälteste Jahres-Anomalien (z):")
    print(f"      {', '.join(f'{y}: z{season_min[y]:+.2f}' for y in top3.index)}")
    print(f"      (bekannte schwere Frostjahre: 1994, 2000, 2021)\n")

    # ── 3. Continuous IC screen ──────────────────────────────────────────────
    print("  [3] Kontinuierlicher IC-Screen (alle Jun–Aug-Monate) …\n")
    sc = score_feature(ja, kc, "cold_signal", horizons=IC_HORIZONS, n_perm=1000)
    print_scorecard(sc)
    ic66 = sc["ic_decay"].loc[66, "ic"]
    p66 = sc["permutation"][66]["p_value"]
    ic_passes = p66 < 0.10 and ic66 > 0
    print(f"\n  Kontinuierlicher IC bei 66d: IC={ic66:+.3f}, perm-p={p66:.3f} "
          f"→ {'PASS' if ic_passes else 'FAIL ✗'}")

    # ── 4. Event study (PRIMARY for a sparse-event hypothesis) ───────────────
    print("\n  [4] Event-Study: Forward-Returns nach jedem z<-2σ Kälte-Event …\n")
    events = ja[(ja["temperature_2m_min_anomaly"] < FROST_Z) &
                (ja.index.year >= 2000)].copy()
    es = event_study(events, close, anom, horizons=(22, 66, 132))
    print(es["table"].to_string(index=False,
          formatters={c: (lambda v: f"{v*100:+.1f}%") for c in es["table"].columns
                      if c.startswith("ret_")}))
    print()
    for h, s in es["summary"].items():
        print(f"    {h:>3}d: mean={s['mean']*100:+.1f}%  median={s['median']*100:+.1f}%  "
              f"win={s['win_rate']:.0%}  n={s['n']}")

    n_events = len(events)
    median_66 = es["summary"][66]["median"]
    median_positive = median_66 > 0

    # ── 5. Net-of-cost threshold backtest (underpowered — n is tiny) ─────────
    print(f"\n  [5] Netto-Backtest (long {HOLD_DAYS}d nach jedem Event) — "
          f"UNTERPOWERT (n_events={n_events}) …\n")
    signal = build_frost_signal(events, HOLD_DAYS, kc.index)
    e = evaluate(kc, signal, n_trials=N_LOCAL)
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

    # ── 6. Plots ─────────────────────────────────────────────────────────────
    print("\n  [6] Plots …")
    _make_plots(ja, anom, events, close, es, sc)

    # ── 7. Persist + verdict ─────────────────────────────────────────────────
    print("  [7] Speichern …")
    summary = {
        "strategy": "0044_coffee_frost_event",
        "hypothesis": "H-KC-01 (realized-frost event study)",
        "region": FROST_REGION,
        "frost_z": FROST_Z, "hold_days": HOLD_DAYS,
        "n_events": n_events,
        "events": es["table"].to_dict(orient="records"),
        "event_study_summary": {str(h): s for h, s in es["summary"].items()},
        "continuous_ic": {str(h): {"ic": float(sc["ic_decay"].loc[h, "ic"]),
                                   "p_value": sc["permutation"][h]["p_value"],
                                   "n_obs": sc["permutation"][h]["n_obs"]}
                          for h in IC_HORIZONS},
        "net_backtest": {"sharpe": m["sharpe"], "cagr": m["cagr"],
                         "max_drawdown": m["max_drawdown"], "n_trades": ts["n_trades"],
                         "win_rate": ts["win_rate"], "expectancy_pct": ts["expectancy"] * 100,
                         "median_trade_pct": median_trade * 100,
                         "perm_p": perm["p_value"], "t_p": tt["p_value"],
                         "boot_ci": [boot["ci_low"], boot["ci_high"]], "dsr_psr": e["psr"]},
        "cost_model": "IBKR_SOFTS (4 bps/side)",
        "n_registered": N_REGISTERED, "n_local_tests": N_LOCAL,
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    es["table"].to_csv(RESULTS / "events.csv", index=False)
    if not e["res"]["trades"].empty:
        e["res"]["trades"].to_csv(RESULTS / "trades.csv")
    print(f"    → {RESULTS}")

    print("\n  ── Verdict ───────────────────────────────────────────────────────")
    print(f"    Kontinuierlicher IC(66d): {ic66:+.3f} (p={p66:.3f}) → "
          f"{'Signal' if ic_passes else 'kein Signal'}")
    print(f"    Event-Study Median(66d): {median_66*100:+.1f}% "
          f"({'positiv' if median_positive else 'NEGATIV — Fat-Tail-Verbot 0027'})")
    print(f"    Events: n={n_events} (unterpowert), Win 66d={es['summary'][66]['win_rate']:.0%}")
    if not ic_passes and not median_positive:
        print(f"    ✗ ABGELEHNT — kein IC-Signal UND Event-Median negativ (Fat-Tail-Lotterie)")
    elif median_positive and perm["p_value"] < 0.01:
        print(f"    ⚠ SCHWACHER LEAD — Median positiv, aber n={n_events} zu klein → Forward-Test nötig")
    else:
        print(f"    ✗ ABGELEHNT — Kriterien (positiver Median + p<0.01) nicht erfüllt")
    print()


def _make_plots(ja, anom, events, close, es, sc) -> None:
    import matplotlib.pyplot as plt

    # Plot 1: anomaly time series + KC price with frost events
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))
    a = anom.dropna()
    colors = ["#1d3557" if v < FROST_Z else "#a8dadc" for v in a]
    ax1.bar(a.index, a.values, color=colors, width=25, alpha=0.9)
    ax1.axhline(FROST_Z, color="#e63946", ls="--", lw=1.2, label=f"Frost z<{FROST_Z}σ")
    ax1.axhline(0, color="black", lw=0.5)
    ax1.set_ylabel("Kältenacht-Anomalie (z)"); ax1.legend(fontsize=8)
    ax1.set_title(f"Kaffee-Frostgürtel {FROST_REGION} — monatliche Kältenacht-Anomalie (Jun–Aug)")

    ax2.plot(close.index, close.values, color="#6d4c41", lw=0.8)
    ax2.set_ylabel("KC=F (¢/lb)")
    ax2.set_title("Arabica-Kaffee-Preis mit Frost-Events (blau) + 66-Tage-Haltefenster (rot)")
    for rel in events["release_date"]:
        i = close.index.searchsorted(rel)
        if i < len(close.index):
            end = min(i + HOLD_DAYS, len(close.index) - 1)
            ax2.axvspan(close.index[i], close.index[end], color="#e63946", alpha=0.18)
    plt.tight_layout()
    plotting._add_caption(fig,
        f"ERA5-Kältenacht-Anomalie (agg=min, 20J rollierende Klimatologie, PIT-korrekt). Blaue Balken: "
        f"z<{FROST_Z}σ Extrem-Kälte. Validierung: die kältesten Jahres-Anomalien sind 1994/2021/2000 = "
        f"die bekannten schweren Frostjahre. Rote Bänder: 66-Tage-Long nach jedem Event.")
    plotting.savefig(fig, PLOTS / "frost_events_overview.png")
    plt.close(fig)

    # Plot 2: event-study forward returns
    tbl = es["table"]
    fig2, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(tbl))
    width = 0.27
    for k, (h, col, c) in enumerate([(22, "ret_22d", "#264653"),
                                     (66, "ret_66d", "#2a9d8f"),
                                     (132, "ret_132d", "#e9c46a")]):
        ax.bar(x + (k - 1) * width, tbl[col] * 100, width, label=f"{h}d", color=c, alpha=0.9)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(tbl["event"])
    ax.set_ylabel("Forward-Return (%)")
    ax.set_title("0044 Kaffee — Forward-Returns nach jedem realisierten Frost-Event")
    ax.legend(title="Horizont")
    med66 = es["summary"][66]["median"] * 100
    ax.annotate(f"Median 66d = {med66:+.1f}%  (Win {es['summary'][66]['win_rate']:.0%}, n={es['summary'][66]['n']})",
                xy=(0.5, 0.95), xycoords="axes fraction", ha="center", fontsize=10,
                color="#e63946", fontweight="bold")
    plotting._add_caption(fig2,
        "Forward-Returns nach jedem z<-2σ Kälte-Event. Nur 2/5 (2021, 2024) führten zu steigenden Preisen; "
        "die anderen waren harmlose Kältenächte, bei denen der Erntedruck dominierte → Preis fiel. "
        "Median bei 22d/66d NEGATIV = Fat-Tail-Lotterie (Verbot aus Lektion 0027), nicht handelbar.")
    plotting.savefig(fig2, PLOTS / "event_study_returns.png")
    plt.close(fig2)


if __name__ == "__main__":
    main()
