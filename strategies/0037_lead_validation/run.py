"""Strategy 0037 — Lead validation sweep (graduate or reject the testing leads).

Phase 1 of the full-year seasonal calendar. Every ``status: testing`` lead with a
fixed week/date window is pushed through ONE frozen protocol built on the new
reusable quantlab infrastructure (no per-strategy copy-paste):

  1. Data-quality gate   — non-positive close / frozen-feed guard (lessons 0005/0025).
  2. Frozen rule         — exact window from the original REPORT, no re-tuning.
  3. Roll / stress test  — quantlab.roll.roll_exclusion_test: must survive removing
                           a tight zone around the in-window expiry (futures) or the
                           concentration cluster (corn WASDE days).
  4. Cross-instrument OOS — the frozen rule on unseen sibling instruments
                           (quantlab patterns 0021/0032): an edge that generalises
                           is not a single-series artifact.
  5. Significance        — permutation, bootstrap Sharpe CI, Deflated Sharpe with a
                           multiple-testing penalty, plus an IS/OOS mid-split.

The script PRINTS every number and writes results/metrics.json + verdict.csv. The
human-set verdict (confirmed / rejected) is then written back into
strategies/seasonal_calendar.yaml and CATALOG.md.

Chinese-New-Year leads (0023/0024) are a *moving feast* and need a dedicated CNY
signal builder — handled in Phase 2, not here.

Run:
    .venv/Scripts/python.exe strategies/0037_lead_validation/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics, trade_stats, run_backtest,
    bootstrap_ci, permutation_test, deflated_sharpe_ratio,
    roll_exclusion_test,
)
from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.lme_data import get_lme_metal  # noqa: E402
from quantlab.seasonal import date_window_signal  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"

# Each lead: frozen window + (optional) roll/stress zones to exclude + unseen
# sibling instruments for the cross-instrument OOS + a multiple-testing penalty.
# `stress_label` documents what the exclusion zone represents for that lead.
LEADS = [
    {
        "id": "0018", "name": "Platin Jahreswechsel", "ticker": "PL=F",
        "start_md": (12, 18), "end_md": (1, 10),
        "stress_zones": [((12, 24), (12, 31))], "stress_label": "Jahresend-Tage (Roll-Probe)",
        "oos_tickers": ["PPLT", "PA=F"], "n_trials": 100,
    },
    {
        "id": "0032", "name": "Mais WASDE-Kern", "ticker": "ZC=F",
        "start_md": (12, 8), "end_md": (12, 18),
        "stress_zones": [((12, 11), (12, 16))], "stress_label": "WASDE-Cluster 11.-16.12.",
        "oos_tickers": ["ZW=F"], "n_trials": 100,
    },
    {
        "id": "0035", "name": "Baumwolle Jahresende", "ticker": "CT=F",
        "start_md": (11, 21), "end_md": (12, 29),
        "stress_zones": [((11, 23), (11, 30))], "stress_label": "Dez-Kontrakt-Roll Ende Nov",
        "oos_tickers": [], "n_trials": 100,
    },
    {
        "id": "0031", "name": "Palladium Jahreswechsel", "ticker": "PA=F",
        "start_md": (12, 6), "end_md": (1, 25),
        "stress_zones": [((12, 24), (12, 31))], "stress_label": "Jahresend-Roll-Zone",
        "oos_tickers": [], "n_trials": 100,
    },
    {
        "id": "0025", "name": "Zink Sommerfenster", "ticker": "LME_ZINC",
        "start_md": (7, 4), "end_md": (7, 30),
        "stress_zones": [], "stress_label": "kein Roll (LME-Cash-Spot)",
        "oos_tickers": [], "n_trials": 100,
    },
]


def load_prices(ticker: str) -> pd.DataFrame:
    """Load a lead's prices and run the data-quality gate (0005/0025)."""
    px = get_lme_metal("zinc") if ticker == "LME_ZINC" else get_prices(ticker, start="2000-01-01")
    close = px["Close"].dropna()
    if (close <= 0).any():
        raise SystemExit(f"{ticker}: non-positive close — abort (0005).")
    # Frozen-feed guard: <=1 distinct close/year or mostly-zero returns => dead feed.
    by_year = close.groupby(close.index.year).nunique()
    zero_frac = float((close.pct_change().fillna(0.0) == 0.0).mean())
    if by_year.median() <= 1 or zero_frac > 0.5:
        raise SystemExit(f"{ticker}: frozen feed (distinct/yr {by_year.median()}, "
                         f"zero-frac {zero_frac:.2f}) — abort (0025).")
    return px


