"""Pegged-asset guard: stablecoins that slip past the name list must be
excluded by the trailing-vol guard (the RLUSD/'United Stables' lesson —
inverse-vol weighting otherwise lets a peg swallow the book)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab import crypto_xsection as cx


def _has_cache() -> bool:
    return any((cx.CACHE_DIR / "cmc").glob("snap_*.parquet"))


pytestmark = pytest.mark.skipif(
    not _has_cache(), reason="crypto cache missing — run scripts/fetch_crypto_universe.py"
)


def test_named_stables_excluded():
    assert "RLUSD" in cx.EXCLUDED_SYMBOLS
    assert "U" in cx.EXCLUDED_SYMBOLS


def test_no_low_vol_members():
    """No member-day may have trailing annualized vol < 10%."""
    uni = cx.build_universe(top_n=150)
    panels = cx.get_price_panels(uni)
    ret, memb = panels["ret"], panels["membership_daily"]
    vol60 = ret.rolling(60, min_periods=30).std() * np.sqrt(365)
    offenders = (memb & (vol60 < 0.10)).sum()
    offenders = offenders[offenders > 0]
    assert offenders.empty, f"pegged members slipped through: {offenders.to_dict()}"
