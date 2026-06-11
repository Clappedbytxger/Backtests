"""Survivorship + PIT gates for the crypto cross-section universe (Pflicht).

Roadmap Teil 5/7: a universe built from today's coins projected backwards is
fiction. These tests prove, on the REAL cached data, that

1. the historical universe contains coins that later died or were delisted
   (LUNA pre-crash, FTT pre-collapse, BCC/Bitcoin-Cash-era, XEM/MIOTA fade),
2. a coin enters the panel only at/after its actual Binance listing and its
   snapshot membership only at/after the snapshot date (no listing or
   market-cap look-ahead),
3. membership applied on day t never uses a snapshot taken after t,
4. synthetic-feature sanity: forward targets at t are NaN unless the coin
   still prints a bar at t+h (no resurrecting the dead for labels).

They require the Parquet cache (run ``scripts/fetch_crypto_universe.py``
once, sandbox off); if the cache is missing the module is skipped, never
silently passed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab import crypto_xsection as cx


def _has_cache() -> bool:
    return any((cx.CACHE_DIR / "cmc").glob("snap_*.parquet"))


pytestmark = pytest.mark.skipif(
    not _has_cache(), reason="crypto cache missing — run tmp_fetch_universe.py first"
)


@pytest.fixture(scope="module")
def universe():
    return cx.build_universe(top_n=150)


@pytest.fixture(scope="module")
def panels(universe):
    return cx.get_price_panels(universe)


# ---------------------------------------------------------------------------
# 1. Dead coins are demonstrably IN the historical universe
# ---------------------------------------------------------------------------

def test_dead_coins_present_at_their_time(universe):
    cases = {
        # pair, a date it must be a member, because it later died/collapsed
        "LUNAUSDT": "2022-04-01",   # Terra, -99.99% May 2022, later delisted
        "FTTUSDT": "2022-10-01",    # FTX token, collapsed Nov 2022
        "SRMUSDT": "2022-06-15",    # Serum (rank ~122 then), dead post-FTX, delisted
        "ANCUSDT": "2022-03-01",    # Anchor, died with Terra
        "XEMUSDT": "2021-06-01",    # NEM, top-10 2018, faded, delisted 2023+
    }
    for pair, date in cases.items():
        members = cx.get_universe_at(universe, date)
        assert pair in members, f"{pair} missing from PIT universe at {date}"


def test_universe_contains_pairs_dead_today(universe, panels):
    """At least 10% of all pairs ever in the universe stopped printing bars
    >30 days before the panel end — the graveyard is real, not decorative."""
    close = panels["close"]
    cutoff = close.index[-1] - pd.Timedelta(days=30)
    dead = [c for c in close.columns if close[c].last_valid_index() < cutoff]
    assert len(dead) >= 0.10 * len(close.columns), (
        f"only {len(dead)}/{len(close.columns)} dead pairs — survivorship suspicious"
    )


def test_dead_coin_leaves_panel(panels):
    """A delisted coin's membership ends; it cannot be held after death."""
    md = panels["membership_daily"]
    close = panels["close"]
    for pair in ["SRMUSDT", "ANCUSDT"]:
        if pair not in md.columns:
            pytest.skip(f"{pair} not in panel")
        last_bar = close[pair].last_valid_index()
        assert last_bar < md.index[-1] - pd.Timedelta(days=180), f"{pair} not dead?"
        assert not md[pair].loc[last_bar + pd.Timedelta(days=1):].any(), (
            f"{pair} still a member after its last bar"
        )


# ---------------------------------------------------------------------------
# 2./3. No listing / market-cap look-ahead
# ---------------------------------------------------------------------------

def test_no_membership_before_listing(panels):
    """membership_daily requires an actual printed bar — a coin ranked by CMC
    but not yet tradable on Binance is not investable."""
    md, close = panels["membership_daily"], panels["close"]
    assert not (md & close.isna()).any().any()


def test_membership_uses_only_past_snapshots(universe, panels):
    """Day-t membership equals the latest snapshot strictly BEFORE t
    (1-day PIT lag), intersected with tradability — verified by
    reconstruction on sample dates."""
    md = panels["membership_daily"]
    close = panels["close"]
    memb_w = universe["membership"]
    rng = np.random.default_rng(42)
    sample = rng.choice(len(md.index[400:]), size=25, replace=False)
    parents = [c.split("~")[0] for c in md.columns]
    vol60 = panels["ret"].rolling(60, min_periods=30).std() * np.sqrt(365)
    for i in sample:
        t = md.index[400:][i]
        snaps = memb_w.index[memb_w.index + pd.Timedelta(days=1) <= t]
        if len(snaps) == 0:
            continue
        expected = memb_w.loc[snaps[-1]].reindex(parents, fill_value=False)
        expected.index = md.columns
        expected = expected & close.loc[t].notna()
        expected &= ~(vol60.loc[t] < 0.10).fillna(False)  # pegged-asset guard
        pd.testing.assert_series_equal(md.loc[t], expected, check_names=False)


def test_mcap_is_pit(universe, panels):
    """mcap_daily at t must equal a snapshot value taken before t, never a
    later (future) snapshot's value."""
    mcap_d = panels["mcap_daily"]
    mcap_w = universe["mcap"]
    t = mcap_d.index[len(mcap_d) // 2]
    snaps_before = mcap_w.index[mcap_w.index + pd.Timedelta(days=1) <= t]
    latest = mcap_w.loc[snaps_before[-1]]
    row = mcap_d.loc[t].dropna()
    aligned = latest.reindex([c.split("~")[0] for c in row.index])
    aligned.index = row.index
    assert ((row == aligned) | aligned.isna()).all()


# ---------------------------------------------------------------------------
# 4. Targets cannot resurrect the dead
# ---------------------------------------------------------------------------

def test_forward_target_nan_when_coin_dies(panels):
    from quantlab import crypto_features as cf

    fp = cf.build_feature_panels(panels)
    close = panels["close"]
    for pair in ["SRMUSDT", "LUNAUSDT"]:
        if pair not in close.columns:
            continue
        last_bar = close[pair].last_valid_index()
        tgt = fp["targets_raw"][28][pair]
        # within 28d of death the 28d-forward target must be NaN
        window = tgt.loc[last_bar - pd.Timedelta(days=27): last_bar]
        assert window.isna().all(), f"{pair} has forward targets into its death"


def test_planted_clairvoyant_is_impossible(panels):
    """Engine-level guard (mirrors cross_sectional's planted-seer test): a
    prediction panel built from the FUTURE return must earn exactly that
    future return only via shift(1) — i.e. the portfolio engine must lag
    holdings. Verifies the chain end-to-end on real crypto data."""
    from quantlab.ml_portfolio import run_ml_portfolio

    ret = panels["ret"].iloc[-400:]
    md = panels["membership_daily"].iloc[-400:]
    # clairvoyant: knows tomorrow's return today
    clair = ret.shift(-1).where(md)
    res = run_ml_portfolio(ret, clair, rebalance="W", cost_bps_per_side=0.0)
    held = res["weights"]
    # holdings on day t must be decided strictly before t: weight changes
    # only on the day AFTER a rebalance date
    rb = set(res["rebalance_dates"])
    changes = held.diff().abs().sum(axis=1)
    changed_days = set(changes.index[changes > 1e-12])
    allowed = {d for d in changed_days if any(
        (d - pd.Timedelta(days=k)) in rb for k in (1, 2, 3)
    )}
    assert changed_days == allowed
