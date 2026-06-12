"""0064 — Football Value Betting, Phase 2: Schwellen-/Liga-Robustheit.

Die 0063-Regel wird EINGEFROREN (Entscheid 2026-06-12) und auf Robustheit
geprüft. Roadmap-Gate Phase 2: ROI-Bootstrap-KI > 0, Schwellen-Plateau stabil.

Eingefrorene Regel (aus 0063, kein Re-Fit):
    Shin-De-Vig auf Pinnacle-Collection-Quoten (PS*), wette Bet365-Outcome
    wenn EV > 2%, EV-Cap 20% (Daten-Fehler-Guard), CLV gemessen an der
    Shin-de-viggten Pinnacle-Schlusslinie.

Vorab registrierte Tests:

1. **Schwellen-Plateau (Diagnostik, keine Selektion):** EV-Schwelle
   0,5%-6% in 0,5%-Schritten auf den 7 Phase-1-Ligen — Median-CLV muss ein
   Plateau um die Headline bilden, kein Spike.
2. **Cross-Liga-OOS (DER Test, 0021-Methode):** eingefrorene Regel auf 11
   in Phase 1 NIE berührten Ligen (Eredivisie, Primeira Liga, Belgien,
   Süper Lig, Griechenland, Schottland, League One/Two, LaLiga2, Serie B,
   Ligue 2), gleiche Saisons. Median-CLV mit Bootstrap-KI.
3. **Odds-Bucket-Analyse (Diagnostik):** CLV/ROI nach Quoten-Klasse
   ([1;2,5), [2,5;4), [4;7), >=7) — lebt der Edge nur in Longshots
   (kaum handelbar: Limits, Slippage) oder auch vorne?
4. **1/4-Kelly-Sizing, Cap 2% Bankroll (1 neuer Trial):** stake ~
   (p*o-1)/(o-1); entschärft die Fat-Tail-Dominanz der Flat-Stakes.
   ROI-Bootstrap-KI auf dem kombinierten Panel (18 Ligen).

Kosten-Szenarien: primär = 0% Steuer (absorbierendes Buch) + 1% Slippage;
Stress = 5,3% Steuer auf Einsatz + 1% Slippage.

Gate Phase 2 (vorab):
    (a) OOS-Ligen: Median-CLV > 0, Bootstrap-KI ohne 0;
    (b) ROI-Bootstrap-KI > 0 (1/4-Kelly, Primär-Szenario, kombiniert);
    (c) Plateau: Median-CLV > 0 für alle Schwellen 1-4%.

Programm-Trials: 12 (0063) + 1 (Kelly) = 13.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "strategies" / "0063_football_value_betting"))

from quantlab.clv import clv_summary  # noqa: E402
from quantlab.football_data import get_matches  # noqa: E402

from run import SEASONS, TAX, build_bets  # noqa: E402  (0063 frozen pieces)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

# Eingefrorene Regel
METHOD = "shin"
THRESHOLD = 0.02
SLIPPAGE = 0.01
KELLY_FRACTION = 0.25
KELLY_CAP = 0.02

DIV_IS = ["E0", "E1", "D1", "D2", "SP1", "I1", "F1"]  # Phase-1-Ligen
DIV_OOS = ["N1", "P1", "B1", "T1", "G1", "SC0", "E2", "E3", "SP2", "I2", "F2"]

PLATEAU_THRESHOLDS = np.arange(0.005, 0.0625, 0.005)
ODDS_BUCKETS = [(1.0, 2.5), (2.5, 4.0), (4.0, 7.0), (7.0, np.inf)]


def select(bets: pd.DataFrame, threshold: float = THRESHOLD) -> pd.DataFrame:
    return bets[(bets["ev"] > threshold) & ~bets["suspect"]].copy()


def add_pnl_scenarios(sel: pd.DataFrame) -> pd.DataFrame:
    """Per-Einheit-Returns: primär (Slippage) und Stress (Slippage+Steuer)."""
    odds_slip = 1.0 + (sel["odds"] - 1.0) * (1.0 - SLIPPAGE)
    sel["ret_primary"] = odds_slip * sel["win"] - 1.0
    sel["ret_stress"] = sel["ret_primary"] - TAX
    # 1/4-Kelly auf der eigenen fair_p-Schätzung, Cap 2% Bankroll.
    f = KELLY_FRACTION * (sel["fair_p_open"] * sel["odds"] - 1.0) / (sel["odds"] - 1.0)
    sel["stake"] = np.clip(f, 0.0, KELLY_CAP)
    return sel


def roi_ci(ret: np.ndarray, stake: np.ndarray, n_boot: int = 10_000, seed: int = 2) -> dict:
    """Einsatz-gewichteter ROI = sum(stake*ret)/sum(stake), Bootstrap über Wetten."""
    ret, stake = np.asarray(ret, float), np.asarray(stake, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ret), size=(n_boot, len(ret)))
    boot = (stake[idx] * ret[idx]).sum(axis=1) / stake[idx].sum(axis=1)
    return {
        "roi": float((stake * ret).sum() / stake.sum()),
        "ci_low": float(np.percentile(boot, 2.5)),
        "ci_high": float(np.percentile(boot, 97.5)),
    }


def bankroll_path(sel: pd.DataFrame, ret_col: str) -> dict:
    """Sequentielle Compounding-Simulation (Diagnostik): stake-Anteil je Wette."""
    s = sel.sort_values("Date")
    equity = (1.0 + s["stake"].to_numpy() * s[ret_col].to_numpy()).cumprod()
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return {
        "final": float(equity[-1]),
        "max_dd": float(dd.min()),
        "n_bets": int(len(s)),
        "equity": equity,
        "dates": s["Date"].to_numpy(),
    }


def main() -> None:
    print("=== Lade Panels ===")
    df_is = get_matches(DIV_IS, SEASONS)
    df_oos = get_matches(DIV_OOS, SEASONS)
    need = ["PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA", "B365H", "B365D", "B365A", "FTR"]
    df_is = df_is.dropna(subset=need).reset_index(drop=True)
    df_oos = df_oos.dropna(subset=need).reset_index(drop=True)
    print(f"Phase-1-Ligen: {len(df_is)} Spiele | OOS-Ligen: {len(df_oos)} Spiele")

    bets_is = build_bets(df_is, METHOD)
    bets_oos = build_bets(df_oos, METHOD)
    metrics: dict = {
        "frozen_rule": f"{METHOD} @ {THRESHOLD:.0%}, EV-Cap 20%, CLV vs Shin-Close",
        "n_trials_program": 13,
        "panel": {"n_is": int(len(df_is)), "n_oos": int(len(df_oos)),
                  "div_is": DIV_IS, "div_oos": DIV_OOS},
    }

    # ---- 1. Schwellen-Plateau (Phase-1-Ligen) ------------------------------
    print("\n=== 1. Schwellen-Plateau (Phase-1-Ligen) ===")
    plateau = []
    for thr in PLATEAU_THRESHOLDS:
        sel = add_pnl_scenarios(select(bets_is, thr))
        if len(sel) < 30:
            continue
        s = clv_summary(sel["clv"].to_numpy())
        r = roi_ci(sel["ret_primary"].to_numpy(), sel["stake"].to_numpy())
        plateau.append({"threshold": float(thr), "n": s["n"], "clv_median": s["median"],
                        "clv_ci_low": s["median_ci_low"], "clv_ci_high": s["median_ci_high"],
                        "roi_kelly": r["roi"]})
        print(f"  thr {thr:.1%}: n={s['n']:>4}  CLV med {s['median']:+.4f} "
              f"[{s['median_ci_low']:+.4f},{s['median_ci_high']:+.4f}]  ROI(Kelly) {r['roi']:+.4f}")
    metrics["plateau"] = plateau
    pl = pd.DataFrame(plateau)
    core = pl[(pl.threshold >= 0.0099) & (pl.threshold <= 0.0401)]
    plateau_ok = bool((core["clv_median"] > 0).all())

    # ---- 2. Cross-Liga-OOS (eingefrorene Regel) ----------------------------
    print("\n=== 2. Cross-Liga-OOS: eingefrorene Regel auf 11 ungesehenen Ligen ===")
    sel_oos = add_pnl_scenarios(select(bets_oos))
    s_oos = clv_summary(sel_oos["clv"].to_numpy())
    print(f"OOS gesamt: n={s_oos['n']}  CLV med {s_oos['median']:+.4f} "
          f"[{s_oos['median_ci_low']:+.4f},{s_oos['median_ci_high']:+.4f}]  "
          f"frac>0 {s_oos['frac_positive']:.2f}")
    by_div = sel_oos.groupby("Div").agg(
        n=("clv", "size"), med_clv=("clv", "median"),
        ret_primary=("ret_primary", "mean"))
    by_season = sel_oos.groupby("Season").agg(n=("clv", "size"), med_clv=("clv", "median"))
    print(by_div.to_string(float_format=lambda x: f"{x:+.4f}"))
    print(by_season.to_string(float_format=lambda x: f"{x:+.4f}"))
    oos_ok = bool(s_oos["median_ci_low"] > 0)
    metrics["oos"] = {
        "summary": s_oos,
        "by_division": by_div.reset_index().to_dict(orient="records"),
        "by_season": by_season.reset_index().to_dict(orient="records"),
        "divisions_positive": int((by_div["med_clv"] > 0).sum()),
    }

    # ---- 3. Odds-Bucket-Analyse (kombiniert) -------------------------------
    print("\n=== 3. Odds-Buckets (kombiniert, eingefrorene Regel) ===")
    sel_is = add_pnl_scenarios(select(bets_is))
    sel_all = pd.concat([sel_is, sel_oos], ignore_index=True)
    buckets = []
    for lo, hi in ODDS_BUCKETS:
        b = sel_all[(sel_all["odds"] >= lo) & (sel_all["odds"] < hi)]
        if len(b) < 20:
            continue
        s = clv_summary(b["clv"].to_numpy())
        buckets.append({"bucket": f"[{lo},{hi})", "n": s["n"], "clv_median": s["median"],
                        "clv_ci_low": s["median_ci_low"], "clv_ci_high": s["median_ci_high"],
                        "ret_primary_mean": float(b["ret_primary"].mean()),
                        "win_rate": float(b["win"].mean())})
        print(f"  Quote [{lo:>4},{hi:>4}): n={s['n']:>4}  CLV med {s['median']:+.4f} "
              f"[{s['median_ci_low']:+.4f},{s['median_ci_high']:+.4f}]  "
              f"Ret/Wette {b['ret_primary'].mean():+.4f}  Win {b['win'].mean():.2f}")
    metrics["odds_buckets"] = buckets

    # ---- 4. Kelly-ROI-Gate (kombiniert) ------------------------------------
    print("\n=== 4. ROI-Gate: 1/4-Kelly, Cap 2%, kombiniert (18 Ligen) ===")
    res_kelly = {}
    for name, col in [("primary", "ret_primary"), ("stress", "ret_stress")]:
        r = roi_ci(sel_all[col].to_numpy(), sel_all["stake"].to_numpy())
        flat = roi_ci(sel_all[col].to_numpy(), np.ones(len(sel_all)))
        res_kelly[name] = {"kelly": r, "flat": flat}
        print(f"  {name:>8}: Kelly-ROI {r['roi']:+.4f} [{r['ci_low']:+.4f},{r['ci_high']:+.4f}]"
              f"  |  flat {flat['roi']:+.4f} [{flat['ci_low']:+.4f},{flat['ci_high']:+.4f}]")
    roi_ok = bool(res_kelly["primary"]["kelly"]["ci_low"] > 0)
    metrics["roi_gate"] = res_kelly

    bank = bankroll_path(sel_all, "ret_primary")
    print(f"  Bankroll-Sim (primär): Endstand {bank['final']:.3f}x, "
          f"MaxDD {bank['max_dd']:.1%} über {bank['n_bets']} Wetten")
    metrics["bankroll"] = {k: bank[k] for k in ("final", "max_dd", "n_bets")}

    # ---- Gate ---------------------------------------------------------------
    gate = {"a_oos_clv_ci_gt0": oos_ok, "b_roi_ci_gt0": roi_ok, "c_plateau_1_4pct": plateau_ok,
            "pass": bool(oos_ok and roi_ok and plateau_ok)}
    metrics["gate"] = gate
    print(f"\n=== Gate Phase 2: OOS-CLV-KI>0: {oos_ok} | ROI-KI>0 (Kelly, primär): {roi_ok} | "
          f"Plateau 1-4%: {plateau_ok} -> {'PASS' if gate['pass'] else 'FAIL'} ===")

    # ---- Plots --------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].errorbar(pl["threshold"] * 100, pl["clv_median"] * 100,
                     yerr=[(pl["clv_median"] - pl["clv_ci_low"]) * 100,
                           (pl["clv_ci_high"] - pl["clv_median"]) * 100],
                     fmt="o-", capsize=3)
    axes[0].axhline(0, color="grey", lw=0.8)
    axes[0].axvline(2.0, color="red", ls="--", lw=0.8, label="Headline 2%")
    axes[0].set_xlabel("EV-Schwelle (%)"); axes[0].set_ylabel("Median-CLV (%)")
    axes[0].set_title("Schwellen-Plateau (Phase-1-Ligen)"); axes[0].legend()
    axes[1].plot(pd.to_datetime(bank["dates"]), bank["equity"])
    axes[1].set_title(f"Bankroll 1/4-Kelly primär (Endstand {bank['final']:.2f}x)")
    axes[1].set_ylabel("Bankroll (x Start)")
    fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(RESULTS / "plateau_bankroll.png", dpi=120)

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    sel_all.to_csv(RESULTS / "trades.csv", index=False)
    print(f"\nGespeichert: results/metrics.json, results/trades.csv ({len(sel_all)} Wetten), "
          f"results/plateau_bankroll.png")


if __name__ == "__main__":
    main()
