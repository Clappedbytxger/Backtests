"""Strategy 0097 — Month-End Credit-ETF Flow (I0059) + Turn-of-Quarter Funding (I0057).

Batch-2 ideas from `D:\\Backtest Ideas`. Both extend the living 0075 month-/quarter-end
forced-flow mechanism into new instruments.

I0059 (#s10): the same month-end index-extension/rebalancing flow that drives 0075 in
Treasuries acts on corporate-bond indices. Long LQD/HYG over the month-end. Crucial
control: test the EXCESS return over a duration-matched Treasury (IEF/TLT) to isolate a
genuine CREDIT flow from the already-known 0075 rates flow (otherwise we just re-measure 0075).

I0057 (#s23): dealers window-dress balance sheets over quarter-end (Basel/G-SIB leverage
ratio) -> repo/funding rates spike predictably -> front-end rates move. Position in the
front-end (SHY/ZT) around quarter-end. Show the SOFR-EFFR spike exists (FRED) and test
whether the front-end price move is tradable (idea flags small magnitude -> cost wall likely).

Free data: yfinance (LQD/HYG/JNK/IEF/TLT/SHY) + FRED (SOFR/EFFR).

Run: .venv/Scripts/python.exe strategies/0097_credit_funding_flow/run.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.costs import IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.seasonal import add_calendar_features  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def fred(sid: str, start="1990-01-01") -> pd.Series:
    key = (ROOT / ".fred.key").read_text().strip()
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
           f"&api_key={key}&file_type=json&observation_start={start}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return pd.Series({pd.Timestamp(o["date"]): float(o["value"])
                      for o in d["observations"] if o["value"] != "."}).sort_index()


def monthend_mask(index: pd.DatetimeIndex, quarter_only=False) -> np.ndarray:
    feats = add_calendar_features(index)
    m = feats["tdom_from_end"].isin([0, 1]).values  # last 2 trading days
    if quarter_only:
        m = m & np.isin(index.month, [3, 6, 9, 12])
    return m


def window_events(ret: pd.Series, mask: np.ndarray) -> np.ndarray:
    """Per-contiguous-window cumulative return (window = a month-end block + roll day)."""
    pos = pd.Series(np.where(mask, 1.0, 0.0), index=ret.index).shift(1).fillna(0.0).values
    r = ret.values
    ev, i = [], 0
    while i < len(pos):
        if pos[i] != 0:
            j, cum = i, 1.0
            while j < len(pos) and pos[j] != 0:
                cum *= (1 + r[j]); j += 1
            ev.append(cum - 1); i = j
        else:
            i += 1
    return np.array(ev)


def eom_credit(tk, hedge_tk, start="2003-01-01") -> dict:
    p = get_prices(tk, start=start)
    h = get_prices(hedge_tk, start=start)
    common = p.index.intersection(h.index)
    pr = p["Close"].pct_change().reindex(common).fillna(0.0)
    hr = h["Close"].pct_change().reindex(common).fillna(0.0)
    mask = monthend_mask(common)
    sig = pd.Series(np.where(mask, 1.0, 0.0), index=common)
    bt = run_backtest(p.reindex(common).ffill(), sig, cost_model=IBKR_LIQUID_ETF)
    raw_net = bt["returns"]
    # credit excess over duration proxy: subtract hedge return on held days (beta=1 crude)
    held = bt["position"]
    excess = held * (pr - hr)
    ev_raw = window_events(pr, mask)
    ev_exc = window_events(pr - hr, mask)
    tt_raw = t_test_mean_return(pd.Series(ev_raw))
    tt_exc = t_test_mean_return(pd.Series(ev_exc))
    boot_exc = bootstrap_ci(pd.Series(ev_exc), statistic="mean", n_boot=4000)
    perm_raw = permutation_test(bt["gross_returns"], pr, held, n_perm=4000, metric="sharpe")
    return {"raw_event_bps": float(ev_raw.mean() * 1e4), "raw_t": tt_raw["t_stat"], "raw_p": tt_raw["p_value"],
            "raw_net_sharpe": ns(raw_net), "raw_perm_p": perm_raw["p_value"],
            "excess_event_bps": float(ev_exc.mean() * 1e4), "excess_t": tt_exc["t_stat"], "excess_p": tt_exc["p_value"],
            "excess_boot_ci_bps": [boot_exc["ci_low"] * 1e4, boot_exc["ci_high"] * 1e4],
            "excess_sharpe": ns(excess[excess != 0]), "n_windows": int(len(ev_raw)), "hedge": hedge_tk}


def main() -> None:
    out = {"idea_ids": ["I0059", "I0057"]}

    # ---------- I0059 month-end credit flow ----------
    print("=== I0059 month-end credit-ETF flow (raw + excess-over-rates) ===")
    out["I0059"] = {}
    for tk, hedge in [("LQD", "IEF"), ("HYG", "IEF"), ("JNK", "IEF"), ("VCIT", "IEF")]:
        try:
            r = eom_credit(tk, hedge)
            out["I0059"][tk] = r
            print(f"  {tk}: RAW {r['raw_event_bps']:+.2f}bps (p={r['raw_p']:.3f}, netSh {r['raw_net_sharpe']:+.2f}, perm {r['raw_perm_p']:.3f}) | "
                  f"EXCESS/{hedge} {r['excess_event_bps']:+.2f}bps (p={r['excess_p']:.3f}, "
                  f"boot[{r['excess_boot_ci_bps'][0]:+.1f},{r['excess_boot_ci_bps'][1]:+.1f}]) n={r['n_windows']}")
        except Exception as e:  # noqa: BLE001
            print(f"  {tk}: skip ({e})")

    # ---------- I0057 turn-of-quarter funding squeeze ----------
    print("\n=== I0057 turn-of-quarter funding squeeze (front-end) ===")
    out["I0057"] = {}
    # (a) show the SOFR-EFFR spike exists over quarter-end
    try:
        sofr, effr = fred("SOFR", "2018-01-01"), fred("EFFR", "2018-01-01")
        basis = (sofr - effr).dropna() * 100  # bp
        feats_b = add_calendar_features(basis.index)
        qe = feats_b["tdom_from_end"].isin([0]).values & np.isin(basis.index.month, [3, 6, 9, 12])
        out["I0057"]["sofr_effr_basis_qend_bps"] = float(basis[qe].mean())
        out["I0057"]["sofr_effr_basis_other_bps"] = float(basis[~qe].mean())
        print(f"  SOFR-EFFR basis: quarter-end-day {basis[qe].mean():+.2f}bp vs other {basis[~qe].mean():+.2f}bp "
              f"(spike exists: {basis[qe].mean() > basis[~qe].mean()})")
    except Exception as e:  # noqa: BLE001
        print(f"  SOFR basis: skip ({e})")

    # (b) is the front-end PRICE move tradable? SHY/ZT around quarter-end (both directions)
    for tk in ("SHY", "ZT=F"):
        try:
            p = get_prices(tk, start="2003-01-01")
            ret = p["Close"].pct_change().fillna(0.0)
            mask = monthend_mask(p.index, quarter_only=True)
            ev = window_events(ret, mask)
            tt = t_test_mean_return(pd.Series(ev))
            sig = pd.Series(np.where(mask, 1.0, 0.0), index=p.index)
            bt = run_backtest(p, sig, cost_model=IBKR_LIQUID_ETF)
            out["I0057"][tk] = {"qend_event_bps": float(ev.mean() * 1e4), "t": tt["t_stat"],
                                "p": tt["p_value"], "net_sharpe": ns(bt["returns"]), "n": int(len(ev))}
            print(f"  {tk} quarter-end long: {ev.mean()*1e4:+.2f}bps (t={tt['t_stat']:+.2f}, p={tt['p_value']:.3f}), "
                  f"net Sharpe {ns(bt['returns']):+.2f}, n={len(ev)}")
        except Exception as e:  # noqa: BLE001
            print(f"  {tk}: skip ({e})")

    # ---------- plot ----------
    fig, ax = plt.subplots(figsize=(8, 4.6))
    labs, raw, exc = [], [], []
    for tk in ("LQD", "HYG", "JNK", "VCIT"):
        if tk in out["I0059"]:
            labs.append(tk); raw.append(out["I0059"][tk]["raw_event_bps"]); exc.append(out["I0059"][tk]["excess_event_bps"])
    x = np.arange(len(labs))
    ax.bar(x - 0.2, raw, 0.4, color="steelblue", label="raw month-end")
    ax.bar(x + 0.2, exc, 0.4, color="darkorange", label="excess over IEF (credit flow)")
    ax.axhline(0, color="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(labs)
    ax.set_ylabel("month-end window return (bps)"); ax.legend(fontsize=8)
    ax.set_title("I0059: credit ETF month-end — raw vs rates-excess"); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "credit_funding.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    leads = [tk for tk in out["I0059"] if out["I0059"][tk]["excess_p"] < 0.05
             and out["I0059"][tk]["excess_boot_ci_bps"][0] > 0]
    print("\nVerdict I0059:", f"genuine credit flow in {leads}" if leads else "no genuine credit flow over rates — see REPORT.")


if __name__ == "__main__":
    main()
