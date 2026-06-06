"""Seasonal discovery screener for the empty calendar months.

Phase 2 of the full-year calendar. Runs candidate (asset, window, macro-story)
hypotheses for the uncovered months (April, June-October) through the SAME gate
battery the validated leads passed, so a new candidate is held to the identical
strict bar:

  1. data-quality gate (non-positive / frozen feed),
  2. frozen window (date or ISO-week, no in-sample tuning here),
  3. roll/stress exclusion for continuous futures (quantlab.roll),
  4. cross-instrument OOS on any unseen sibling,
  5. permutation + bootstrap Sharpe CI + Deflated Sharpe + IS/OOS mid-split.

This is the shared entry point for BOTH self-mined candidates and user-supplied
Seasonax windows: add a dict to CANDIDATES and re-run. A candidate that does not
clear the bar is documented as rejected — leaving the month uncovered is an
acceptable outcome ("Strenge halten, Lücke lassen").

Run:
    .venv/Scripts/python.exe analysis/seasonal_discovery.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics, trade_stats, run_backtest,
    bootstrap_ci, permutation_test, deflated_sharpe_ratio, roll_exclusion_test,
)
from quantlab.costs import IBKR_DEFAULT, IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.lme_data import get_lme_metal  # noqa: E402
from quantlab.seasonal import date_window_signal, event_signal  # noqa: E402

OUT = Path(__file__).resolve().parent / "discovery_results.json"

# Candidate windows for the empty months. Each needs a genuine supply/demand
# story and (ideally) a drift-poor asset so a permutation pass is meaningful.
# roll_zones: tight month-end zones around in-window expiries (continuous futures).
# oos_tickers: unseen siblings for the cross-instrument check.
CANDIDATES = [
    {
        "name": "Sojabohnen Ernte-Tief", "ticker": "ZS=F", "month": "Okt",
        "kind": "date", "start_md": (10, 1), "end_md": (10, 21),
        "roll_zones": [], "oos_tickers": ["ZM=F", "ZL=F"],
        "macro": "US-Sojaernte-Druck bodet Anfang Okt, dann SA-Pflanzwetter-Prämie."},
    {
        "name": "Weizen Herbst-Export", "ticker": "ZW=F", "month": "Sep",
        "kind": "date", "start_md": (9, 1), "end_md": (9, 25),
        "roll_zones": [], "oos_tickers": ["KE=F"],
        "macro": "Nordhalbkugel-Aussaat + Export-Nachfrage festigen Weizen im Sep."},
    {
        "name": "Heizöl Vorwinter", "ticker": "HO=F", "month": "Sep/Okt",
        "kind": "date", "start_md": (9, 5), "end_md": (10, 20),
        "roll_zones": [((9, 24), (9, 30)), ((10, 24), (10, 31))], "oos_tickers": [],
        "macro": "Destillat-Bevorratung vor der Heizsaison treibt Heizöl im Herbst."},
    {
        "name": "Benzin April-Fortsetzung", "ticker": "RB=F", "month": "Apr",
        "kind": "date", "start_md": (3, 20), "end_md": (4, 18),
        "roll_zones": [((3, 26), (3, 31)), ((4, 24), (4, 30))], "oos_tickers": [],
        "macro": "Driving-Season-Aufbau setzt sich nach dem KW9-Kick (0006) fort."},
    {
        "name": "Mageres Schwein Grill", "ticker": "HE=F", "month": "Jun",
        "kind": "date", "start_md": (6, 1), "end_md": (6, 25),
        "roll_zones": [], "oos_tickers": ["LE=F"],
        "macro": "Sommer-Grillnachfrage stützt Schweine vor dem Juli-Hoch."},
    {
        "name": "Kupfer Sommerflaute (kontra)", "ticker": "LME_COPPER", "month": "Aug",
        "kind": "date", "start_md": (8, 1), "end_md": (8, 25),
        "roll_zones": [], "oos_tickers": [],
        "macro": "China-Restocking nach Sommerflaute; LME-Cash (kein Roll)."},
    {
        "name": "Broadridge Sommerfenster", "ticker": "BR", "month": "Jun/Jul",
        "kind": "date", "start_md": (6, 5), "end_md": (7, 25), "cost": IBKR_DEFAULT,
        "roll_zones": [], "oos_tickers": [],
        "macro": "Seasonax-Lead (US11133T1034). FY-Ende 30.6. + Pre-Earnings-Drift "
                 "(Q4-Report Anfang Aug) — dünne Story; driftstarke Einzelaktie."},
    {
        "name": "Weizen Ernte-Short", "ticker": "ZW=F", "month": "Jun-Aug",
        "kind": "date", "start_md": (6, 18), "end_md": (8, 11), "direction": -1,
        "roll_zones": [((6, 26), (7, 2)), ((7, 12), (7, 16))], "oos_tickers": ["KE=F"],
        "macro": "Seasonax-Short: Nordhalbkugel-Winterweizen-Ernte drückt Juni/Juli "
                 "(Erntedruck-Tief). Continuous rollt Jul->Sep mitten im Fenster."},
    {
        "name": "Soja Ernte-Short", "ticker": "ZS=F", "month": "Jun-Aug",
        "kind": "date", "start_md": (6, 18), "end_md": (8, 11), "direction": -1,
        "roll_zones": [((6, 26), (7, 2)), ((7, 12), (7, 16)), ((7, 26), (8, 2))],
        "oos_tickers": ["ZM=F", "ZL=F"],
        "macro": "Seasonax-Short. ROLL-ARTEFAKT: voll perm p=0.021 + Sojamehl p=0.045, "
                 "aber ~88% der Expectancy auf Roll-Tagen (Old/New-Crop-Roll-Down); "
                 "nach Ausschluss p 0.021->0.093, exp +2.78%->+0.32%. Wie 0028/0034."},
    {
        "name": "Kakao Juni-Kurzfenster", "ticker": "CC=F", "month": "Jun",
        "kind": "date", "start_md": (6, 5), "end_md": (6, 13), "direction": 1,
        "roll_zones": [], "oos_tickers": [],
        "macro": "Seasonax-Lead (75% Win, +99.7% annualisiert). ABGELEHNT: Headline "
                 "irrefuehrend (6-Tage-Hold annualisiert); perm p=0.166, Sharpe -0.12, "
                 "IS/OOS beide negativ. Kein Timing-Edge, nur kleiner Long-Schnitt. Wie 0026."},
    {
        "name": "Magere Schweine Juni-Roll", "ticker": "HE=F", "month": "Jun",
        "kind": "date", "start_md": (6, 5), "end_md": (6, 18), "direction": 1,
        "roll_zones": [((6, 12), (6, 17))], "oos_tickers": [],
        "macro": "Seasonax-Lead. ROLL-ARTEFAKT trotz perm p=0.011 + IS/OOS beide positiv "
                 "+ driftarm: HE-Juni-Kontrakt verfaellt mitten im Fenster; ~86% der "
                 "Expectancy auf Roll-Tagen, nach Ausschluss p 0.011->0.715. Wie 0028/0029."},
]


def load_prices(ticker: str) -> pd.DataFrame:
    if ticker.startswith("LME_"):
        px = get_lme_metal(ticker.split("_", 1)[1].lower())
    else:
        px = get_prices(ticker, start="2000-01-01")
    close = px["Close"].dropna()
    if (close <= 0).any():
        raise ValueError(f"{ticker}: non-positive close")
    by_year = close.groupby(close.index.year).nunique()
    zero_frac = float((close.pct_change().fillna(0.0) == 0.0).mean())
    if by_year.median() <= 1 or zero_frac > 0.5:
        raise ValueError(f"{ticker}: frozen feed")
    return px


def make_signal(idx, c):
    """Build the leg signal, applying direction (+1 long / -1 short)."""
    direction = c.get("direction", 1)
    if c["kind"] == "week":
        sig = event_signal(idx, c["week"], hold_days=c.get("hold_days", 5))
    else:
        sig = date_window_signal(idx, c["start_md"], c["end_md"])
    return direction * sig


def evaluate(px, c, n_trials=100):
    cost = c.get("cost", IBKR_FUTURES)
    sig = make_signal(px.index, c)
    res = run_backtest(px, sig, cost_model=cost)
    rets = res["returns"]
    asset_ret = px["Close"].pct_change().fillna(0.0)
    m = compute_metrics(rets); ts = trade_stats(res["trades"])
    perm = permutation_test(rets, asset_ret, res["position"], n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
    dsr = deflated_sharpe_ratio(m["sharpe"], len(rets), n_trials, returns=rets)
    yrs = px.index.year; mid = (int(yrs.min()) + int(yrs.max())) // 2
    is_px, oos_px = px.loc[:f"{mid}-01-01"], px.loc[f"{mid}-01-01":]
    is_sh = compute_metrics(run_backtest(is_px, make_signal(is_px.index, c), cost_model=cost)["returns"])["sharpe"]
    oos_sh = compute_metrics(run_backtest(oos_px, make_signal(oos_px.index, c), cost_model=cost)["returns"])["sharpe"]
    return {"sharpe": m["sharpe"], "cagr": m["cagr"], "expectancy": ts["expectancy"],
            "win_rate": ts["win_rate"], "n_trades": ts["n_trades"], "perm_p": perm["p_value"],
            "boot_lo": boot["ci_low"], "boot_hi": boot["ci_high"], "dsr": dsr["psr_deflated"],
            "is_sharpe": is_sh, "oos_sharpe": oos_sh}


def cross(ticker, c):
    try:
        px = load_prices(ticker)
    except ValueError as e:
        return {"ticker": ticker, "ok": False, "note": str(e)}
    sig = make_signal(px.index, c)
    res = run_backtest(px, sig, cost_model=IBKR_FUTURES)
    perm = permutation_test(res["returns"], px["Close"].pct_change().fillna(0.0),
                            res["position"], n_perm=2000)
    ts = trade_stats(res["trades"])
    return {"ticker": ticker, "ok": True, "perm_p": perm["p_value"],
            "win_rate": ts["win_rate"], "n_trades": ts["n_trades"]}


def verdict(full, stress, crosses, has_sib):
    eff_p = stress["roll_excluded"]["perm_p"] if stress else full["perm_p"]
    survives = eff_p < 0.05
    boot_ok = full["boot_lo"] > 0
    oos_ok = full["oos_sharpe"] > 0
    cross_ok = any(c.get("ok") and c.get("perm_p", 1) < 0.05 for c in crosses)
    if has_sib:
        return "LEAD" if (survives and cross_ok and oos_ok) else "reject"
    return "LEAD" if (survives and boot_ok and oos_ok) else "reject"


def main():
    print("Phase 2 — seasonal discovery screen (empty months)\n")
    out = {}
    for c in CANDIDATES:
        print(f"=== {c['name']} [{c['ticker']}] {c['month']} ===")
        print(f"    Makro: {c['macro']}")
        try:
            px = load_prices(c["ticker"])
        except ValueError as e:
            print(f"    SKIP — {e}\n"); out[c["name"]] = {"skip": str(e)}; continue
        full = evaluate(px, c)
        stress = None
        if c["roll_zones"]:
            stress = roll_exclusion_test(px, make_signal(px.index, c), c["roll_zones"], n_perm=2000)
        crosses = [cross(t, c) for t in c["oos_tickers"]]
        v = verdict(full, stress, crosses, bool(c["oos_tickers"]))
        print(f"    FULL: Sharpe {full['sharpe']:.2f}  exp {full['expectancy']*100:+.2f}%  win {full['win_rate']:.0%}  "
              f"n {full['n_trades']}  perm_p {full['perm_p']:.3f}  boot[{full['boot_lo']:.2f};{full['boot_hi']:.2f}]  "
              f"IS/OOS {full['is_sharpe']:.2f}/{full['oos_sharpe']:.2f}")
        if stress:
            print(f"    STRESS: perm_p {stress['base']['perm_p']:.3f} -> {stress['roll_excluded']['perm_p']:.3f}  "
                  f"share_on_zone {stress['share_on_roll_days']:.0%}")
        for cr in crosses:
            print(f"    XOOS {cr['ticker']}: " + (f"perm_p {cr['perm_p']:.3f} win {cr['win_rate']:.0%} n {cr['n_trades']}"
                                                  if cr.get("ok") else cr.get("note")))
        print(f"    -> {v}\n")
        out[c["name"]] = {"candidate": c, "full": full, "stress": stress, "cross": crosses, "verdict": v}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    leads = [k for k, v in out.items() if isinstance(v, dict) and v.get("verdict") == "LEAD"]
    print(f"LEADS: {leads or 'none — all candidates rejected, months stay uncovered'}")
    print(f"results -> {OUT}")


if __name__ == "__main__":
    main()
