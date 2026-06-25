"""Strategy 0092 — S&P-500 core + switch-into-trade overlay book (0020 model, EUR2000).

Robin's request: be long the S&P 500 by default; whenever a discrete edge-trade
fires, SELL everything and put 100% into that trade; when it ends, go back to the
S&P 500 (exactly the 0010/0020/0036 overlay model, priority = one trade at a time).

Switch legs (priority order = strongest per-trade edge first; seasonals are mostly
disjoint, the rates legs fire monthly):
  1 Benzin KW9 (RB, long)      2 Mais Dez (ZC, long)     3 Baumwolle (CT, long)
  4 Mastrind KW21 (GF, long)   5 Platin Jahreswechsel (PL, long)
  6 Auction-Short (TLT, SHORT, ~5 td before each 30y auction)
  7 EOM-Treasury (TLT, long, last+first trading day of month)
Default (no leg active): LONG S&P 500 (SPY).

The always-on overlays (VIX-carry 90%, USD-regime 48%, Wheat-RV 56%) do NOT fit a
"switch the whole account into one trade" model — they would replace the equity
core most of the time — so they are deliberately excluded here (they are parallel
sleeves, see 0091). Turn-of-Month and Pre-FOMC are equity-LONG timing edges that
are redundant when the core is already 100% long S&P, so they are absorbed by the
core and not switched into.

Reports brutto (no cost) + netto (switch costs) + all key stats vs buy&hold S&P.
Sized to a EUR 2000 account (return-space metrics apply directly; instrument note
+ ETF proxies for the small account at the end).

Run: .venv/Scripts/python.exe strategies/0092_sp500_overlay_book/run.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics
from quantlab.seasonal import event_signal, date_window_signal, turn_of_month_signal
RESULTS = Path(__file__).resolve().parent / "results"; RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)
SWITCH_BPS = 3.0   # per side; a switch = sell old + buy new = 2 sides
ACCOUNT_EUR = 2000.0


def auction_held_mask(index):
    terms = {"30-Year", "29-Year 11-Month", "29-Year 10-Month", "29-Year 9-Month"}
    data = json.loads((ROOT / "strategies/0078_treasury_auction/results/auctions_bond.json").read_text())
    auc = pd.DatetimeIndex(sorted({x["auctionDate"][:10] for x in data if x["securityTerm"] in terms}))
    s = np.zeros(len(index))
    for d in auc:
        a = index.searchsorted(d)
        if 0 <= a < len(index):
            s[max(0, a-5):a] = 1.0
    return pd.Series(s, index=index)  # decision-time short window


def main():
    out = {}
    start = "2002-08-01"
    px = {t: get_prices(t, start=start)["Close"] for t in ["SPY", "RB=F", "GF=F", "PL=F", "CT=F", "ZC=F", "TLT"]}
    df = pd.DataFrame(px).dropna()
    idx = df.index
    rets = df.pct_change().fillna(0.0)

    # priority-ordered legs: (id, instrument, direction, decision-time signal)
    legs = [
        ("benzin",   "RB=F", +1, event_signal(idx, 9, 5)),
        ("mais",     "ZC=F", +1, date_window_signal(idx, (12, 8), (12, 18))),
        ("baumwolle","CT=F", +1, date_window_signal(idx, (11, 21), (12, 29))),
        ("mastrind", "GF=F", +1, event_signal(idx, 21, 5)),
        ("platin",   "PL=F", +1, date_window_signal(idx, (12, 18), (1, 10))),
        ("auction",  "TLT",  -1, auction_held_mask(idx)),
        ("eom",      "TLT",  +1, turn_of_month_signal(idx, 2, 0)),
    ]
    # held (T+1): position decided at prior close
    held = {lid: (sig.shift(1).fillna(0.0) > 0) for lid, _, _, sig in legs}

    # priority resolve -> per-day winning leg label + instrument return
    label = pd.Series("SPY", index=idx, dtype=object)
    gross = rets["SPY"].copy()
    taken = pd.Series(False, index=idx)
    for lid, inst, d, _ in legs:
        take = held[lid] & ~taken
        label[take] = lid
        gross[take] = d * rets[inst][take]
        taken = taken | take

    # switch cost: charge 2 sides whenever the held label changes
    switch = (label != label.shift(1)).astype(float)
    cost = switch * (2 * SWITCH_BPS / 1e4)
    net = gross - cost
    bh = rets["SPY"]

    # ---- per-overlay-trade stats (contiguous non-SPY holdings) ----
    trades = []
    i, n = 0, len(idx)
    lab = label.values
    while i < n:
        if lab[i] != "SPY":
            j = i
            while j < n and lab[j] == lab[i]:
                j += 1
            tr_ret = float((1 + net.iloc[i:j]).prod() - 1)
            trades.append({"leg": lab[i], "entry": idx[i], "days": j - i, "ret": tr_ret})
            i = j
        else:
            i += 1
    tr = pd.DataFrame(trades)
    wins = tr[tr["ret"] > 0]; losses = tr[tr["ret"] <= 0]
    pf = float(wins["ret"].sum() / -losses["ret"].sum()) if len(losses) and losses["ret"].sum() != 0 else float("inf")
    payoff = float(wins["ret"].mean() / -losses["ret"].mean()) if len(losses) else float("inf")

    def stats(r, label_):
        m = compute_metrics(r)
        return {"strategy": label_, "sharpe": round(m["sharpe"], 2), "sortino": round(m["sortino"], 2),
                "cagr_pct": round(m["cagr"] * 100, 2), "vol_pct": round(r.std() * ANN * 100, 1),
                "maxdd_pct": round(m["max_drawdown"] * 100, 1), "calmar": round(m["calmar"], 2)}

    out["gross"] = stats(gross, "Overlay BRUTTO")
    out["net"] = stats(net, "Overlay NETTO")
    out["buyhold"] = stats(bh, "S&P 500 Buy&Hold")
    out["trades"] = {
        "n_trades": len(tr), "win_rate_pct": round((tr["ret"] > 0).mean() * 100, 1),
        "expectancy_pct": round(tr["ret"].mean() * 100, 3), "median_pct": round(tr["ret"].median() * 100, 3),
        "avg_win_pct": round(wins["ret"].mean() * 100, 2), "avg_loss_pct": round(losses["ret"].mean() * 100, 2),
        "profit_factor": round(pf, 2), "payoff_ratio": round(payoff, 2),
        "avg_hold_days": round(tr["days"].mean(), 1), "trades_per_yr": round(len(tr) / ((idx[-1]-idx[0]).days/365.25), 1),
        "pct_time_in_overlay": round((label != "SPY").mean() * 100, 1),
        "by_leg": {lid: {"n": int((tr["leg"]==lid).sum()), "mean_pct": round(tr[tr["leg"]==lid]["ret"].mean()*100,2),
                          "win_pct": round((tr[tr["leg"]==lid]["ret"]>0).mean()*100,0)} for lid in tr["leg"].unique()},
    }
    yrs = (idx[-1]-idx[0]).days/365.25
    out["eur2000"] = {"start_eur": ACCOUNT_EUR,
                      "end_eur_net": round(ACCOUNT_EUR * float((1+net).prod()), 0),
                      "end_eur_gross": round(ACCOUNT_EUR * float((1+gross).prod()), 0),
                      "end_eur_bh": round(ACCOUNT_EUR * float((1+bh).prod()), 0),
                      "avg_eur_per_trade_net": round(ACCOUNT_EUR * tr["ret"].mean(), 1)}

    # ---- print ----
    print(f"Overlay-Buch (S&P-Kern + Switch-Trades) {idx[0].date()}..{idx[-1].date()}  ({yrs:.1f} J)\n")
    print(f"{'':22}{'Sharpe':>8}{'Sortino':>9}{'CAGR%':>8}{'Vol%':>7}{'MaxDD%':>8}{'Calmar':>8}")
    for k in ("gross", "net", "buyhold"):
        s = out[k]
        print(f"{s['strategy']:22}{s['sharpe']:>8}{s['sortino']:>9}{s['cagr_pct']:>8}{s['vol_pct']:>7}{s['maxdd_pct']:>8}{s['calmar']:>8}")
    t = out["trades"]
    print(f"\nSwitch-Trades: n={t['n_trades']} ({t['trades_per_yr']}/J), {t['pct_time_in_overlay']}% der Zeit im Overlay (sonst S&P)")
    print(f"  Win-Rate {t['win_rate_pct']}%, Expectancy {t['expectancy_pct']}%/Trade (Median {t['median_pct']}%)")
    print(f"  Ø-Win {t['avg_win_pct']}% / Ø-Loss {t['avg_loss_pct']}%, Profit-Faktor {t['profit_factor']}, Payoff {t['payoff_ratio']}, Ø-Hold {t['avg_hold_days']}d")
    print("  je Bein:", {k: v for k, v in t["by_leg"].items()})
    e = out["eur2000"]
    print(f"\nEUR 2000 -> netto {e['end_eur_net']:.0f} EUR | brutto {e['end_eur_gross']:.0f} | S&P-B&H {e['end_eur_bh']:.0f} (Ø {e['avg_eur_per_trade_net']:.0f} EUR/Trade)")

    # ---- plot ----
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot((1+net).cumprod(), label="Overlay NETTO", color="navy", lw=1.8)
    ax.plot((1+gross).cumprod(), label="Overlay BRUTTO", color="seagreen", lw=1, alpha=0.7)
    ax.plot((1+bh).cumprod(), label="S&P 500 Buy&Hold", color="grey", lw=1.2)
    ax.set_yscale("log"); ax.legend(); ax.grid(alpha=0.3, which="both")
    ax.set_title("0092 — S&P-Kern + Switch-Trade-Overlay (0020-Modell) vs Buy&Hold")
    fig.tight_layout(); fig.savefig(RESULTS / "overlay_book.png", dpi=110); plt.close(fig)
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
