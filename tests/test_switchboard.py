"""Routing + matrix tests for the Switchboard (quantlab.switchboard).

Pins the two pieces the dashboard trusts: (1) the profit-factor primitive and the
cell-rating/qualification gate behave as specified (Sharpe>0.8 AND PF>1.2), and
(2) ``build_switchboard`` routes a sleeve ACTIVE in exactly the current regime it
qualifies for, PAUSED otherwise — and flips when the current regime changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab import regime, switchboard as sb


def _synthetic_ohlc(n: int = 900, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    drift = np.concatenate([np.full(300, 0.0008), np.full(200, -0.0002),
                            np.full(200, -0.0010), np.full(n - 700, 0.0003)])
    vol = np.concatenate([np.full(300, 0.008), np.full(200, 0.020),
                          np.full(200, 0.012), np.full(n - 700, 0.006)])
    ret = drift + vol * rng.standard_normal(n)
    close = 100 * np.exp(np.cumsum(ret))
    idx = pd.bdate_range("2018-01-01", periods=n)
    high = close * (1 + np.abs(rng.standard_normal(n)) * 0.004)
    low = close * (1 - np.abs(rng.standard_normal(n)) * 0.004)
    open_ = close * (1 + rng.standard_normal(n) * 0.002)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": rng.integers(1e6, 5e6, n)}, index=idx)


def test_profit_factor_basic():
    assert regime.profit_factor(pd.Series([0.01, -0.005, 0.02, -0.005])) == 3.0
    # only winners → capped sentinel, never inf
    assert regime.profit_factor(pd.Series([0.01, 0.02])) == regime.PROFIT_FACTOR_CAP
    # empty / flat → 0
    assert regime.profit_factor(pd.Series([], dtype=float)) == 0.0
    assert regime.profit_factor(pd.Series([0.0, 0.0])) == 0.0


def test_cell_qualified_and_rating():
    th = sb.RoutingThresholds()
    win = {"n": 50, "sharpe": 1.0, "profit_factor": 1.5, "total_return": 0.1}
    assert sb.cell_qualified(win, th)
    assert sb.cell_rating(win, th) == sb.RATING_GOOD
    strong = {"n": 50, "sharpe": 2.0, "profit_factor": 3.0, "total_return": 0.4}
    assert sb.cell_rating(strong, th) == sb.RATING_EXCELLENT
    weak = {"n": 50, "sharpe": 0.5, "profit_factor": 1.1, "total_return": 0.02}
    assert not sb.cell_qualified(weak, th)
    assert sb.cell_rating(weak, th) == sb.RATING_NEUTRAL
    loser = {"n": 50, "sharpe": -0.3, "profit_factor": 0.7, "total_return": -0.1}
    assert sb.cell_rating(loser, th) == sb.RATING_LOSS
    thin = {"n": 3, "sharpe": 5.0, "profit_factor": 9.0, "total_return": 0.2}
    assert not sb.cell_qualified(thin, th)  # too few trades to trust
    assert sb.cell_rating(thin, th) == sb.RATING_NEUTRAL


def test_route_status_follows_current_regime():
    """A sleeve qualified only in regime A is ACTIVE when A is current, PAUSED in B."""
    cells = {
        "high_vol_trend": {"qualified": True},
        "low_vol_trend": {"qualified": False},
        "high_vol_range": {"qualified": False},
        "low_vol_range": {"qualified": False},
    }
    assert sb.route_status(cells, "high_vol_trend") == sb.STATUS_ACTIVE
    assert sb.route_status(cells, "low_vol_trend") == sb.STATUS_PAUSED
    assert sb.route_status(cells, None) == sb.STATUS_PAUSED


def test_build_switchboard_shape_and_routing():
    df = _synthetic_ohlc()
    classified = regime.classify(df)
    # a sleeve whose returns ARE the benchmark's returns → it should look good in the
    # trending regimes (it rides the trend) and the matrix must have all 4 cells.
    ret = df["Close"].pct_change().fillna(0.0)
    panel = pd.DataFrame({"0001 trend rider": ret})
    meta = [{"num": "0001", "label": "0001 trend rider", "name": "Trend Rider",
             "status": "testing", "category": "test"}]
    current = regime.current_regime(classified)["regime"]
    board = sb.build_switchboard(panel, meta, classified, current)

    assert board["summary"]["n_strategies"] == 1
    row = board["rows"][0]
    assert set(row["cells"].keys()) == set(regime.REGIMES)
    for cell in row["cells"].values():
        assert "profit_factor" in cell and "rating" in cell and "qualified" in cell
    # status is consistent with the current-regime cell's qualified flag
    expected = sb.STATUS_ACTIVE if row["cells"][current]["qualified"] else sb.STATUS_PAUSED
    assert row["status"] == expected
    assert board["current_regime"] == current
