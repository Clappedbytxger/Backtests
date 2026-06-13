"""0067 pre-test (0049 discipline): kill hypotheses BEFORE building the report.

Calendar-spread seasonality: express the catalog's VALIDATED outright seasonal
windows as front-vs-second spreads (long .c.0 / short .c.1). The windows are
pre-registered from prior work — NO new window mining. 5 hypotheses = 5 trials.

Spread return = roll-adjusted front return − roll-adjusted second return
(both legs zeroed on either leg's instrument_id change — lesson 0028/0048:
the stitch gap is a fiction; intra-contract convergence is the real carry).

Run:
    .venv/Scripts/python.exe strategies/0067_calendar_spread_seasonals/explore.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.futures_curve import get_curve_contract  # noqa: E402
from quantlab.significance import t_test_mean_return  # noqa: E402

# Pre-registered hypotheses: window <- the validated/known outright seasonal.
HYPOTHESES = [
    {"id": "H1", "root": "RB", "kind": "week", "week": 9, "hold": 5,
     "name": "Benzin KW9 (0006)", "story": "Driving-Season-Restocking strafft den Prompt"},
    {"id": "H2", "root": "GF", "kind": "week", "week": 21, "hold": 5,
     "name": "Mastrind KW21 (0009)", "story": "Grillsaison-Prompt-Nachfrage"},
    {"id": "H3", "root": "ZC", "kind": "date", "start_md": (12, 8), "end_md": (12, 18),
     "name": "Mais Dezember (0030)", "story": "WASDE/alte-vs-neue-Ernte"},
    {"id": "H4", "root": "NG", "kind": "date", "start_md": (9, 21), "end_md": (11, 1),
     "name": "Erdgas Herbst (0028!)", "story": "Injection->Withdrawal-Uebergang (als Outright Roll-Artefakt)"},
    {"id": "H5", "root": "PL", "kind": "date", "start_md": (12, 18), "end_md": (1, 10),
     "name": "Platin Jahreswechsel (0021)", "story": "Jahresend-Investment-/Industrienachfrage"},
]


def spread_returns(root: str) -> pd.Series:
    """Daily long-front/short-second return, roll days zeroed on both legs."""
    f = get_curve_contract(f"{root}.c.0")
    s = get_curve_contract(f"{root}.c.1")
    df = pd.DataFrame({
        "f": f["Close"], "fid": f["instrument_id"],
        "s": s["Close"], "sid": s["instrument_id"],
    }).dropna()
    # Drop UTC-Sunday session rows (0057 lesson: thin Globex Sunday bars).
    df = df[df.index.dayofweek < 5]
    roll = (df["fid"].ne(df["fid"].shift(1)) | df["sid"].ne(df["sid"].shift(1)))
    roll.iloc[0] = False
    rf = df["f"].pct_change().where(~roll, 0.0)
    rs = df["s"].pct_change().where(~roll, 0.0)
    return (rf - rs).dropna().rename(root)


def window_mask(index: pd.DatetimeIndex, h: dict) -> pd.Series:
    pos = np.zeros(len(index))
    if h["kind"] == "week":
        iso = index.isocalendar()
        for y in np.unique(iso["year"].values):
            locs = np.where((iso["year"].values == y) & (iso["week"].values == h["week"]))[0]
            if len(locs):
                pos[locs[0]:locs[0] + h["hold"]] = 1.0
    else:
        sm, sd = h["start_md"]; em, ed = h["end_md"]
        wrap = (em, ed) < (sm, sd)
        for y in range(index.year.min() - 1, index.year.max() + 1):
            start = pd.Timestamp(y, sm, sd)
            end = pd.Timestamp(y + 1 if wrap else y, em, ed)
            pos[np.asarray((index >= start) & (index <= end))] = 1.0
    return pd.Series(pos, index=index)


def main() -> None:
    print("0067 explore — Saison-Fenster als Front/Second-Spreads (5 vorregistrierte Hypothesen)\n")
    print(f"{'hyp':28s}{'Jahre':>6}{'mean/Trade':>12}{'win':>6}{'t':>7}{'p':>8}"
          f"{'Sharpe(akt)':>12}{'Baseline bps/d':>15}")
    for h in HYPOTHESES:
        r = spread_returns(h["root"])
        sig = window_mask(r.index, h).shift(1).fillna(0.0)  # T+1 wie der Backtest
        act = r[sig > 0]
        base = r[sig == 0]
        # per-year trade PnL (sum of in-window daily spread returns);
        # year-wrap windows assign the January part to the previous year's trade
        per_year = act.groupby(act.index.year).sum()
        if h["kind"] == "date" and h["end_md"] < h["start_md"]:
            yr = act.index.year - (act.index.month <= h["end_md"][0]).astype(int)
            per_year = act.groupby(yr).sum()
        tt = t_test_mean_return(per_year)
        shp = act.mean() / act.std() * np.sqrt(252) if act.std() > 0 else np.nan
        print(f"{h['id']+' '+h['name']:28s}{len(per_year):6d}{per_year.mean():12.2%}"
              f"{(per_year > 0).mean():6.0%}{tt['t_stat']:7.2f}{tt['p_value']:8.3f}"
              f"{shp:12.2f}{base.mean()*1e4:15.2f}")
        years = "  ".join(f"{y}:{v:+.1%}" for y, v in per_year.items())
        print(f"    {years}\n")


if __name__ == "__main__":
    main()
