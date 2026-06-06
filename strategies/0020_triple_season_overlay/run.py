"""Strategy 0020 — Triple seasonal overlay (gasoline + feeder cattle + platinum) on equities.

Extends 0010. There we held an equity core (S&P 500 / DAX) all year and stepped
OUT into a future for two short, non-overlapping seasonal windows:

  * ISO week 9  (~early March): GASOLINE future RB=F (0006, forward-validated).
  * ISO week 21 (~late May):    FEEDER CATTLE future GF=F (0009, forward-validated).

0018/0019 produced a THIRD macro-justifiable seasonal lead — PLATINUM (PL=F),
the turn-of-year window. 0019 excluded the mid-January roll artifact and
recommended a roll-safe refinement: enter ~18 Dec, exit ~10 Jan (just before the
Jan->Apr roll zone). That window does not overlap the two spring windows, so we
stack a third overlay on the same equity core:

  * 18 Dec -> 10 Jan (turn of year, ~15 trading days): PLATINUM future PL=F.

Rule, all year: hold the index; step OUT into the relevant future for each of the
three windows, then back into the index.

Look-ahead safety (same as 0007/0010): decision-time event signals, the held
position is shifted one bar (T+1 execution). Switching costs are charged on every
entry and exit day: one futures side (IBKR_FUTURES) + one equity side
(IBKR_LIQUID_ETF) per index<->future swap.

HONEST CAVEAT — read before reading the numbers:
  * Gasoline + cattle legs are PRE-REGISTERED forward tests (discovered in-sample
    in 0005/0008, then forward-tested 2016+ in 0006/0009). For them the post-2016
    period is genuinely out-of-sample.
  * The PLATINUM leg is NOT a pre-registered forward test. It was Seasonax-mined
    on full history (0018), so 2016+ is NOT clean OOS for platinum — it sits inside
    platinum's own IS/OOS sample. 0020 is therefore a PORTFOLIO-CONSTRUCTION /
    bundling exercise (like 0007/0010), not a new edge, and it inherits the
    "no true OOS for platinum" caveat from 0018/0019.
  * Notional treatment: each switch moves 100% of notional between index and a
    future ("either/or"). In practice futures sit on margin, so a real book could
    keep the index AND post margin for the seasonal leg — making this conservative.

Run:
    .venv/Scripts/python.exe strategies/0020_triple_season_overlay/run.py
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
HOLD_DAYS = 5  # for the two ISO-week legs (gasoline, cattle)

# Three non-overlapping seasonal legs. The two spring legs are ISO-week based
# (kind="week", ~5 trading days). The turn-of-year platinum leg is date based
# (kind="date") and wraps the calendar year (18 Dec year y -> 10 Jan year y+1).
LEGS = [
    {"ticker": "RB=F", "kind": "week", "week": 9, "name": "Benzin"},
    {"ticker": "GF=F", "kind": "week", "week": 21, "name": "Mastrind"},
    {"ticker": "PL=F", "kind": "date", "start_md": (12, 18), "end_md": (1, 10), "name": "Platin"},
]

INDICES = {
    "^GSPC": "S&P 500",
    "^GDAXI": "DAX",
}

# Per-side switching cost as a fraction of notional (bps -> fraction). Same basis
# as 0007/0010: futures slippage+fees on one side, liquid-ETF slippage+fees on the
# other; per-share commission is negligible at index/contract notionals.
FUT_SIDE = (IBKR_FUTURES.slippage_bps + IBKR_FUTURES.regulatory_bps) / 10_000.0
IDX_SIDE = (IBKR_LIQUID_ETF.slippage_bps + IBKR_LIQUID_ETF.regulatory_bps) / 10_000.0
SWITCH_COST = FUT_SIDE + IDX_SIDE  # charged on each entry and each exit day


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


def date_window_signal(index, start_md, end_md, name="date") -> pd.Series:
    """One trade per year: long on all trading days in [start_md, end_md].
    Handles a year-wrapping window (end_md <= start_md => spans new year).
    Decision-time; caller applies the T+1 shift."""
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    same_year = tuple(end_md) > tuple(start_md)
    ymin, ymax = int(idx.year.min()), int(idx.year.max())
    for y in range(ymin - 1, ymax + 1):
        start = pd.Timestamp(y, *start_md)
        end_year = y if same_year else y + 1
        end = pd.Timestamp(end_year, *end_md)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def leg_signal(index, leg) -> pd.Series:
    """Decision-time signal for one leg, dispatching on its kind."""
    if leg["kind"] == "week":
        return event_signal(index, leg["week"], name=leg["ticker"])
    return date_window_signal(index, leg["start_md"], leg["end_md"], name=leg["ticker"])


def build_overlay(legs_px: dict, idx: pd.DataFrame):
    """Build the triple-overlay net return series aligned on common dates.

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
        sig = leg_signal(df.index, leg)
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
    print("Strategy 0020 — Triple seasonal overlay (Benzin KW9 + Mastrind KW21 + Platin 18.12.-10.1.) on equities")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    legs_px = {leg["ticker"]: get_prices(leg["ticker"], start="2000-01-01") for leg in LEGS}
    for leg in LEGS:
        px = legs_px[leg["ticker"]]
        if (px["Close"] <= 0).any():  # CLAUDE lesson 0005: futures can print <= 0
            raise SystemExit(f"Non-positive close in {leg['ticker']} — abort (roll/print artifact).")

    summary = {"legs": LEGS, "hold_days": HOLD_DAYS, "indices": {}}
    card_card = None

    for ticker, name in INDICES.items():
        idx = get_prices(ticker, start="2000-01-01")
        df, idx_ret, overlay_net, held_total, held = build_overlay(legs_px, idx)
        start_date, end_date = df.index[0].date(), df.index[-1].date()

        # Full-sample comparison.
        m_overlay = metric_row(f"{name} + Triple-Overlay", overlay_net)
        m_bh = metric_row(f"{name} Buy & Hold", idx_ret)

        # Forward-only sub-period (gas/cattle truly OOS; platinum NOT — see header).
        fwd_mask = df.index >= FORWARD_START
        m_overlay_fwd = metric_row(f"{name} + Overlay (Forward)", overlay_net[fwd_mask])
        m_bh_fwd = metric_row(f"{name} B&H (Forward)", idx_ret[fwd_mask])

        # Per-leg trade context (how many trades, expectancy) on the same dates.
        leg_stats = {}
        for leg in LEGS:
            frame = df[[leg["ticker"]]].rename(columns={leg["ticker"]: "Close"})
            bt = run_backtest(frame, leg_signal(df.index, leg), cost_model=IBKR_FUTURES)
            leg_stats[leg["ticker"]] = trade_stats(bt["trades"])

        overlay_eq = (1 + overlay_net).cumprod()
        bh_eq = (1 + idx_ret).cumprod()

        safe = ticker.replace("^", "").lower()
        plotting.savefig(
            plotting.plot_equity(
                overlay_eq, benchmark=bh_eq,
                title=f"0020 {name}: Benzin+Mastrind+Platin-Overlay vs. reines Buy & Hold",
                strategy_label=f"{name} + Triple-Saison-Overlay",
                benchmark_label=f"{name} Buy & Hold",
                caption=(
                    f"Kapitalkurve {start_date}–{end_date}, netto nach Kosten, log-Skala. "
                    f"Beide Kurven ganzjährig im {name} — die Overlay-Variante (blau) steigt nur "
                    f"in ISO-Woche 9 (~Anfang März) in Benzin (RB=F), in ISO-Woche 21 (~Ende Mai) "
                    f"in Mastrind (GF=F) und vom 18. Dez. bis 10. Jan. in Platin (PL=F) um, sonst "
                    f"Index. Differenz = Mehrwert der drei Saison-Trades/Jahr ggü. denselben "
                    f"Index-Tagen.")),
            PLOTS / f"overlay_{safe}.png")

        plotting.savefig(
            plotting.plot_equity(
                (1 + overlay_net[fwd_mask]).cumprod(),
                benchmark=(1 + idx_ret[fwd_mask]).cumprod(),
                title=f"0020 {name}: Triple-Overlay vs. Buy & Hold — ab 2016",
                strategy_label=f"{name} + Triple-Saison-Overlay",
                benchmark_label=f"{name} Buy & Hold",
                caption=(
                    f"Wie oben, aber nur ab 2016. ACHTUNG: echter Forward-Test nur für die "
                    f"Benzin-/Mastrind-Beine (vorab fixiert in 0006/0009). Das Platin-Bein wurde "
                    f"auf der vollen Historie geminte (Seasonax) — für Platin ist 2016+ KEIN "
                    f"sauberes Out-of-Sample. Beide Kurven bei 1 gestartet, netto nach Kosten.")),
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
                "id": "0020", "label": "Benzin+Mastrind+Platin-Overlay auf S&P 500",
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
