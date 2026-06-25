"""Trailing-stop & fixed-1R invariants (spec Teil 4 step 4 + Teil 1 exit logic).

Pins the 1R-step ratchet, the conservative same-bar convention (stop before the
next R-level / before the target) and gap fills (never better than the gap open).
"""

from quantlab.smc.exits import Fixed1R, TrailingStop


def test_trailing_locks_breakeven_at_1r():
    t = TrailingStop(direction=1, entry=100.0, r=10.0)
    assert t.stop == 90.0
    # Reach +1R (high 111) without breaching the initial stop -> stop to BE.
    assert t.update(high=111, low=95, open_=100) is None
    assert t.locked == 1 and t.stop == 100.0
    # Reach +2R -> stop to entry+1R.
    assert t.update(high=121, low=101, open_=111) is None
    assert t.locked == 2 and t.stop == 110.0


def test_trailing_exit_at_trailed_stop():
    t = TrailingStop(direction=1, entry=100.0, r=10.0)
    t.update(high=121, low=95, open_=100)   # locks +2R region; stop -> 110
    assert t.locked == 2 and t.stop == 110.0
    fill = t.update(high=112, low=109, open_=111)   # low pierces 110
    assert fill is not None and fill.reason == "trail"
    assert fill.price == 110.0 and fill.r_locked == 2


def test_same_bar_stop_beats_next_level():
    """Conservative: if a bar both reaches the next R-level and breaches the
    current stop, the stop is hit first (no further lock)."""
    t = TrailingStop(direction=1, entry=100.0, r=10.0)
    t.update(high=111, low=101, open_=100)   # lock +1R -> stop = BE (100)
    assert t.locked == 1 and t.stop == 100.0
    fill = t.update(high=121, low=99, open_=100.5)   # reaches +2R AND hits 100
    assert fill is not None and fill.price == 100.0   # exit at BE, not a +1R lock
    assert t.locked == 1


def test_initial_stop_and_gap_fill():
    t = TrailingStop(direction=1, entry=100.0, r=10.0)
    fill = t.update(high=92, low=80, open_=85)   # gap opens below the 90 stop
    assert fill is not None and fill.reason == "stop"
    assert fill.price == 85.0   # filled at the gap open, worse than the stop


def test_trailing_short_mirror():
    t = TrailingStop(direction=-1, entry=100.0, r=10.0)
    assert t.stop == 110.0
    assert t.update(high=105, low=89, open_=100) is None   # reaches +1R (90)
    assert t.locked == 1 and t.stop == 100.0               # stop to BE
    fill = t.update(high=101, low=95, open_=99)            # high pierces BE
    assert fill is not None and fill.price == 100.0


def test_fixed1r_target_and_stop_precedence():
    f = Fixed1R(direction=1, entry=100.0, r=10.0)
    assert f.target == 110.0 and f.stop == 90.0
    fill = f.update(high=111, low=95, open_=100)   # clean target hit
    assert fill is not None and fill.reason == "target" and fill.price == 110.0

    f2 = Fixed1R(direction=1, entry=100.0, r=10.0)
    fill2 = f2.update(high=111, low=89, open_=100)  # both touched -> stop first
    assert fill2 is not None and fill2.reason == "stop" and fill2.price == 90.0
