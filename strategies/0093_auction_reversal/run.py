"""Strategy 0093 — Post-Auction Concession-Reversal + Vol/Size sizing overlay.

Batch-2 ideas I0054 + I0055 from `D:\\Backtest Ideas` (source #s21 Lou/Yan/Zhang
2013 JFE; #s03 Sigaux). Mirror leg of the 0078 winner.

I0054 (Post-Auction Reversal, LONG): the dealer concession that pushes Treasury
prices DOWN before an auction reverts AFTER allotment (dealers place the absorbed
supply, the liquidity-premium pressure unwinds). So go LONG the maturity-matched
instrument at the auction-day close (T0, after the result) and exit at T+2. This is
the economic mirror of the 0078 short, on a DIFFERENT day-block -> potentially
uncorrelated, diversifying the 0091 book.

  0078 already found (event study): post-auction [T0..T+2] reversal is significant
  at the 10y (IEF +9.3 bps, p=0.037), weak at the 30y. So the reversal lives at the
  SHORT end, opposite to where the concession-short lives (30y). We test it properly
  as a tradable long net of cost, with the drift-trap permutation.

I0055 (Vol/Size-conditioned sizing): the concession scales with dealer inventory
risk -> bigger when rate-vol (MOVE) is high and issuance is large. Overlay on the
0078 SHORT: does trading only the top-MOVE / top-size tercile, or vol-scaling, lift
OOS Sharpe vs the unconditioned short? (Roadmap "Idea E": sizing a proven leg.)

Free data only: TreasuryDirect auction calendar (cached from 0078), yfinance
(ZN=F/ZB=F/IEF/TLT), FRED (^MOVE proxy via FRED 'BAMLC0A0CM'? no -> use FRED MOVE
not available; use realized-vol of the future as the vol proxy + TreasuryDirect
'offeringAmount' for size). Auction size comes from the cached TreasuryDirect JSON.

Run: .venv/Scripts/python.exe strategies/0093_auction_reversal/run.py
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

from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
AUC_CACHE = ROOT / "strategies/0078_treasury_auction/results"

ANN = np.sqrt(252)
POST = 2  # long window: enter T0 close, exit T+POST close (earn ret[a+1..a+POST])
TERMS_10Y = {"10-Year", "9-Year 11-Month", "9-Year 10-Month", "9-Year 9-Month"}
TERMS_30Y = {"30-Year", "29-Year 11-Month", "29-Year 10-Month", "29-Year 9-Month"}


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def load_auctions(security_type: str, terms: set[str], start="2000-01-01"):
    """Return (dates, size_by_date) from the cached TreasuryDirect JSON."""
    cache = AUC_CACHE / f"auctions_{security_type.lower()}.json"
    data = json.loads(cache.read_text())
    rows = {}
    for x in data:
        if x["securityTerm"] in terms and x["auctionDate"][:10] >= start:
            d = x["auctionDate"][:10]
            amt = x.get("offeringAmount") or x.get("totalAccepted") or ""
            try:
                rows[d] = float(amt) if amt else np.nan
            except (ValueError, TypeError):
                rows[d] = np.nan
    dates = pd.DatetimeIndex(pd.to_datetime(sorted(rows)))
    size = pd.Series({pd.Timestamp(d): rows[d] for d in rows}).sort_index()
    return dates, size


def map_to_index(auctions: pd.DatetimeIndex, index: pd.DatetimeIndex) -> np.ndarray:
    locs = []
    for d in auctions:
        loc = index.searchsorted(d)
        if 0 <= loc < len(index):
            locs.append(loc)
    return np.array(sorted(set(locs)))


def reversal_event_study(prices: pd.DataFrame, locs: np.ndarray) -> dict:
    """Long entered at T0 close -> earns ret[a+1..a+POST]. Also report rel path."""
    ret = prices["Close"].pct_change().fillna(0.0).values
    n = len(ret)
    post, rel = [], {k: [] for k in range(-1, POST + 2)}
    for a in locs:
        if a + POST + 1 >= n or a - 1 < 0:
            continue
        post.append(float(np.prod(1 + ret[a + 1:a + POST + 1]) - 1))  # T0c->T+POSTc
        for k in range(-1, POST + 2):
            rel[k].append(float(ret[a + k]))
    return {"post": np.array(post),
            "rel_mean_bps": {k: float(np.mean(v) * 1e4) for k, v in rel.items()},
            "n": len(post)}


def long_signal(index: pd.DatetimeIndex, locs: np.ndarray) -> pd.Series:
    """+1 on days [T0 .. T0+POST-1] so the shifted position earns ret[a+1..a+POST]."""
    s = np.zeros(len(index))
    for a in locs:
        s[a:min(len(index), a + POST)] = 1.0
    return pd.Series(s, index=index, name="auction_reversal_long")


def split_sharpe(ret: pd.Series, cut="2014-01-01") -> dict:
    return {"is": ns(ret[ret.index < cut]), "oos": ns(ret[ret.index >= cut]),
            "ex2022": ns(ret[(ret.index < "2022-01-01") | (ret.index >= "2023-01-01")])}


def main() -> None:
    out = {"idea_ids": ["I0054", "I0055"], "post_window": POST}

    a10, size10 = load_auctions("Note", TERMS_10Y)
    a30, size30 = load_auctions("Bond", TERMS_30Y)
    print(f"10y auctions: {len(a10)} | 30y auctions: {len(a30)}\n")

    # ---------- I0054: post-auction reversal LONG ----------
    out["I0054"] = {}
    markets = [("IEF", "10y ETF", a10, IBKR_LIQUID_ETF),
               ("TLT", "30y ETF", a30, IBKR_LIQUID_ETF),
               ("ZN=F", "10y fut", a10, IBKR_FUTURES),
               ("ZB=F", "30y fut", a30, IBKR_FUTURES)]
    for tk, label, auc, cost in markets:
        try:
            p = get_prices(tk, start="2000-01-01")
            if (p["Close"] <= 0).any():
                raise ValueError("non-positive price")
        except Exception as e:  # noqa: BLE001
            print(f"{label}: skipped ({e})")
            continue
        locs = map_to_index(auc, p.index)
        es = reversal_event_study(p, locs)
        tt = t_test_mean_return(pd.Series(es["post"]))
        sig = long_signal(p.index, locs)
        bt = run_backtest(p, sig, cost_model=cost)
        gross, net = bt["gross_returns"], bt["returns"]
        ar = p["Close"].pct_change().fillna(0.0)
        perm = permutation_test(gross, ar, bt["position"], n_perm=5000, metric="sharpe")
        boot = bootstrap_ci(pd.Series(es["post"]), statistic="mean", n_boot=5000)
        rec = {"label": label, "n_events": es["n"],
               "post_mean_bps": float(es["post"].mean() * 1e4),
               "post_t": tt["t_stat"], "post_p": tt["p_value"],
               "post_boot_ci_bps": [boot["ci_low"] * 1e4, boot["ci_high"] * 1e4],
               "long_gross_sharpe": ns(gross), "long_net_sharpe": ns(net),
               "long_net_cagr_pct": float(compute_metrics(net)["cagr"] * 100),
               "long_perm_p": perm["p_value"],
               "splits": split_sharpe(net), "rel_mean_bps": es["rel_mean_bps"]}
        out["I0054"][tk] = rec
        print(f"=== {label} ({tk}, {es['n']} events) — POST-AUCTION LONG ===")
        print(f"  post [T0c..T+{POST}c] mean {rec['post_mean_bps']:+.2f}bps "
              f"(t={rec['post_t']:+.2f}, p={rec['post_p']:.3f}, "
              f"boot95 [{rec['post_boot_ci_bps'][0]:+.1f},{rec['post_boot_ci_bps'][1]:+.1f}])")
        print(f"  long: gross {rec['long_gross_sharpe']:+.2f}, net {rec['long_net_sharpe']:+.2f}, "
              f"perm p={rec['long_perm_p']:.3f}, CAGR {rec['long_net_cagr_pct']:+.1f}%, "
              f"IS/OOS {rec['splits']['is']:+.2f}/{rec['splits']['oos']:+.2f}")
        print(f"  rel path bps: " + " ".join(f"{k:+d}:{v:+.1f}" for k, v in rec["rel_mean_bps"].items()))
        print()

    # ---------- I0055: vol/size conditioning of the 0078 SHORT (30y/TLT) ----------
    # Concession should be larger when rate-vol high and issuance large.
    print("--- I0055: vol/size-conditioned 30y concession SHORT (TLT) ---")
    PRE = 5
    tlt = get_prices("TLT", start="2002-01-01")
    locs30 = map_to_index(a30, tlt.index)
    ret = tlt["Close"].pct_change().fillna(0.0).values
    # realized vol proxy: 21d std of TLT returns, known at T-PRE (use value at a-PRE)
    rv = pd.Series(ret, index=tlt.index).rolling(21).std()
    size30_idx = size30.reindex(tlt.index, method="ffill")
    # per-event concession (pre short return) + conditioning vars known pre-window
    rows = []
    for a in locs30:
        if a - PRE < 0:
            continue
        pre_short = -(np.prod(1 + ret[a - PRE:a]) - 1)  # SHORT pnl = -(price move)
        vol = rv.iloc[a - PRE] if a - PRE < len(rv) else np.nan
        sz = size30_idx.iloc[a] if a < len(size30_idx) else np.nan
        rows.append((tlt.index[a], pre_short, vol, sz))
    ev = pd.DataFrame(rows, columns=["date", "short_pnl", "vol", "size"]).set_index("date").dropna(subset=["short_pnl"])
    # terciles on conditioning vars (walk-forward expanding to avoid look-ahead)
    def tercile_means(col):
        d = ev.dropna(subset=[col]).copy()
        # expanding rank: at each event, rank vs PAST events only
        hi, lo = [], []
        for i in range(len(d)):
            past = d[col].iloc[:i]
            if len(past) < 20:
                continue
            q33, q67 = past.quantile(0.33), past.quantile(0.67)
            v = d[col].iloc[i]
            if v >= q67:
                hi.append(d["short_pnl"].iloc[i])
            elif v <= q33:
                lo.append(d["short_pnl"].iloc[i])
        return (float(np.mean(hi) * 1e4) if hi else np.nan,
                float(np.mean(lo) * 1e4) if lo else np.nan, len(hi), len(lo))
    vh, vl, nvh, nvl = tercile_means("vol")
    sh, sl, nsh, nsl = tercile_means("size")
    out["I0055"] = {
        "all_short_mean_bps": float(ev["short_pnl"].mean() * 1e4), "n": len(ev),
        "vol_hi_bps": vh, "vol_lo_bps": vl, "n_vol_hi": nvh, "n_vol_lo": nvl,
        "size_hi_bps": sh, "size_lo_bps": sl, "n_size_hi": nsh, "n_size_lo": nsl}
    print(f"  all events: {out['I0055']['all_short_mean_bps']:+.1f}bps (n={len(ev)})")
    print(f"  vol  hi-tercile {vh:+.1f} (n={nvh}) vs lo {vl:+.1f} (n={nvl})  [expect hi > lo]")
    print(f"  size hi-tercile {sh:+.1f} (n={nsh}) vs lo {sl:+.1f} (n={nsl})  [expect hi > lo]")

    # ---------- plot ----------
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for tk in ("IEF", "TLT"):
        if tk in out["I0054"]:
            rel = out["I0054"][tk]["rel_mean_bps"]
            ks = sorted(int(k) for k in rel)
            cum = np.cumsum([rel[k] for k in ks])
            ax[0].plot(ks, cum, marker="o", label=out["I0054"][tk]["label"])
    ax[0].axvline(0, color="k", ls="--", lw=1, label="auction day T0")
    ax[0].axhline(0, color="grey", lw=0.6)
    ax[0].set_xlabel("trading day rel. to auction"); ax[0].set_ylabel("cum mean ret (bps)")
    ax[0].set_title("Post-auction reversal (expect UP after T0)"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    cats = ["all", "vol-hi", "vol-lo", "size-hi", "size-lo"]
    vals = [out["I0055"]["all_short_mean_bps"], vh, vl, sh, sl]
    ax[1].bar(cats, vals, color=["grey", "firebrick", "salmon", "navy", "skyblue"])
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_ylabel("30y concession short pnl (bps)")
    ax[1].set_title("I0055: concession by vol/size tercile"); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "auction_reversal.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    # verdict
    ief = out["I0054"].get("IEF", {})
    lead = (ief.get("post_p", 1) < 0.05 and ief.get("long_net_sharpe", -1) > 0
            and ief.get("long_perm_p", 1) < 0.05 and ief.get("post_boot_ci_bps", [0, 0])[0] > 0)
    print("\nVerdict I0054:", "reversal tradable net & timing beats random — lead."
          if lead else "see REPORT — reversal weak/cost-eaten or not vs random.")


if __name__ == "__main__":
    main()
