"""Tests for roll-adjustment — the fix that turned 0048 from a roll artifact into
an honest result. The stitch gap on a roll day must be removed; the real
intra-contract returns must be preserved.
"""

import numpy as np
import pandas as pd

from quantlab.futures_curve import roll_adjusted_close, carry_signal


def test_roll_gap_is_removed():
    """A fabricated +20% stitch jump on the roll day must not enter the return."""
    dates = pd.bdate_range("2020-01-01", periods=6)
    # Contract A: 100 -> 101 -> 102, then roll to contract B at a 120 stitch level.
    close = pd.Series([100, 101, 102, 120, 121, 122], index=dates, dtype=float)
    iid = pd.Series([1, 1, 1, 2, 2, 2], index=dates)
    adj = roll_adjusted_close(close, iid)
    rets = adj.pct_change().dropna()
    # No day may carry the ~+18% gap; all returns are the smooth ~+1% moves.
    assert rets.abs().max() < 0.05
    # The roll day itself is zeroed.
    assert abs(rets.loc[dates[3]]) < 1e-12


def test_intra_contract_returns_preserved():
    dates = pd.bdate_range("2020-01-01", periods=4)
    close = pd.Series([100, 110, 99, 108.9], index=dates, dtype=float)  # +10%, roll, +10%
    iid = pd.Series([1, 1, 2, 2], index=dates)
    adj = roll_adjusted_close(close, iid)
    rets = adj.pct_change().dropna()
    assert abs(rets.iloc[0] - 0.10) < 1e-9   # +10% within contract A
    assert abs(rets.iloc[1]) < 1e-12         # roll day zeroed
    assert abs(rets.iloc[2] - 0.10) < 1e-9   # +10% within contract B


def test_carry_signal_sign():
    """Backwardation (front > second) must give positive carry."""
    dates = pd.bdate_range("2020-01-01", periods=3)
    back = pd.DataFrame({"front": [102.0] * 3, "second": [100.0] * 3}, index=dates)
    cont = pd.DataFrame({"front": [100.0] * 3, "second": [102.0] * 3}, index=dates)
    sig = carry_signal({"BACK": back, "CONT": cont}, annualize=False)
    assert (sig["BACK"] > 0).all()
    assert (sig["CONT"] < 0).all()
