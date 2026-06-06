"""Strategy 0033 — Quad seasonal overlay (gasoline + cattle + platinum + corn) on equities.

Extends 0020 (Benzin KW9 + Mastrind KW21 + Platin 18.12.-10.1.) with a FOURTH leg:
the corn WASDE core (`ZC=F`, 8-18 Dec, refined in 0032). Rule, all year: hold the
equity index; step OUT into the relevant future for each short seasonal window, then
back into the index.

The corn (8-18 Dec) and platinum (18 Dec -> 10 Jan) windows *touch* on 18 Dec. The
overlay can only hold one instrument at a time, so legs are made **disjoint by
priority = list order**: corn is listed before platinum, so corn owns its 8-18 Dec
window and platinum effectively begins the next trading day (~19 Dec). The lost ~1
platinum day is negligible. `held_total` is asserted <= 1 to guarantee no
double-allocation.

Look-ahead safety (as 0020): decision-time event signals, held position shifted one
bar (T+1). Switching cost charged on each entry and exit day: one futures side
(IBKR_FUTURES) + one equity side (IBKR_LIQUID_ETF) per index<->future swap.

HONEST CAVEAT — read before the numbers:
  * Gasoline + cattle legs ARE pre-registered forward tests (0006/0009); for them
    2016+ is genuinely out-of-sample.
  * Platinum (0018) AND corn (0030/0032) were mined on full history (Seasonax /
    WASDE event); for them 2016+ is NOT clean OOS. 0033 is therefore a PORTFOLIO-
    CONSTRUCTION / bundling exercise (like 0007/0010/0020), not a new edge, and it
    inherits the "no true OOS for platinum & corn" caveat.
  * Notional: each switch moves 100% of notional index<->future ("either/or").
    In practice futures sit on margin, so a real book is less constrained — this is
    conservative.

Run:
    .venv/Scripts/python.exe strategies/0033_quad_season_overlay/run.py
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

# Four non-overlapping seasonal legs (corn listed before platinum so it wins the
# shared 18 Dec touch-point; see header). Two spring legs are ISO-week based; the
# corn and platinum legs are date based, platinum wraps the calendar year.
LEGS = [
    {"ticker": "RB=F", "kind": "week", "week": 9, "name": "Benzin"},
    {"ticker": "GF=F", "kind": "week", "week": 21, "name": "Mastrind"},
    {"ticker": "ZC=F", "kind": "date", "start_md": (12, 8), "end_md": (12, 18), "name": "Mais"},
    {"ticker": "PL=F", "kind": "date", "start_md": (12, 18), "end_md": (1, 10), "name": "Platin"},
]

INDICES = {"^GSPC": "S&P 500", "^GDAXI": "DAX"}

FUT_SIDE = (IBKR_FUTURES.slippage_bps + IBKR_FUTURES.regulatory_bps) / 10_000.0
IDX_SIDE = (IBKR_LIQUID_ETF.slippage_bps + IBKR_LIQUID_ETF.regulatory_bps) / 10_000.0
SWITCH_COST = FUT_SIDE + IDX_SIDE  # charged on each entry and each exit day


def event_signal(index, iso_week, hold_days=HOLD_DAYS, name="event") -> pd.Series:
    """One trade/year: long ``hold_days`` trading days from the first day of ``iso_week``."""
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
        pos[start:min(len(idx), start + hold_days)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def date_window_signal(index, start_md, end_md, name="date") -> pd.Series:
    """One trade/year: long on [start_md, end_md]; handles a year-wrapping window."""
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
    """Build the quad-overlay net return series; legs forced disjoint by list order."""
    data = {"idx": idx["Close"].astype(float)}
    for leg in LEGS:
        data[leg["ticker"]] = legs_px[leg["ticker"]]["Close"].astype(float)
    df = pd.DataFrame(data).dropna()

    idx_ret = df["idx"].pct_change().fillna(0.0)
    leg_ret = {leg["ticker"]: df[leg["ticker"]].pct_change().fillna(0.0) for leg in LEGS}

    overlay_gross = idx_ret.copy()
    held_total = pd.Series(0.0, index=df.index)
    held_any = pd.Series(False, index=df.index)
    held = {}
    for leg in LEGS:
        sig = leg_signal(df.index, leg)
        h_raw = sig.reindex(df.index).fillna(0.0).shift(1).fillna(0.0) > 0
        h = h_raw & ~held_any           # disjoint: earlier legs (list order) win the overlap
        held[leg["ticker"]] = h.astype(float)
        overlay_gross = overlay_gross.where(~h.values, leg_ret[leg["ticker"]])
        held_any = held_any | h
        held_total = held_total + h.astype(float)

    assert held_total.max() <= 1.0, "legs overlap — double allocation!"

    switch = pd.Series(0.0, index=df.index)
    for leg in LEGS:
        h = held[leg["ticker"]]
        switch = switch + h.diff().abs().fillna(h.abs())
    overlay_net = overlay_gross - switch * SWITCH_COST
    return df, idx_ret, overlay_net, held_total, held


def metric_row(label: str, rets: pd.Series) -> dict:
    m = compute_metrics(rets)
    return {"label": label, "cagr": m["cagr"], "sharpe": m["sharpe"], "sortino": m["sortino"],
            "annual_volatility": m["annual_volatility"], "calmar": m["calmar"],
            "max_drawdown": m["max_drawdown"], "total_return": m["total_return"]}


def fmt(label, m):
    return (f"  [{label}]\n"
            f"    CAGR {m['cagr']:.2%}  Sharpe {m['sharpe']:.2f}  Sortino {m['sortino']:.2f}"
            f"  Vol {m['annual_volatility']:.2%}  MaxDD {m['max_drawdown']:.2%}  TotRet {m['total_return']:.1%}\n")


def main() -> None:
    print("Strategy 0033 — Quad seasonal overlay (Benzin KW9 + Mastrind KW21 + Mais 8.-18.12. + Platin 18.12.-10.1.)")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    legs_px = {leg["ticker"]: get_prices(leg["ticker"], start="2000-01-01") for leg in LEGS}
    for leg in LEGS:
        if (legs_px[leg["ticker"]]["Close"] <= 0).any():
            raise SystemExit(f"Non-positive close in {leg['ticker']} — abort (0005).")

    summary = {"legs": LEGS, "hold_days": HOLD_DAYS, "indices": {}}
    card_card = None

    for ticker, name in INDICES.items():
        idx = get_prices(ticker, start="2000-01-01")
        df, idx_ret, overlay_net, held_total, held = build_overlay(legs_px, idx)
        start_date, end_date = df.index[0].date(), df.index[-1].date()

        m_overlay = metric_row(f"{name} + Quad-Overlay", overlay_net)
        m_bh = metric_row(f"{name} Buy & Hold", idx_ret)
        fwd = df.index >= FORWARD_START
        m_overlay_fwd = metric_row(f"{name} + Overlay (Forward)", overlay_net[fwd])
        m_bh_fwd = metric_row(f"{name} B&H (Forward)", idx_ret[fwd])

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
                title=f"0033 {name}: Quad-Saison-Overlay (Benzin+Mastrind+Mais+Platin) vs. Buy & Hold",
                strategy_label=f"{name} + Quad-Saison-Overlay", benchmark_label=f"{name} Buy & Hold",
                caption=(f"Kapitalkurve {start_date}–{end_date}, netto, log-Skala. Beide ganzjährig im "
                         f"{name}; die Overlay-Variante steigt nur in KW9 (Benzin RB=F), KW21 (Mastrind GF=F), "
                         f"8.–18.12. (Mais ZC=F) und 18.12.–10.1. (Platin PL=F) in den Future um. Vier kurze "
                         f"Saison-Trades/Jahr ggü. denselben Index-Tagen.")),
            PLOTS / f"overlay_{safe}.png")
        plotting.savefig(
            plotting.plot_equity(
                (1 + overlay_net[fwd]).cumprod(), benchmark=(1 + idx_ret[fwd]).cumprod(),
                title=f"0033 {name}: Quad-Overlay vs. Buy & Hold — ab 2016",
                strategy_label=f"{name} + Quad-Saison-Overlay", benchmark_label=f"{name} Buy & Hold",
                caption=("Nur ab 2016. ACHTUNG: echter Forward-Test nur für Benzin/Mastrind (0006/0009). "
                         "Platin (Seasonax) UND Mais (WASDE, 0030/0032) wurden auf voller Historie geminte → "
                         "für sie ist 2016+ KEIN sauberes OOS. Netto nach Kosten, beide bei 1 gestartet.")),
            PLOTS / f"overlay_{safe}_forward.png")

        summary["indices"][ticker] = {
            "name": name, "start": str(start_date), "end": str(end_date),
            "full": {"overlay": m_overlay, "buy_hold": m_bh},
            "forward": {"overlay": m_overlay_fwd, "buy_hold": m_bh_fwd},
            "leg_trades": {t: leg_stats[t] for t in leg_stats},
        }

        print(f"\n  === {name} ({ticker}), {start_date}–{end_date} ===")
        print(fmt("FULL  overlay", m_overlay)); print(fmt("FULL  buy&hold", m_bh))
        print(fmt("FWD   overlay", m_overlay_fwd)); print(fmt("FWD   buy&hold", m_bh_fwd))
        for leg in LEGS:
            ts = leg_stats[leg["ticker"]]
            print(f"    {leg['name']:9s} leg: {ts['n_trades']} trades, win {ts['win_rate']:.0%}, "
                  f"expectancy/trade {ts['expectancy']:.2%}")

        if ticker == "^GSPC":
            card_card = {"id": "0033", "label": "Quad-Saison-Overlay (Benzin+Mastrind+Mais+Platin) auf S&P 500",
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
