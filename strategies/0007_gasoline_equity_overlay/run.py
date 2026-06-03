"""Strategy 0007 — Gasoline week-9 overlay on an equity buy-and-hold core.

Idea from the user: the 0006 gasoline rule is only invested ~2% of the year, so
98% of the capital sits idle. Instead of holding cash, park the core in a broad
equity index (S&P 500 or DAX) and only step OUT of the index into the gasoline
future for the ~5-day week-9 window each year. The rest of the time it is plain
buy-and-hold. We then compare this overlay's equity curve against pure index
buy-and-hold to see whether swapping those ~5 index days/year for the gasoline
trade actually improves the curve.

Mechanics (look-ahead safe):
  * Decision-time gasoline signal = 0006 event_signal; the position held is
    shifted by one bar (T+1 execution), exactly like the engine.
  * On any day the gasoline position is ON, the portfolio earns the gasoline
    daily return; otherwise it earns the index daily return.
  * Switching costs are charged on every entry/exit day: one futures side
    (IBKR_FUTURES) + one equity side (IBKR_LIQUID_ETF). Two switches per year.

Caveat (stated honestly in the report): this treats the switch as moving 100%
of notional between index and gasoline futures. In practice a future is held on
margin, so a real implementation could keep the index AND post margin for the
gasoline leg — making this a conservative "either/or" version of the overlay.

Run:
    .venv/Scripts/python.exe strategies/0007_gasoline_equity_overlay/run.py
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

GAS_TICKER = "RB=F"
ISO_WEEK = 9
HOLD_DAYS = 5
FORWARD_START = "2016-01-01"

INDICES = {
    "^GSPC": "S&P 500",
    "^GDAXI": "DAX",
}

# Per-side switching cost as a fraction of notional. Futures slippage+fees and
# liquid-ETF slippage+fees, expressed directly in bps (the per-share commission
# is negligible at index/contract notionals and would otherwise distort a tiny
# representative trade).
GAS_SIDE = (IBKR_FUTURES.slippage_bps + IBKR_FUTURES.regulatory_bps) / 10_000.0
IDX_SIDE = (IBKR_LIQUID_ETF.slippage_bps + IBKR_LIQUID_ETF.regulatory_bps) / 10_000.0
SWITCH_COST = GAS_SIDE + IDX_SIDE  # charged on each entry and each exit day


def event_signal(index, iso_week=ISO_WEEK, hold_days=HOLD_DAYS, name="rb_event") -> pd.Series:
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


def build_overlay(gas: pd.DataFrame, idx: pd.DataFrame):
    """Return (frame, idx_ret, overlay_net, held_pos) aligned on common dates."""
    df = pd.DataFrame({
        "gas": gas["Close"].astype(float),
        "idx": idx["Close"].astype(float),
    }).dropna()
    gas_ret = df["gas"].pct_change().fillna(0.0)
    idx_ret = df["idx"].pct_change().fillna(0.0)

    sig = event_signal(df.index)
    held = sig.reindex(df.index).fillna(0.0).shift(1).fillna(0.0)  # T+1 execution

    overlay_gross = pd.Series(
        np.where(held.values > 0, gas_ret.values, idx_ret.values), index=df.index)
    switch = held.diff().abs().fillna(held.abs())
    overlay_net = overlay_gross - switch * SWITCH_COST
    return df, idx_ret, overlay_net, held


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
    print(f"Strategy 0007 — Gasoline week-{ISO_WEEK} overlay on equity buy-and-hold")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    gas = get_prices(GAS_TICKER, start="2000-01-01")

    summary = {"gas_ticker": GAS_TICKER, "iso_week": ISO_WEEK, "hold_days": HOLD_DAYS,
               "indices": {}}
    card_card = None

    for ticker, name in INDICES.items():
        idx = get_prices(ticker, start="2000-01-01")
        df, idx_ret, overlay_net, held = build_overlay(gas, idx)
        start_date, end_date = df.index[0].date(), df.index[-1].date()

        # Full-sample comparison.
        m_overlay = metric_row(f"{name} + Benzin-Overlay", overlay_net)
        m_bh = metric_row(f"{name} Buy & Hold", idx_ret)

        # Forward-only sub-period (gasoline rule validated 2016+).
        fwd_mask = df.index >= FORWARD_START
        m_overlay_fwd = metric_row(f"{name} + Overlay (Forward)", overlay_net[fwd_mask])
        m_bh_fwd = metric_row(f"{name} B&H (Forward)", idx_ret[fwd_mask])

        # Gasoline-leg trade log (context: how many trades, expectancy).
        gas_frame = df[["gas"]].rename(columns={"gas": "Close"})
        gas_bt = run_backtest(gas_frame, event_signal(df.index), cost_model=IBKR_FUTURES)
        ts = trade_stats(gas_bt["trades"])

        overlay_eq = (1 + overlay_net).cumprod()
        bh_eq = (1 + idx_ret).cumprod()

        # Plot: full-sample overlay vs pure buy-and-hold.
        safe = ticker.replace("^", "").lower()
        plotting.savefig(
            plotting.plot_equity(
                overlay_eq, benchmark=bh_eq,
                title=f"0007 {name}: Benzin-KW{ISO_WEEK}-Overlay vs. reines Buy & Hold",
                strategy_label=f"{name} + Benzin-Overlay",
                benchmark_label=f"{name} Buy & Hold",
                caption=(
                    f"Kapitalkurve {start_date}–{end_date}, netto nach Kosten, log-Skala. "
                    f"Beide Kurven sind ganzjährig im {name} investiert — die Overlay-Variante "
                    f"(blau) steigt nur in der ISO-Woche 9 (~Anfang März) für {HOLD_DAYS} "
                    f"Handelstage in den Benzin-Future um und kehrt danach in den Index zurück. "
                    f"Differenz = Mehrwert der {ts['n_trades']} Benzin-Trades gegenüber den "
                    f"gleichen ~5 Index-Tagen.")),
            PLOTS / f"overlay_{safe}.png")

        # Plot: forward-only window, the honest slice for the gasoline edge.
        plotting.savefig(
            plotting.plot_equity(
                (1 + overlay_net[fwd_mask]).cumprod(),
                benchmark=(1 + idx_ret[fwd_mask]).cumprod(),
                title=f"0007 {name}: Overlay vs. Buy & Hold — nur Forward-Periode (ab 2016)",
                strategy_label=f"{name} + Benzin-Overlay",
                benchmark_label=f"{name} Buy & Hold",
                caption=(
                    f"Wie oben, aber nur auf den Jahren ab 2016, die bei der Wahl des "
                    f"Benzin-Fensters keine Rolle spielten (echter Forward-Test des Edges). "
                    f"Beide Kurven bei 1 gestartet, netto nach Kosten.")),
            PLOTS / f"overlay_{safe}_forward.png")

        summary["indices"][ticker] = {
            "name": name, "start": str(start_date), "end": str(end_date),
            "full": {"overlay": m_overlay, "buy_hold": m_bh},
            "forward": {"overlay": m_overlay_fwd, "buy_hold": m_bh_fwd},
            "gasoline_trades": ts,
        }

        print(f"\n  === {name} ({ticker}), {start_date}–{end_date} ===")
        print(fmt("FULL  overlay", m_overlay))
        print(fmt("FULL  buy&hold", m_bh))
        print(fmt("FWD   overlay", m_overlay_fwd))
        print(fmt("FWD   buy&hold", m_bh_fwd))
        print(f"    Gasoline leg: {ts['n_trades']} trades, win {ts['win_rate']:.0%}, "
              f"expectancy/trade {ts['expectancy']:.2%}")

        if ticker == "^GSPC":
            card_card = {
                "id": "0007", "label": "Benzin-Overlay auf S&P 500",
                "cagr": m_overlay["cagr"], "annual_volatility": m_overlay["annual_volatility"],
                "sharpe": m_overlay["sharpe"], "max_drawdown": m_overlay["max_drawdown"],
                "is_strategy": True,
            }
            (overlay_eq.rename("equity")).to_csv(RESULTS / "equity.csv")
            gas_bt["trades"].to_csv(RESULTS / "trades.csv", index=False)

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    if card_card is not None:
        with open(RESULTS / "card.json", "w") as fh:
            json.dump(card_card, fh, indent=2)

    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
