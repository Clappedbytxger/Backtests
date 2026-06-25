"""Strategy 0081 — Calendar & inter-commodity spreads (handoff group I0001-I0007).

Roadmap-top idea group from `D:\\Backtest Ideas` (#s01/#s14). A spread is
roll-clean by construction (the year-to-year roll happens OUTSIDE the season
window) and beta-neutral within the commodity/complex — it isolates the seasonal
supply/demand transition without the direction/roll artifacts that killed the
outright versions (0028/0029, 0080).

Spreads (dollar-neutral RETURN = long-leg %ret minus short-leg %ret, built from
single-contract chains via quantlab.futures_chain, Databento daily 2010-2026):

  I0001 Corn old/new   : long Jul (ZCN) / short Dec (ZCZ),  window 01 Dec -> 15 Jun
  I0003 NatGas winter  : long Mar (NGH) / short Apr (NGJ),  window 01 Oct -> 20 Feb
  I0004 RBOB driving   : long Jul (RBN) / short Nov (RBX),  window 01 Feb -> 20 May
  I0002 Soy crush      : long 0.5 ZM + 0.5 ZL - 1.0 ZS,     window 01 Oct -> 31 Jan
  I0007 3-2-1 crack    : long (2 RB + 1 HO)/3 - 1.0 CL,     window 15 Feb -> 25 May

Windows are pre-registered from the briefs (#s01/#s14) before looking at results.
THE test is the permutation: does the seasonal window beat random same-length
windows on the SAME continuous spread-return series? (controls any residual drift).

Run:
    .venv/Scripts/python.exe strategies/0081_calendar_spreads/run.py
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

from quantlab.futures_chain import calendar_spread_return, matched_month_spread_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(252)
COST_BPS = 4.0  # per-side, two legs -> ~8 bps round trip on the spread; padded for futures
rng = np.random.default_rng(11)


def in_window(index: pd.DatetimeIndex, start_md, end_md) -> np.ndarray:
    """Boolean: date in the [start_md, end_md] window each year (wraps year-end)."""
    md = np.array([(d.month, d.day) for d in index])
    s, e = start_md, end_md
    if s <= e:
        return np.array([s <= (m, dd) <= e for m, dd in md])
    return np.array([(m, dd) >= s or (m, dd) <= e for m, dd in md])


def perm_window(spread_ret: pd.Series, mask: np.ndarray, n: int = 5000) -> dict:
    """Permutation: window mean vs random same-length contiguous windows."""
    r = spread_ret.values
    k = int(mask.sum())
    obs = float(r[mask].mean())
    N = len(r)
    null = np.empty(n)
    for i in range(n):
        st = rng.integers(0, N - k)
        null[i] = r[st:st + k].mean()
    p = float((null >= obs).mean())
    return {"obs_mean_bps": obs * 1e4, "perm_p": p, "k_days": k}


def evaluate(name: str, spread_ret: pd.Series, start_md, end_md) -> dict:
    spread_ret = spread_ret.dropna()
    mask = in_window(spread_ret.index, start_md, end_md)
    win = spread_ret[mask]
    # net: charge cost on the ~1 entry + 1 exit per year (turnover at window edges)
    pos = pd.Series(mask.astype(float), index=spread_ret.index)
    turns = int(pos.diff().abs().sum() / 2)  # entries
    gross_ann = win.mean() * 252
    net_ret_series = spread_ret.copy()
    # subtract cost at each window entry/exit day
    edges = pos.diff().abs() > 0
    cost = edges.astype(float) * (COST_BPS / 1e4)
    net_win = (spread_ret - cost)[mask]
    sharpe = float(win.mean() / win.std() * ANN) if win.std() else float("nan")
    net_sharpe = float(net_win.mean() / net_win.std() * ANN) if net_win.std() else float("nan")
    # per-year window total return
    yr = win.groupby(win.index.year if start_md <= end_md else
                     ((win.index + pd.offsets.MonthEnd(0)).year)).sum()
    perm = perm_window(spread_ret, mask)
    # bootstrap of the window daily mean
    wv = win.values
    boot = np.array([rng.choice(wv, len(wv)).mean() for _ in range(5000)])
    ci = (float(np.percentile(boot, 2.5) * 1e4), float(np.percentile(boot, 97.5) * 1e4))
    return {
        "name": name, "window": [list(start_md), list(end_md)],
        "n_days_in_window": int(mask.sum()), "years": int(len(yr)),
        "gross_sharpe": sharpe, "net_sharpe": net_sharpe,
        "win_mean_bps_day": float(win.mean() * 1e4),
        "gross_ann_pct": float(gross_ann * 100),
        "perm_p": perm["perm_p"], "boot_mean_ci_bps": list(ci),
        "pct_years_positive": float((yr > 0).mean()),
        "year_returns_pct": {str(int(k)): float(v * 100) for k, v in yr.items()},
        "spread_ret": spread_ret, "mask": mask,
    }


def main() -> None:
    out: dict = {"idea_group": "I0001-I0007", "cost_bps_per_side": COST_BPS}

    specs = []
    # I0001 corn old/new
    specs.append(("I0001 Corn Jul/Dec", calendar_spread_return("ZC", "N", "Z"), (12, 1), (6, 15)))
    # I0003 NG winter Mar/Apr (widow maker)
    specs.append(("I0003 NatGas Mar/Apr", calendar_spread_return("NG", "H", "J"), (10, 1), (2, 20)))
    # I0004 RBOB summer/winter Jul/Nov
    specs.append(("I0004 RBOB Jul/Nov", calendar_spread_return("RB", "N", "X"), (2, 1), (5, 20)))
    # I0002 soy crush (products minus beans) — roll-clean matched March delivery, capture Sep->Feb
    specs.append(("I0002 Soy crush",
                  matched_month_spread_return([("ZM", 0.5), ("ZL", 0.5), ("ZS", -1.0)], "H", (9, 1), (2, 28)),
                  (10, 1), (1, 31)))
    # I0007 3-2-1 crack — roll-clean matched July delivery, capture Jan->Jun
    specs.append(("I0007 3-2-1 crack",
                  matched_month_spread_return([("RB", 2/3), ("HO", 1/3), ("CL", -1.0)], "N", (1, 1), (6, 30)),
                  (2, 15), (5, 25)))

    out["spreads"] = {}
    print(f"{'spread':22}{'years':>6}{'gSharpe':>9}{'netShrp':>9}{'win%yr':>8}{'perm_p':>9}{'bootCI(bps)':>20}")
    for name, sr, smd, emd in specs:
        if len(sr) < 200:
            print(f"{name:22}  insufficient data ({len(sr)})"); continue
        ev = evaluate(name, sr, smd, emd)
        out["spreads"][name] = {k: v for k, v in ev.items() if k not in ("spread_ret", "mask")}
        print(f"{name:22}{ev['years']:>6}{ev['gross_sharpe']:>9.2f}{ev['net_sharpe']:>9.2f}"
              f"{ev['pct_years_positive']*100:>7.0f}%{ev['perm_p']:>9.3f}"
              f"   [{ev['boot_mean_ci_bps'][0]:+.2f},{ev['boot_mean_ci_bps'][1]:+.2f}]")

    # plot: equity of each spread's windowed return
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for name, sr, smd, emd in specs:
        if len(sr) < 200:
            continue
        ev = evaluate(name, sr, smd, emd)
        wr = ev["spread_ret"].copy()
        wr[~ev["mask"]] = 0.0
        ax[0].plot((1 + wr).cumprod(), label=name.split(" ", 1)[1] if " " in name else name)
    ax[0].set_title("Windowed spread equity (gross, in-window only)"); ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3); ax[0].set_yscale("log")
    names = list(out["spreads"].keys())
    pvals = [out["spreads"][n]["perm_p"] for n in names]
    ax[1].barh(range(len(names)), pvals, color=["seagreen" if p < 0.05 else "grey" for p in pvals], edgecolor="k")
    ax[1].axvline(0.05, color="red", ls="--", lw=1); ax[1].set_yticks(range(len(names)))
    ax[1].set_yticklabels([n.split(" ", 1)[0] for n in names]); ax[1].set_xlabel("permutation p")
    ax[1].set_title("Window vs random-timing permutation"); ax[1].grid(alpha=0.3, axis="x")
    fig.tight_layout(); fig.savefig(RESULTS / "calendar_spreads.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    leads = [n for n in out["spreads"] if out["spreads"][n]["perm_p"] < 0.05
             and out["spreads"][n]["boot_mean_ci_bps"][0] > 0]
    print(f"\nLeads (perm p<0.05 AND boot-CI>0): {leads if leads else 'none'}")


if __name__ == "__main__":
    main()
