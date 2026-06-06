"""Strategy 0010 — Dual seasonal overlay (gasoline + feeder cattle) on equities.

Generalizes 0007. There, the gasoline week-9 rule (0006) was overlaid on an equity
buy-and-hold core: stay in the index all year, but step OUT into the gasoline
future for the ~5-day week-9 window. 0008/0009 produced a SECOND macro-justifiable
seasonal lead — feeder cattle (GF=F), ISO week 21 (~late May). Those two windows do
not overlap, so we can stack both overlays on the same equity core:

  * All year: hold the index (S&P 500 or DAX), plain buy-and-hold.
  * ISO week 9 (~early March): step OUT of the index into the GASOLINE future
    (~5 trading days), then back into the index.
  * ISO week 21 (~late May): step OUT of the index into the FEEDER CATTLE future
    (~5 trading days), then back into the index.

We then compare this dual overlay's equity curve against pure index buy-and-hold,
exactly as in 0007, both full-sample and on the forward period (2016+, unseen by
either window choice).

Look-ahead safety (same as 0007): decision-time event signals, position held is
shifted by one bar (T+1 execution). Switching costs are charged on every entry and
exit day: one futures side (IBKR_FUTURES) + one equity side (IBKR_LIQUID_ETF), for
each of the (up to) four switches per year.

Honest caveat (also in the report): this treats each switch as moving 100% of
notional between index and a future. In practice futures are held on margin, so a
real book could keep the index AND post margin for the seasonal leg — making this
a conservative "either/or" version of the overlay.

Run:
    .venv/Scripts/python.exe strategies/0010_dual_seasonal_equity_overlay/run.py
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

# Seasonal legs: (ticker, ISO week, display name). Windows do not overlap.
LEGS = [
    {"ticker": "RB=F", "week": 9, "name": "Benzin"},
    {"ticker": "GF=F", "week": 21, "name": "Mastrind"},
]

INDICES = {
    "^GSPC": "S&P 500",
    "^GDAXI": "DAX",
}

# Per-side switching cost as a fraction of notional (bps -> fraction). Same basis
# as 0007: futures slippage+fees on one side, liquid-ETF slippage+fees on the
# other; the per-share commission is negligible at index/contract notionals.
GAS_SIDE = (IBKR_FUTURES.slippage_bps + IBKR_FUTURES.regulatory_bps) / 10_000.0
IDX_SIDE = (IBKR_LIQUID_ETF.slippage_bps + IBKR_LIQUID_ETF.regulatory_bps) / 10_000.0
SWITCH_COST = GAS_SIDE + IDX_SIDE  # charged on each entry and each exit day


def event_signal(index, iso_week, hold_days=HOLD_DAYS, name="event") -> pd.Series:
    """One trade per year: long for ``hold_days`` trading days from the first
    trading day of ``iso_week``. Decision-time; caller applies the T+1 shift."""
    idx = pd.DatetimeIndex(index)
    feats = add_calendar_features(idx)
    weeks = feats["week"].values
    years = idx.year.values
    pos = np.zeros(len(idx))
    for y in np.unique(years):
        locs = np.where((years == y) & (weeks == iso_week))[0]
        if len(locs) == 0:
            continue
        start = locs[0]
        end = min(len(idx), start + hold_days)
        pos[start:end] = 1.0
    return pd.Series(pos, index=idx, name=name)


def build_overlay(legs_px: dict, idx: pd.DataFrame):
    """Build the dual-overlay net return series aligned on common dates.

    ``legs_px`` maps ticker -> price DataFrame. Returns
    (frame, idx_ret, overlay_net, held_total, per_leg_held).
    """
    data = {"idx": idx["Close"].astype(float)}
    for leg in LEGS:
        data[leg["ticker"]] = legs_px[leg["ticker"]]["Close"].astype(float)
    df = pd.DataFrame(data).dropna()

    idx_ret = df["idx"].pct_change().fillna(0.0)
    leg_ret = {leg["ticker"]: df[leg["ticker"]].pct_change().fillna(0.0) for leg in LEGS}

    # Held (T+1 shifted) position per leg; windows are disjoint so no overlap.
    held = {}
    overlay_gross = idx_ret.copy()
    held_total = pd.Series(0.0, index=df.index)
    for leg in LEGS:
        sig = event_signal(df.index, leg["week"], name=leg["ticker"])
        h = sig.reindex(df.index).fillna(0.0).shift(1).fillna(0.0)
        held[leg["ticker"]] = h
        overlay_gross = overlay_gross.where(h.values <= 0, leg_ret[leg["ticker"]])
        held_total = held_total + h

    # Switch cost: each leg entry and exit is one index<->future swap.
    switch = pd.Series(0.0, index=df.index)
    for leg in LEGS:
        h = held[leg["ticker"]]
        switch = switch + h.diff().abs().fillna(h.abs())
    overlay_net = overlay_gross - switch * SWITCH_COST
    return df, idx_ret, overlay_net, held_total, held


def metric_row(label: str, rets: pd.Series) -> dict:
    m = compute_metrics(rets)
    return {
        "label": label,
        "cagr": m["cagr"], "sharpe": m["sharpe"], "sortino": m["sortino"],
        "annual_volatility": m["annual_volatility"], "calmar": m["calmar"],
        "max_drawdown": m["max_drawdown"], "total_return": m["total_return"],
    }


def fmt(label, m):
    return (f"  [{label}]\n"
            f"    CAGR {m['cagr']:.2%}  Sharpe {m['sharpe']:.2f}  Sortino {m['sortino']:.2f}"
            f"  Vol {m['annual_volatility']:.2%}  MaxDD {m['max_drawdown']:.2%}"
            f"  TotRet {m['total_return']:.1%}\n")


def main() -> None:
    print("Strategy 0010 — Dual seasonal overlay (Benzin KW9 + Mastrind KW21) on equities")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    legs_px = {leg["ticker"]: get_prices(leg["ticker"], start="2000-01-01") for leg in LEGS}

    summary = {"legs": LEGS, "hold_days": HOLD_DAYS, "indices": {}}
    card_card = None

    for ticker, name in INDICES.items():
        idx = get_prices(ticker, start="2000-01-01")
        df, idx_ret, overlay_net, held_total, held = build_overlay(legs_px, idx)
        start_date, end_date = df.index[0].date(), df.index[-1].date()

        # Full-sample comparison.
        m_overlay = metric_row(f"{name} + Dual-Overlay", overlay_net)
        m_bh = metric_row(f"{name} Buy & Hold", idx_ret)

        # Forward-only sub-period (both rules validated/forward-tested 2016+).
        fwd_mask = df.index >= FORWARD_START
        m_overlay_fwd = metric_row(f"{name} + Overlay (Forward)", overlay_net[fwd_mask])
        m_bh_fwd = metric_row(f"{name} B&H (Forward)", idx_ret[fwd_mask])

        # Per-leg trade context (how many trades, expectancy) on the same dates.
        leg_stats = {}
        for leg in LEGS:
            frame = df[[leg["ticker"]]].rename(columns={leg["ticker"]: "Close"})
            bt = run_backtest(frame, event_signal(df.index, leg["week"]),
                              cost_model=IBKR_FUTURES)
            leg_stats[leg["ticker"]] = trade_stats(bt["trades"])

        overlay_eq = (1 + overlay_net).cumprod()
        bh_eq = (1 + idx_ret).cumprod()

        # Plot: full-sample dual overlay vs pure buy-and-hold.
        safe = ticker.replace("^", "").lower()
        plotting.savefig(
            plotting.plot_equity(
                overlay_eq, benchmark=bh_eq,
                title=f"0010 {name}: Benzin+Mastrind-Overlay vs. reines Buy & Hold",
                strategy_label=f"{name} + Dual-Saison-Overlay",
                benchmark_label=f"{name} Buy & Hold",
                caption=(
                    f"Kapitalkurve {start_date}–{end_date}, netto nach Kosten, log-Skala. "
                    f"Beide Kurven sind ganzjährig im {name} investiert — die Overlay-Variante "
                    f"(blau) steigt nur in ISO-Woche 9 (~Anfang März) in den Benzin-Future und "
                    f"in ISO-Woche 21 (~Ende Mai) in den Feeder-Cattle-Future um (je ~{HOLD_DAYS} "
                    f"Handelstage), sonst Index. Differenz = Mehrwert der zwei Saison-Trades/Jahr "
                    f"gegenüber den gleichen ~10 Index-Tagen.")),
            PLOTS / f"overlay_{safe}.png")

        # Plot: forward-only window.
        plotting.savefig(
            plotting.plot_equity(
                (1 + overlay_net[fwd_mask]).cumprod(),
                benchmark=(1 + idx_ret[fwd_mask]).cumprod(),
                title=f"0010 {name}: Dual-Overlay vs. Buy & Hold — nur Forward (ab 2016)",
                strategy_label=f"{name} + Dual-Saison-Overlay",
                benchmark_label=f"{name} Buy & Hold",
                caption=(
                    f"Wie oben, aber nur auf den Jahren ab 2016, die bei der Wahl beider "
                    f"Saison-Fenster keine Rolle spielten (echter Forward-Test). Beide Kurven "
                    f"bei 1 gestartet, netto nach Kosten.")),
            PLOTS / f"overlay_{safe}_forward.png")

        summary["indices"][ticker] = {
            "name": name, "start": str(start_date), "end": str(end_date),
            "full": {"overlay": m_overlay, "buy_hold": m_bh},
            "forward": {"overlay": m_overlay_fwd, "buy_hold": m_bh_fwd},
            "leg_trades": {t: leg_stats[t] for t in leg_stats},
        }

        print(f"\n  === {name} ({ticker}), {start_date}–{end_date} ===")
        print(fmt("FULL  overlay", m_overlay))
        print(fmt("FULL  buy&hold", m_bh))
        print(fmt("FWD   overlay", m_overlay_fwd))
        print(fmt("FWD   buy&hold", m_bh_fwd))
        for leg in LEGS:
            ts = leg_stats[leg["ticker"]]
            print(f"    {leg['name']} leg: {ts['n_trades']} trades, win {ts['win_rate']:.0%}, "
                  f"expectancy/trade {ts['expectancy']:.2%}")

        if ticker == "^GSPC":
            card_card = {
                "id": "0010", "label": "Benzin+Mastrind-Overlay auf S&P 500",
                "cagr": m_overlay["cagr"], "annual_volatility": m_overlay["annual_volatility"],
                "sharpe": m_overlay["sharpe"], "max_drawdown": m_overlay["max_drawdown"],
                "is_strategy": True,
            }
            (overlay_eq.rename("equity")).to_csv(RESULTS / "equity.csv")

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    if card_card is not None:
        with open(RESULTS / "card.json", "w") as fh:
            json.dump(card_card, fh, indent=2)

    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
