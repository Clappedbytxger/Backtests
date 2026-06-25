"""Tests for the Conditional Backtesting Engine (:mod:`quantlab.conditional`).

Covers the three Phase-2 capabilities: trade-level regime tagging (look-ahead-safe),
the per-strategy Regime Performance Matrix (allowed_market_regimes), and the
regime-switch detection + ACTIVE/PAUSED flip plan that drives the live router.
"""

import numpy as np
import pandas as pd

from quantlab import conditional as cb
from quantlab import regime as rg

WIN = "low_vol_trend"   # the regime our test strategy earns in
FRESH = "high_vol_trend"


def _classified(codes: list[str], start="2020-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(codes))
    return pd.DataFrame({"regime": codes}, index=idx)


def _winning_returns(cls: pd.DataFrame, seed=0) -> pd.Series:
    """+1%/day (with noise) inside WIN, flat elsewhere → qualifies in WIN only."""
    rng = np.random.default_rng(seed)
    ret = pd.Series(0.0, index=cls.index)
    mask = (cls["regime"] == WIN).to_numpy()
    ret[mask] = rng.normal(0.01, 0.01, int(mask.sum()))
    return ret


# ── 2.1 trade tagging ───────────────────────────────────────────────────────
def test_tag_trades_assigns_entry_regime_lookahead_safe():
    cls = _classified([WIN] * 298 + [FRESH] * 2)
    d = cls.index
    trades = pd.DataFrame({
        "entry_date": [d[5], d[299], pd.Timestamp("2019-06-01")],  # WIN, FRESH, pre-history
        "net_return": [0.02, -0.01, 0.05],
    })
    tagged = cb.tag_trades(trades, cls)
    by = tagged.set_index("entry_date")["entry_regime"]
    assert by[d[5]] == WIN
    assert by[d[299]] == FRESH
    assert pd.isna(by[pd.Timestamp("2019-06-01")])  # before first bar → NA, never future


def test_regime_trade_stats_aggregates_per_regime():
    cls = _classified([WIN] * 298 + [FRESH] * 2)
    d = cls.index
    trades = pd.DataFrame({
        "entry_date": [d[5], d[6], d[299]],
        "net_return": [0.02, -0.01, 0.03],
    })
    stats = cb.regime_trade_stats(cb.tag_trades(trades, cls))
    assert stats[WIN]["n_trades"] == 2
    assert stats[FRESH]["n_trades"] == 1
    assert abs(stats[WIN]["win_rate"] - 0.5) < 1e-9
    assert all(c in stats for c in rg.REGIMES)  # all four regimes present


# ── 2.2 regime performance matrix ───────────────────────────────────────────
def test_conditional_matrix_allowed_regimes():
    cls = _classified([WIN] * 200 + ["high_vol_range"] * 100)
    ret = _winning_returns(cls)
    m = cb.conditional_matrix(ret, cls)
    assert WIN in m["allowed_market_regimes"]          # earns here → allowed
    assert "high_vol_range" not in m["allowed_market_regimes"]  # flat here → not
    assert m["best_regime"] == WIN
    assert m["cells"][WIN]["qualified"] is True


# ── 2.3 switch detection + flip delta ───────────────────────────────────────
def test_detect_switch_flags_fresh_flip():
    cls = _classified([WIN] * 298 + [FRESH] * 2)
    sw = cb.detect_switch(cls)
    assert sw["current_regime"] == FRESH
    assert sw["previous_regime"] == WIN
    assert sw["bars_in_regime"] == 2
    assert sw["just_switched"] is True   # 2 <= SWITCH_FRESH_BARS

    steady = cb.detect_switch(_classified([WIN] * 300))
    assert steady["previous_regime"] is None
    assert steady["just_switched"] is False


def test_live_switch_delta():
    rows = [
        {"num": "A", "name": "A", "active_regimes": [WIN]},
        {"num": "B", "name": "B", "active_regimes": [FRESH]},
        {"num": "C", "name": "C", "active_regimes": [WIN, FRESH]},  # on in both → no flip
    ]
    delta = cb.live_switch_delta(rows, current_regime=FRESH, previous_regime=WIN)
    assert [a["num"] for a in delta["activated"]] == ["B"]
    assert [a["num"] for a in delta["deactivated"]] == ["A"]
    assert delta["n_activated"] == 1 and delta["n_deactivated"] == 1


# ── the router + commander view ─────────────────────────────────────────────
def _book(cls):
    ret = _winning_returns(cls)
    flat = pd.Series(0.0, index=cls.index)
    panel = pd.DataFrame({"0001 Winner": ret, "0002 Flat": flat})
    meta = [
        {"label": "0001 Winner", "num": "0001", "name": "Winner",
         "status": "testing", "category": "seasonal"},
        {"label": "0002 Flat", "num": "0002", "name": "Flat",
         "status": "testing", "category": "trend"},
    ]
    return panel, meta


def test_build_router_routes_and_exposes_allowed():
    cls = _classified([WIN] * 300)             # current regime = WIN
    panel, meta = _book(cls)
    board = cb.build_router(panel, meta, cls)
    assert board["switch"]["current_regime"] == WIN
    rows = {r["num"]: r for r in board["rows"]}
    assert rows["0001"]["status"] == "ACTIVE"           # winner qualifies in WIN
    assert WIN in rows["0001"]["allowed_market_regimes"]
    assert rows["0002"]["status"] == "PAUSED"           # flat sleeve paused


def test_commander_strategy_view_orders_active_first():
    cls = _classified([WIN] * 300)
    panel, meta = _book(cls)
    board = cb.build_router(panel, meta, cls)
    view = cb.commander_strategy_view(board["rows"], WIN)
    assert view[0]["regime_status"] == "ACTIVE"
    assert "allowed_regimes" in view[0]
    assert view[0]["num"] == "0001"