def evaluate(px: pd.DataFrame, start_md, end_md, n_trials: int) -> dict:
    """Full-sample frozen-window backtest + significance + IS/OOS mid-split."""
    sig = date_window_signal(px.index, start_md, end_md)
    res = run_backtest(px, sig, cost_model=IBKR_FUTURES)
    rets = res["returns"]
    asset_ret = px["Close"].pct_change().fillna(0.0)
    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])
    perm = permutation_test(rets, asset_ret, res["position"], n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
    dsr = deflated_sharpe_ratio(m["sharpe"], len(rets), n_trials, returns=rets)

    yrs = px.index.year
    mid = (int(yrs.min()) + int(yrs.max())) // 2
    split = f"{mid}-01-01"
    is_px, oos_px = px.loc[:split], px.loc[split:]
    is_sh = compute_metrics(run_backtest(is_px, date_window_signal(is_px.index, start_md, end_md),
                                         cost_model=IBKR_FUTURES)["returns"])["sharpe"]
    oos_sh = compute_metrics(run_backtest(oos_px, date_window_signal(oos_px.index, start_md, end_md),
                                          cost_model=IBKR_FUTURES)["returns"])["sharpe"]
    return {
        "sharpe": m["sharpe"], "cagr": m["cagr"], "max_dd": m["max_drawdown"],
        "expectancy": ts["expectancy"], "win_rate": ts["win_rate"], "n_trades": ts["n_trades"],
        "perm_p": perm["p_value"], "boot_lo": boot["ci_low"], "boot_hi": boot["ci_high"],
        "dsr": dsr["psr_deflated"], "is_sharpe": is_sh, "oos_sharpe": oos_sh, "split": split,
    }


def cross_instrument(ticker: str, start_md, end_md) -> dict:
    """Frozen rule on an unseen sibling: perm p, win, expectancy, bootstrap CI."""
    px = get_prices(ticker, start="2000-01-01")
    close = px["Close"].dropna()
    if len(close) < 250 or (close <= 0).any():
        return {"ticker": ticker, "ok": False, "note": "insufficient/invalid data"}
    sig = date_window_signal(px.index, start_md, end_md)
    res = run_backtest(px, sig, cost_model=IBKR_FUTURES)
    rets = res["returns"]
    ts = trade_stats(res["trades"])
    perm = permutation_test(rets, px["Close"].pct_change().fillna(0.0), res["position"], n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
    return {"ticker": ticker, "ok": True, "perm_p": perm["p_value"], "win_rate": ts["win_rate"],
            "expectancy": ts["expectancy"], "n_trades": ts["n_trades"],
            "boot_lo": boot["ci_low"], "boot_hi": boot["ci_high"]}


def suggest_verdict(full: dict, stress: dict | None, crosses: list[dict], has_siblings: bool) -> str:
    """Conservative auto-suggestion; final call documented by the human in REPORT."""
    # Significance must survive the stress/roll exclusion (if any).
    eff_p = stress["roll_excluded"]["perm_p"] if stress else full["perm_p"]
    survives = eff_p < 0.05
    boot_excl_zero = full["boot_lo"] > 0
    cross_ok = any(c.get("ok") and c.get("perm_p", 1) < 0.05 for c in crosses)
    if has_siblings:
        ok = survives and cross_ok and (boot_excl_zero or any(
            c.get("ok") and c.get("boot_lo", -1) > 0 for c in crosses))
    else:
        ok = survives and boot_excl_zero
    return "confirmed" if ok else "rejected"


def main() -> None:
    print("Strategy 0037 — Lead validation sweep (Phase 1)\n")
    RESULTS.mkdir(parents=True, exist_ok=True)

    summary, verdict_rows = {}, []
    for lead in LEADS:
        print(f"=== {lead['id']} {lead['name']} [{lead['ticker']}] "
              f"{lead['start_md']}->{lead['end_md']} ===")
        px = load_prices(lead["ticker"])
        full = evaluate(px, lead["start_md"], lead["end_md"], lead["n_trials"])

        stress = None
        if lead["stress_zones"]:
            sig = date_window_signal(px.index, lead["start_md"], lead["end_md"])
            stress = roll_exclusion_test(px, sig, lead["stress_zones"], n_perm=2000)

        crosses = [cross_instrument(t, lead["start_md"], lead["end_md"]) for t in lead["oos_tickers"]]
        has_sib = len(lead["oos_tickers"]) > 0
        verdict = suggest_verdict(full, stress, crosses, has_sib)

        print(f"  FULL : Sharpe {full['sharpe']:.2f}  exp {full['expectancy']*100:+.2f}%  "
              f"win {full['win_rate']:.0%}  n {full['n_trades']}  perm_p {full['perm_p']:.3f}  "
              f"boot[{full['boot_lo']:.2f};{full['boot_hi']:.2f}]  DSR {full['dsr']:.2f}")
        print(f"         IS/OOS Sharpe {full['is_sharpe']:.2f} / {full['oos_sharpe']:.2f} "
              f"(split {full['split']})")
        if stress:
            b, e = stress["base"], stress["roll_excluded"]
            print(f"  STRESS ({lead['stress_label']}): exp {b['expectancy']*100:+.2f}% -> "
                  f"{e['expectancy']*100:+.2f}%  perm_p {b['perm_p']:.3f} -> {e['perm_p']:.3f}  "
                  f"share_on_zone {stress['share_on_roll_days']:.0%}")
        else:
            print(f"  STRESS: {lead['stress_label']} (kein Test)")
        for c in crosses:
            if c.get("ok"):
                print(f"  XOOS  {c['ticker']}: perm_p {c['perm_p']:.3f}  win {c['win_rate']:.0%}  "
                      f"exp {c['expectancy']*100:+.2f}%  n {c['n_trades']}  "
                      f"boot[{c['boot_lo']:.2f};{c['boot_hi']:.2f}]")
            else:
                print(f"  XOOS  {c['ticker']}: {c.get('note')}")
        print(f"  -> SUGGESTED VERDICT: {verdict.upper()}\n")

        summary[lead["id"]] = {"name": lead["name"], "ticker": lead["ticker"],
                               "window": [list(lead["start_md"]), list(lead["end_md"])],
                               "full": full, "stress": stress, "stress_label": lead["stress_label"],
                               "cross": crosses, "suggested_verdict": verdict}
        verdict_rows.append({"id": lead["id"], "name": lead["name"], "ticker": lead["ticker"],
                             "perm_p": round(full["perm_p"], 3),
                             "stress_perm_p": round(stress["roll_excluded"]["perm_p"], 3) if stress else None,
                             "boot_lo": round(full["boot_lo"], 2), "dsr": round(full["dsr"], 2),
                             "is_sharpe": round(full["is_sharpe"], 2), "oos_sharpe": round(full["oos_sharpe"], 2),
                             "suggested_verdict": verdict})

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    pd.DataFrame(verdict_rows).to_csv(RESULTS / "verdict.csv", index=False)
    print(f"results -> {RESULTS}")


if __name__ == "__main__":
    main()
