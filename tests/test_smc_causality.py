"""Look-ahead guard for the SMC engine (spec Teil 5, mandatory gate).

Truncating the data at any bar ``t`` must not change a single decision taken at
or before ``t``: the trades that have already closed in a full run must be
byte-for-byte reproduced by a run on the data cut off at the truncation bar.
A repaint (a swing/sweep/BOS that uses a future bar) would break this.
"""

import numpy as np
import pandas as pd

from quantlab.smc import SmcCosts, run_smc_backtest


def _synthetic_ohlc(n: int = 800, seed: int = 7) -> pd.DataFrame:
    """Deterministic random-walk OHLC with enough wiggle to generate setups."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n).cumsum()
    close = 100 + steps
    spread = rng.uniform(0.3, 1.2, n)
    high = close + spread * rng.uniform(0.4, 1.0, n)
    low = close - spread * rng.uniform(0.4, 1.0, n)
    open_ = close - rng.normal(0, 0.4, n)
    high = np.maximum.reduce([high, open_, close])
    low = np.minimum.reduce([low, open_, close])
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close},
                        index=idx)


COLS = ["entry_time", "exit_time", "direction", "entry", "stop", "exit", "reason"]


def _completed_before(trades: pd.DataFrame, boundary: pd.Timestamp) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades[trades["exit_time"] <= boundary].reset_index(drop=True)
    return out[COLS]


def test_no_lookahead_truncation_matches_full():
    df = _synthetic_ohlc()
    costs = SmcCosts(commission_bps=1.0, spread_bps=1.0, slip_coef=0.05, slip_min_bps=1.0)
    full = run_smc_backtest(df, direction="both", risk_frac=0.01, costs=costs)["trades"]
    assert len(full) > 5, "test data should produce several trades"

    for t in (250, 400, 600, 750):
        boundary = df.index[t - 1]
        trunc = run_smc_backtest(df.iloc[:t], direction="both", risk_frac=0.01,
                                 costs=costs)["trades"]
        a = _completed_before(trunc, boundary)
        b = _completed_before(full, boundary)
        assert len(a) == len(b), f"trade count diverges at t={t}: {len(a)} vs {len(b)}"
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_no_lookahead_asymmetric_swing():
    """The asymmetric (back, forward) pivot must also be look-ahead-free: the
    confirmation lag equals `forward`, never less."""
    df = _synthetic_ohlc(seed=11)
    costs = SmcCosts(commission_bps=1.0, spread_bps=1.0)
    full = run_smc_backtest(df, direction="both", n=8, forward=2, risk_frac=0.01,
                            costs=costs)["trades"]
    assert len(full) > 5
    for t in (300, 500, 700):
        boundary = df.index[t - 1]
        trunc = run_smc_backtest(df.iloc[:t], direction="both", n=8, forward=2,
                                 risk_frac=0.01, costs=costs)["trades"]
        a = _completed_before(trunc, boundary)
        b = _completed_before(full, boundary)
        assert len(a) == len(b), f"asymmetric trade count diverges at t={t}"
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_swing_confirmation_lag_is_respected():
    """A pivot must not influence any decision before it is confirmed (Bildung+N)."""
    from quantlab.smc.structure import swing_points

    df = _synthetic_ohlc(300, seed=3)
    is_high, is_low = swing_points(df["High"], df["Low"], back=2, forward=2)
    # Every labelled pivot has the required clearance on both sides (i.e. the
    # label genuinely needs N future bars, which the loop only consults at i+N).
    h = df["High"].to_numpy()
    for i in np.where(is_high)[0]:
        assert h[i] > h[i - 2:i].max() and h[i] > h[i + 1:i + 3].max()
