"""Strategy 0036 — Quint seasonal overlay (adds cotton; equal-weight on overlap).

Extends 0033 (Benzin KW9 + Mastrind KW21 + Mais 8-18 Dec + Platin 18.12.-10.1.)
with a FIFTH leg: cotton (`CT=F`, 21 Nov - 29 Dec, from 0035).

KEY MODEL CHANGE vs 0020/0033. There the seasonal windows were disjoint, so an
"either/or" 100%-notional swap (index <-> one future) worked. Cotton's window
(21 Nov - 29 Dec) OVERLAPS both corn (8-18 Dec) and platinum (18 Dec - 10 Jan) -
three December seasonals on three different instruments now compete for the same
calendar. Forcing one to win (priority) would artificially cannibalise the others.

In reality these are three separate futures held on margin, tradable in parallel.
So this overlay uses **equal-weight allocation across simultaneously-active legs**:
on a day where k seasonal legs are active, each gets 1/k of the seasonal notional;
on a day with none, hold the index. This is more realistic AND resolves the overlap
additively (it also lowers concentration/vol on the crowded December days).

Switching cost: charged on the turnover of each leg's weight, SWITCH_COST per unit
of |Δweight| (one index<->future swap side-pair), so partial entries/exits and the
equal-weight reshuffles are all costed.

Look-ahead safety: decision-time signals, weights shifted one bar (T+1).

HONEST CAVEAT (as 0033): only Benzin/Mastrind are pre-registered forward tests
(0006/0009). Platinum (0018), corn (0032) and cotton (0035) were mined on full
history, so 2016+ is NOT clean OOS for them. This is portfolio construction, not a
new edge.

Run:
    .venv/Scripts/python.exe strategies/0036_quint_season_overlay/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import compute_metrics, trade_stats, run_backtest  # noqa: E402
from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.seasonal import add_calendar_features  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

FORWARD_START = "2016-01-01"
HOLD_DAYS = 5

LEGS = [
    {"ticker": "RB=F", "kind": "week", "week": 9, "name": "Benzin"},
    {"ticker": "GF=F", "kind": "week", "week": 21, "name": "Mastrind"},
    {"ticker": "CT=F", "kind": "date", "start_md": (11, 21), "end_md": (12, 29), "name": "Baumwolle"},
    {"ticker": "ZC=F", "kind": "date", "start_md": (12, 8), "end_md": (12, 18), "name": "Mais"},
    {"ticker": "PL=F", "kind": "date", "start_md": (12, 18), "end_md": (1, 10), "name": "Platin"},
]

INDICES = {"^GSPC": "S&P 500", "^GDAXI": "DAX"}

FUT_SIDE = (IBKR_FUTURES.slippage_bps + IBKR_FUTURES.regulatory_bps) / 10_000.0
IDX_SIDE = (IBKR_LIQUID_ETF.slippage_bps + IBKR_LIQUID_ETF.regulatory_bps) / 10_000.0
SWITCH_COST = FUT_SIDE + IDX_SIDE


def event_signal(index, iso_week, hold_days=HOLD_DAYS, name="event") -> pd.Series:
    idx = pd.DatetimeIndex(index)
    feats = add_calendar_features(idx)
    weeks, years = feats["week"].values, idx.year.values
    pos = np.zeros(len(idx))
    for y in np.unique(years):
        locs = np.where((years == y) & (weeks == iso_week))[0]
        if len(locs):
            pos[locs[0]:min(len(idx), locs[0] + hold_days)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def date_window_signal(index, start_md, end_md, name="date") -> pd.Series:
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    same_year = tuple(end_md) > tuple(start_md)
    for y in range(int(idx.year.min()) - 1, int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md)
        end = pd.Timestamp(y if same_year else y + 1, *end_md)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def leg_signal(index, leg) -> pd.Series:
    if leg["kind"] == "week":
        return event_signal(index, leg["week"], name=leg["ticker"])
    return date_window_signal(index, leg["start_md"], leg["end_md"], name=leg["ticker"])


def build_overlay(legs_px: dict, idx: pd.DataFrame):
    """Equal-weight overlay: active legs split the seasonal notional 1/k that day."""
    data = {"idx": idx["Close"].astype(float)}
    for leg in LEGS:
        data[leg["ticker"]] = legs_px[leg["ticker"]]["Close"].astype(float)
    df = pd.DataFrame(data).dropna()

    idx_ret = df["idx"].pct_change().fillna(0.0)
    leg_ret = {leg["ticker"]: df[leg["ticker"]].pct_change().fillna(0.0) for leg in LEGS}

    # Held (T+1) indicator per leg.
    held = {leg["ticker"]: (leg_signal(df.index, leg).reindex(df.index).fillna(0.0)
                            .shift(1).fillna(0.0) > 0).astype(float) for leg in LEGS}
    held_mat = pd.DataFrame(held)
    n_active = held_mat.sum(axis=1)
    # Equal weight across active legs (0 where none active).
    weights = held_mat.div(n_active.where(n_active > 0, 1.0), axis=0)
    weights[n_active == 0] = 0.0

    seasonal_ret = sum(weights[leg["ticker"]] * leg_ret[leg["ticker"]] for leg in LEGS)
    overlay_gross = idx_ret.where(n_active.values == 0, seasonal_ret)

    # Turnover cost: sum of |Δweight| across legs (covers entries, exits, reshuffles).
    turnover = weights.diff().abs().fillna(weights.abs()).sum(axis=1)
    overlay_net = overlay_gross - turnover * SWITCH_COST
    return df, idx_ret, overlay_net, n_active, held_mat, weights


def metric_row(label, rets):
    m = compute_metrics(rets)
    return {"label": label, "cagr": m["cagr"], "sharpe": m["sharpe"], "sortino": m["sortino"],
            "annual_volatility": m["annual_volatility"], "calmar": m["calmar"],
            "max_drawdown": m["max_drawdown"], "total_return": m["total_return"]}


def fmt(label, m):
    return (f"  [{label}]\n    CAGR {m['cagr']:.2%}  Sharpe {m['sharpe']:.2f}  Sortino {m['sortino']:.2f}"
            f"  Vol {m['annual_volatility']:.2%}  MaxDD {m['max_drawdown']:.2%}  TotRet {m['total_return']:.1%}\n")


def main():
    print("Strategy 0036 — Quint overlay (Benzin+Mastrind+Baumwolle+Mais+Platin, equal-weight on overlap)")
    RESULTS.mkdir(parents=True, exist_ok=True); PLOTS.mkdir(parents=True, exist_ok=True)

    legs_px = {leg["ticker"]: get_prices(leg["ticker"], start="2000-01-01") for leg in LEGS}
    for leg in LEGS:
        if (legs_px[leg["ticker"]]["Close"] <= 0).any():
            raise SystemExit(f"Non-positive close in {leg['ticker']} (0005).")

    summary = {"legs": LEGS, "model": "equal-weight across active legs", "indices": {}}
    card_card = None

    for ticker, name in INDICES.items():
        idx = get_prices(ticker, start="2000-01-01")
        df, idx_ret, overlay_net, n_active, held_mat, weights = build_overlay(legs_px, idx)
        start_date, end_date = df.index[0].date(), df.index[-1].date()
        overlap_days = int((n_active > 1).sum())

        m_overlay = metric_row(f"{name} + Quint-Overlay", overlay_net)
        m_bh = metric_row(f"{name} Buy & Hold", idx_ret)
        fwd = df.index >= FORWARD_START
        m_overlay_fwd = metric_row(f"{name} + Overlay (Forward)", overlay_net[fwd])
        m_bh_fwd = metric_row(f"{name} B&H (Forward)", idx_ret[fwd])

        # Per-leg standalone trade context + realized active days inside the overlay.
        leg_stats = {}
        for leg in LEGS:
            frame = df[[leg["ticker"]]].rename(columns={leg["ticker"]: "Close"})
            bt = run_backtest(frame, leg_signal(df.index, leg), cost_model=IBKR_FUTURES)
            ts = trade_stats(bt["trades"])
            leg_stats[leg["ticker"]] = {**ts, "active_days": int((held_mat[leg["ticker"]] > 0).sum())}

        overlay_eq = (1 + overlay_net).cumprod(); bh_eq = (1 + idx_ret).cumprod()
        safe = ticker.replace("^", "").lower()
        plotting.savefig(plotting.plot_equity(
            overlay_eq, benchmark=bh_eq,
            title=f"0036 {name}: Quint-Saison-Overlay (5 Beine, gleichgewichtet) vs. Buy & Hold",
            strategy_label=f"{name} + Quint-Saison-Overlay", benchmark_label=f"{name} Buy & Hold",
            caption=(f"Kapitalkurve {start_date}–{end_date}, netto, log-Skala. Ganzjährig {name}; Umstieg in "
                     f"KW9 (Benzin), KW21 (Mastrind), 21.11.–29.12. (Baumwolle CT=F), 8.–18.12. (Mais ZC=F), "
                     f"18.12.–10.1. (Platin PL=F). An Tagen mit mehreren aktiven Dezember-Beinen wird das "
                     f"Kapital gleich aufgeteilt (realistisch: getrennte Futures auf Margin). "
                     f"{overlap_days} Überlappungstage.")),
            PLOTS / f"overlay_{safe}.png")
        plotting.savefig(plotting.plot_equity(
            (1 + overlay_net[fwd]).cumprod(), benchmark=(1 + idx_ret[fwd]).cumprod(),
            title=f"0036 {name}: Quint-Overlay vs. Buy & Hold — ab 2016",
            strategy_label=f"{name} + Quint-Saison-Overlay", benchmark_label=f"{name} Buy & Hold",
            caption=("Nur ab 2016. ACHTUNG: echter Forward-Test nur Benzin/Mastrind (0006/0009). Platin, "
                     "Mais, Baumwolle full-history-gemined → 2016+ KEIN sauberes OOS für sie. Netto.")),
            PLOTS / f"overlay_{safe}_forward.png")

        summary["indices"][ticker] = {
            "name": name, "start": str(start_date), "end": str(end_date), "overlap_days": overlap_days,
            "full": {"overlay": m_overlay, "buy_hold": m_bh},
            "forward": {"overlay": m_overlay_fwd, "buy_hold": m_bh_fwd},
            "leg_trades": leg_stats,
        }

        print(f"\n  === {name} ({ticker}), {start_date}–{end_date} | {overlap_days} Überlappungstage ===")
        print(fmt("FULL  overlay", m_overlay)); print(fmt("FULL  buy&hold", m_bh))
        print(fmt("FWD   overlay", m_overlay_fwd)); print(fmt("FWD   buy&hold", m_bh_fwd))
        for leg in LEGS:
            ts = leg_stats[leg["ticker"]]
            print(f"    {leg['name']:9s} leg: {ts['n_trades']} trades, win {ts['win_rate']:.0%}, "
                  f"exp/trade {ts['expectancy']:.2%}, aktive Tage {ts['active_days']}")

        if ticker == "^GSPC":
            card_card = {"id": "0036", "label": "Quint-Saison-Overlay (Benzin+Mastrind+Baumwolle+Mais+Platin) auf S&P 500",
                         "cagr": m_overlay["cagr"], "annual_volatility": m_overlay["annual_volatility"],
                         "sharpe": m_overlay["sharpe"], "max_drawdown": m_overlay["max_drawdown"], "is_strategy": True}
            overlay_eq.rename("equity").to_csv(RESULTS / "equity.csv")

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    if card_card is not None:
        with open(RESULTS / "card.json", "w") as fh:
            json.dump(card_card, fh, indent=2)
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
