"""Strategy 0067 — Seasonal calendar spreads (front vs second contract).

Idea A from NEXT-STRATEGIES-AND-LIVE-SYSTEM.md: express the catalog's
validated outright seasonal windows as long-front/short-second calendar
spreads — market-neutral within the commodity, no outright beta, and the
roll/expiry dynamics become the signal instead of an artifact.

Pre-registered hypotheses (5 = the full trial count; windows taken verbatim
from prior validated/known work, NO new window mining):
  H1 RB KW9 (0006), H2 GF KW21 (0009), H3 ZC 8.-18.12. (0030),
  H4 NG 21.9.-1.11. (0028 — outright was a roll artifact), H5 PL 18.12.-10.1. (0021).

Construction: spread return = roll-adjusted front return − roll-adjusted
second return; BOTH legs zeroed on either leg's instrument_id change
(0028/0048 lesson). UTC-Sunday Globex rows dropped (0057 lesson).

Costs: IBKR futures 2.5 bps/side for the front leg; the deferred leg is
thinner so it is padded to 4.5 bps/side -> 7 bps per side-pair, 14 bps per
spread round trip, charged on |Δposition|.

Battery: permutation vs random same-length windows per year (controls for the
spread's carry drift), bootstrap CI on the per-trade mean, IS/OOS split
2010-2018 / 2019-2026, Deflated Sharpe with n_trials=5.

Run:
    .venv/Scripts/python.exe strategies/0067_calendar_spread_seasonals/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.futures_curve import get_curve_contract  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    t_test_mean_return,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

N_TRIALS = 5
COST_PER_SIDE_PAIR = (2.5 + 4.5) / 10_000.0  # front 2.5 + padded deferred 4.5 bps
IS_END = "2018-12-31"

HYPOTHESES = [
    {"id": "H1", "root": "RB", "kind": "week", "week": 9, "hold": 5,
     "name": "Benzin KW9 (0006)"},
    {"id": "H2", "root": "GF", "kind": "week", "week": 21, "hold": 5,
     "name": "Mastrind KW21 (0009)"},
    {"id": "H3", "root": "ZC", "kind": "date", "start_md": (12, 8), "end_md": (12, 18),
     "name": "Mais Dezember (0030)"},
    {"id": "H4", "root": "NG", "kind": "date", "start_md": (9, 21), "end_md": (11, 1),
     "name": "Erdgas Herbst (0028)"},
    {"id": "H5", "root": "PL", "kind": "date", "start_md": (12, 18), "end_md": (1, 10),
     "name": "Platin Jahreswechsel (0021)"},
]


def spread_returns(root: str) -> pd.Series:
    f = get_curve_contract(f"{root}.c.0")
    s = get_curve_contract(f"{root}.c.1")
    df = pd.DataFrame({"f": f["Close"], "fid": f["instrument_id"],
                       "s": s["Close"], "sid": s["instrument_id"]}).dropna()
    df = df[df.index.dayofweek < 5]
    roll = df["fid"].ne(df["fid"].shift(1)) | df["sid"].ne(df["sid"].shift(1))
    roll.iloc[0] = False
    rf = df["f"].pct_change().where(~roll, 0.0)
    rs = df["s"].pct_change().where(~roll, 0.0)
    return (rf - rs).dropna()


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


def trade_pnl_per_year(act: pd.Series, h: dict) -> pd.Series:
    yr = act.index.year.values.copy()
    if h["kind"] == "date" and h["end_md"] < h["start_md"]:
        yr = yr - (act.index.month <= h["end_md"][0]).astype(int)
    return pd.Series(act.values, index=yr).groupby(level=0).sum()


def net_series(r: pd.Series, sig: pd.Series) -> pd.Series:
    pos = sig.shift(1).fillna(0.0)
    cost = pos.diff().abs().fillna(pos.abs()) * COST_PER_SIDE_PAIR
    return pos * r - cost


def random_window_permutation(r: pd.Series, h: dict, n_perm: int = 2000,
                              seed: int = 42) -> float:
    """p-value: observed mean trade PnL vs same-length windows at random starts.

    Placement is random per year, so the null carries the spread's full drift/
    carry — only the TIMING is tested (drift-trap lesson 0016/0017).
    """
    sig = window_mask(r.index, h).shift(1).fillna(0.0)
    act = r[sig > 0]
    obs = trade_pnl_per_year(act, h).mean()
    win_len = max(1, int(round((sig > 0).sum() / max(1, len(np.unique(act.index.year))))))
    years = r.groupby(r.index.year)
    rng = np.random.default_rng(seed)
    sums_by_year = []
    for _, yr_r in years:
        v = yr_r.values
        if len(v) <= win_len:
            continue
        # all rolling window sums for this year, choose randomly per replicate
        roll = pd.Series(v).rolling(win_len).sum().dropna().values
        sums_by_year.append(roll)
    null = np.zeros(n_perm)
    for i in range(n_perm):
        null[i] = np.mean([roll[rng.integers(len(roll))] for roll in sums_by_year])
    return float((np.sum(null >= obs) + 1) / (n_perm + 1))


def main() -> None:
    out = {"n_trials": N_TRIALS, "cost_rt_bps": COST_PER_SIDE_PAIR * 2 * 1e4,
           "hypotheses": {}}
    print("0067 — Saison-Kalenderspreads, volle Batterie (n_trials=5, Kosten 14 bps RT)\n")
    fig, axes = plt.subplots(1, len(HYPOTHESES), figsize=(4 * len(HYPOTHESES), 3.6))

    for ax, h in zip(axes, HYPOTHESES):
        r = spread_returns(h["root"])
        sig = window_mask(r.index, h)
        net = net_series(r, sig)
        pos = sig.shift(1).fillna(0.0)
        act_net = net[pos > 0]
        per_year = trade_pnl_per_year(act_net, h)

        tt = t_test_mean_return(per_year)
        p_perm = random_window_permutation(r, h)
        boot = bootstrap_ci(per_year, statistic="mean", n_boot=5000)
        sp = act_net.mean() / act_net.std() if act_net.std() > 0 else np.nan
        dsr = deflated_sharpe_ratio(observed_sharpe=sp, n_obs=len(act_net),
                                    n_trials=N_TRIALS, returns=act_net)
        is_mask = per_year.index <= int(IS_END[:4])
        res = {
            "name": h["name"], "n_trades": int(len(per_year)),
            "mean_per_trade_net": float(per_year.mean()),
            "win_rate": float((per_year > 0).mean()),
            "t_p": tt["p_value"], "perm_p": p_perm,
            "boot_ci_mean": [boot["ci_low"], boot["ci_high"]],
            "dsr": dsr["psr_deflated"],
            "is_mean": float(per_year[is_mask].mean()),
            "oos_mean": float(per_year[~is_mask].mean()),
            "per_year": {int(k): float(v) for k, v in per_year.items()},
        }
        out["hypotheses"][h["id"]] = res
        print(f"{h['id']} {h['name']}")
        print(f"   n={res['n_trades']}  mean/Trade(net) {res['mean_per_trade_net']:+.2%}  "
              f"win {res['win_rate']:.0%}  t-p {tt['p_value']:.3f}  PERM p {p_perm:.3f}")
        print(f"   Bootstrap-KI Mean [{boot['ci_low']:+.2%}, {boot['ci_high']:+.2%}]  "
              f"DSR {dsr['psr_deflated']:.3f}  IS {res['is_mean']:+.2%} / OOS {res['oos_mean']:+.2%}\n")

        eq = (1 + net).cumprod()
        ax.plot(eq.index, eq.values, lw=0.9)
        ax.set_title(f"{h['id']} {h['root']} (perm p={p_perm:.2f})", fontsize=9)
        ax.grid(alpha=0.3)

    fig.suptitle("0067: Saison-Fenster als Front/Second-Spreads — Netto-Equity (nur aktive Tage bewegen)")
    fig.tight_layout()
    fig.savefig(RESULTS / "spread_equity_panels.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"results -> {RESULTS}")


if __name__ == "__main__":
    main()
