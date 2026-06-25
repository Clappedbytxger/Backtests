"""Strategy 0078 — Treasury Auction Concession (pre-auction short).

Idea I0009 from the `D:\\Backtest Ideas` handoff (source #s03/#s18: Sigaux ECB
WP2208; Somogyi FRBSF). Claim: ahead of US Treasury auctions, secondary-market
prices fall predictably (dealers demand a price "concession" to absorb supply,
the "inverted V"), then recover. Short the maturity-matched future in the days
before the auction, cover/long after.

#s18 caveat: magnitude is SMALL (~2.4 bps yield on the Italian-BTP sample) ->
cost likely binds outright; the cleaner expression may be an RV/spread (10y vs
30y). We therefore (a) run the event study to see if the concession even exists
on US futures, (b) test the outright short net of cost, (c) note the RV path.

Auction calendar: TreasuryDirect API (free, no key). 10-year Note auctions
(original + reopenings) and 30-year Bond auctions, 2000+.

Pre-registered windows: pre-auction short [T-5 .. T-1] (concession builds from the
dealer meeting ~5 business days out + size announcement 2-4 days out), post-auction
long [T0 .. T+2] (reversal). Permutation against random non-auction day blocks.

Data: ZN=F (10y future) / ZB=F (30y future) — direct but quarterly roll caveat
(lesson 0028/0029); IEF/TLT (ETF, roll-clean cross-check). Work in price returns
(price up = yield down -> concession = price falls pre-auction).

Run:
    .venv/Scripts/python.exe strategies/0078_treasury_auction/run.py
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

from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(252)
PRE = 5    # short window [T-PRE .. T-1]
POST = 2   # long window  [T0 .. T+POST]
TERMS_10Y = {"10-Year", "9-Year 11-Month", "9-Year 10-Month", "9-Year 9-Month"}
TERMS_30Y = {"30-Year", "29-Year 11-Month", "29-Year 10-Month", "29-Year 9-Month"}


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def fetch_auctions(security_type: str) -> list[dict]:
    cache = RESULTS / f"auctions_{security_type.lower()}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    url = f"https://www.treasurydirect.gov/TA_WS/securities/search?type={security_type}&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=60))
    cache.write_text(json.dumps(data))
    return data


def auction_dates(security_type: str, terms: set[str], start: str = "2000-01-01") -> pd.DatetimeIndex:
    data = fetch_auctions(security_type)
    dates = sorted({x["auctionDate"][:10] for x in data
                    if x["securityTerm"] in terms and x["auctionDate"][:10] >= start})
    return pd.DatetimeIndex(pd.to_datetime(dates))


def map_to_index(auctions: pd.DatetimeIndex, index: pd.DatetimeIndex) -> np.ndarray:
    """Position in `index` of each auction (the trading day on/after auctionDate)."""
    locs = []
    for d in auctions:
        loc = index.searchsorted(d)
        if 0 <= loc < len(index):
            locs.append(loc)
    return np.array(sorted(set(locs)))


def event_study(prices: pd.DataFrame, auctions: pd.DatetimeIndex) -> dict:
    ret = prices["Close"].pct_change().fillna(0.0).values
    idx = prices.index
    locs = map_to_index(auctions, idx)
    n = len(idx)
    pre, post, t0 = [], [], []
    rel = {k: [] for k in range(-PRE, POST + 1)}
    for a in locs:
        if a - PRE < 0 or a + POST >= n:
            continue
        pre.append(float(np.prod(1 + ret[a - PRE:a]) - 1))     # T-PRE..T-1
        post.append(float(np.prod(1 + ret[a:a + POST + 1]) - 1))  # T0..T+POST
        t0.append(float(ret[a]))
        for k in range(-PRE, POST + 1):
            rel[k].append(float(ret[a + k]))
    return {"pre": np.array(pre), "post": np.array(post), "t0": np.array(t0),
            "rel_mean_bps": {k: float(np.mean(v) * 1e4) for k, v in rel.items()},
            "locs": locs, "n_events": len(pre)}


def short_signal(index: pd.DatetimeIndex, locs: np.ndarray) -> pd.Series:
    """-1 on the PRE days before each auction (concession short)."""
    s = np.zeros(len(index))
    for a in locs:
        s[max(0, a - PRE):a] = -1.0
    return pd.Series(s, index=index, name="auction_short")


def main() -> None:
    out: dict = {"idea_id": "I0009", "pre": PRE, "post": POST}

    a10 = auction_dates("Note", TERMS_10Y)
    a30 = auction_dates("Bond", TERMS_30Y)
    print(f"10y Note auctions 2000+: {len(a10)} | 30y Bond auctions: {len(a30)}\n")

    markets = []
    for tk, label, auc, cost in [("ZN=F", "10y future", a10, IBKR_FUTURES),
                                 ("ZB=F", "30y future", a30, IBKR_FUTURES),
                                 ("IEF", "10y ETF", a10, IBKR_LIQUID_ETF),
                                 ("TLT", "20y+ ETF", a30, IBKR_LIQUID_ETF)]:
        try:
            p = get_prices(tk, start="2000-01-01")
            if (p["Close"] <= 0).any():
                raise ValueError("non-positive price")
            markets.append((tk, label, p, auc, cost))
        except Exception as e:  # noqa: BLE001
            print(f"{label}: skipped ({e})")

    out["markets"] = {}
    for tk, label, p, auc, cost in markets:
        es = event_study(p, auc)
        # pre-auction concession = pre returns negative; post reversal = post positive
        tt_pre = t_test_mean_return(pd.Series(es["pre"]))
        tt_post = t_test_mean_return(pd.Series(es["post"]))
        # tradable short over PRE window, net of cost
        locs = es["locs"]
        sig = short_signal(p.index, locs)
        bt = run_backtest(p, sig, cost_model=cost)
        gross, net = bt["gross_returns"], bt["returns"]
        ar = p["Close"].pct_change().fillna(0.0)
        perm = permutation_test(gross, ar, bt["position"], n_perm=5000, metric="sharpe")
        boot_pre = bootstrap_ci(pd.Series(es["pre"]), statistic="mean", n_boot=5000)
        rec = {
            "label": label, "n_events": es["n_events"],
            "pre_mean_bps": float(es["pre"].mean() * 1e4), "pre_t": tt_pre["t_stat"], "pre_p": tt_pre["p_value"],
            "post_mean_bps": float(es["post"].mean() * 1e4), "post_t": tt_post["t_stat"], "post_p": tt_post["p_value"],
            "t0_mean_bps": float(es["t0"].mean() * 1e4),
            "short_gross_sharpe": net_sharpe(gross), "short_net_sharpe": net_sharpe(net),
            "short_net_cagr_pct": float(compute_metrics(net)["cagr"] * 100),
            "short_perm_p": perm["p_value"],
            "pre_mean_boot_ci_bps": [boot_pre["ci_low"] * 1e4, boot_pre["ci_high"] * 1e4],
            "rel_mean_bps": es["rel_mean_bps"],
        }
        out["markets"][tk] = rec
        print(f"=== {label} ({tk}, {es['n_events']} events) ===")
        print(f"  pre [T-{PRE}..T-1] mean {rec['pre_mean_bps']:+.2f}bps (t={rec['pre_t']:+.2f}, p={rec['pre_p']:.3f})  "
              f"[concession = NEGATIVE]")
        print(f"  post [T0..T+{POST}] mean {rec['post_mean_bps']:+.2f}bps (t={rec['post_t']:+.2f}, p={rec['post_p']:.3f})  "
              f"[reversal = POSITIVE]")
        print(f"  pre-window short: gross Sharpe {rec['short_gross_sharpe']:+.2f}, net {rec['short_net_sharpe']:+.2f}, "
              f"perm p={rec['short_perm_p']:.3f}, CAGR {rec['short_net_cagr_pct']:+.1f}%")
        print(f"  rel-day mean (bps): " + " ".join(f"{k:+d}:{v:+.1f}" for k, v in rec["rel_mean_bps"].items()))
        print()

    # ---- RV cross-check: 10y vs 30y around 10y auctions (the #s18 suggestion) ----
    try:
        ief = get_prices("IEF", start="2002-01-01")
        tlt = get_prices("TLT", start="2002-01-01")
        common = ief.index.intersection(tlt.index)
        # duration-neutral-ish: TLT ~3x IEF duration; spread = IEF_ret - (1/3)*TLT_ret is messy.
        # Simpler RV: long IEF / short TLT (curve) over pre-window of 10y auctions.
        ief_ret = ief["Close"].pct_change().reindex(common).fillna(0.0)
        tlt_ret = tlt["Close"].pct_change().reindex(common).fillna(0.0)
        rv_ret = ief_ret - tlt_ret  # 10y outperforms 30y?
        locs = map_to_index(a10, common)
        pre_rv = []
        rv_arr = rv_ret.values
        for a in locs:
            if a - PRE >= 0:
                pre_rv.append(float(np.sum(rv_arr[a - PRE:a])))  # additive for spread
        pre_rv = np.array(pre_rv)
        tt_rv = t_test_mean_return(pd.Series(pre_rv))
        out["rv_10y_vs_30y_pre"] = {"mean_bps": float(pre_rv.mean() * 1e4),
                                    "t": tt_rv["t_stat"], "p": tt_rv["p_value"], "n": len(pre_rv)}
        print(f"RV (IEF-TLT) pre-10y-auction mean {pre_rv.mean()*1e4:+.2f}bps (t={tt_rv['t_stat']:+.2f}, p={tt_rv['p_value']:.3f}, n={len(pre_rv)})")
    except Exception as e:  # noqa: BLE001
        out["rv_10y_vs_30y_pre"] = {"error": str(e)}

    # ---- plot: event-study average path ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for tk in ("ZN=F", "ZB=F"):
        if tk in out["markets"]:
            rel = out["markets"][tk]["rel_mean_bps"]
            ks = sorted(int(k) for k in rel)
            cum = np.cumsum([rel[k] for k in ks])
            ax[0].plot(ks, cum, marker="o", label=out["markets"][tk]["label"])
    ax[0].axvline(0, color="k", ls="--", lw=1, label="auction day")
    ax[0].axhline(0, color="grey", lw=0.6)
    ax[0].set_xlabel("trading day relative to auction"); ax[0].set_ylabel("cumulative mean return (bps)")
    ax[0].set_title("Auction concession 'inverted V'?\n(down into auction, up after)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    labs = [out["markets"][tk]["label"] for tk in out["markets"]]
    pres = [out["markets"][tk]["pre_mean_bps"] for tk in out["markets"]]
    posts = [out["markets"][tk]["post_mean_bps"] for tk in out["markets"]]
    x = np.arange(len(labs))
    ax[1].bar(x - 0.2, pres, 0.4, color="firebrick", label=f"pre [T-{PRE}..T-1]")
    ax[1].bar(x + 0.2, posts, 0.4, color="seagreen", label=f"post [T0..T+{POST}]")
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_xticks(x); ax[1].set_xticklabels(labs, rotation=15, ha="right")
    ax[1].set_ylabel("mean window return (bps)"); ax[1].legend(fontsize=8)
    ax[1].set_title("Pre (expect <0) vs post (expect >0)"); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(RESULTS / "treasury_auction.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    zn = out["markets"].get("ZN=F", {})
    passes = (zn.get("pre_p", 1) < 0.05 and zn.get("pre_mean_bps", 0) < 0
              and zn.get("short_net_sharpe", -1) > 0 and zn.get("short_perm_p", 1) < 0.05)
    print("\nVerdict:", "concession exists & tradable net — lead."
          if passes else "see REPORT — concession weak/not tradable net of cost.")


if __name__ == "__main__":
    main()
