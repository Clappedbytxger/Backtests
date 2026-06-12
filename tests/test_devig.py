"""Guards for the de-vig module (Phase 0 gate of the football program).

Properties that must hold:
  * every method returns probabilities summing to exactly 1;
  * a zero-margin book is returned unchanged by all methods;
  * Shin and power shift margin onto longshots (longshot prob below
    multiplicative, favourite prob above) — the bias they exist to fix;
  * margin() reproduces the overround;
  * invalid rows (NaN / odds <= 1) yield NaN, valid rows are unaffected.
"""

import numpy as np
import pytest

from quantlab.devig import METHODS, devig, fair_odds, margin

# A typical 1X2 market with ~5% overround and a clear longshot (away).
ODDS_1X2 = np.array([1.50, 4.20, 7.00])
# A 2-way market (e.g. over/under) with ~3% margin.
ODDS_2WAY = np.array([1.87, 2.05])


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("odds", [ODDS_1X2, ODDS_2WAY])
def test_probabilities_sum_to_one(method, odds):
    p = devig(odds, method=method)
    assert np.isclose(p.sum(), 1.0, atol=1e-9)
    assert (p > 0).all() and (p < 1).all()


@pytest.mark.parametrize("method", METHODS)
def test_zero_margin_is_identity(method):
    p_true = np.array([0.5, 0.3, 0.2])
    odds = 1.0 / p_true  # fair book, overround exactly 0
    p = devig(odds, method=method)
    assert np.allclose(p, p_true, atol=1e-9)


def test_margin_reproduces_overround():
    assert np.isclose(margin(ODDS_1X2), (1 / ODDS_1X2).sum() - 1)
    book = np.vstack([ODDS_1X2, ODDS_2WAY[[0, 1, 0]]])
    assert margin(book).shape == (2,)
    assert (margin(book) > 0).all()


@pytest.mark.parametrize("method", ["shin", "power"])
def test_longshot_bias_correction(method):
    p_mult = devig(ODDS_1X2, method="multiplicative")
    p = devig(ODDS_1X2, method=method)
    # Longshot (index 2) gets LESS probability than proportional scaling,
    # favourite (index 0) gets MORE.
    assert p[2] < p_mult[2]
    assert p[0] > p_mult[0]


def test_vectorized_panel_and_invalid_rows():
    panel = np.array(
        [
            [1.50, 4.20, 7.00],
            [np.nan, 4.20, 7.00],  # missing quote
            [0.95, 4.20, 7.00],  # impossible decimal odd
            [2.10, 3.30, 3.90],
        ]
    )
    for method in METHODS:
        p = devig(panel, method=method)
        assert p.shape == panel.shape
        assert np.isclose(p[0].sum(), 1.0) and np.isclose(p[3].sum(), 1.0)
        assert np.isnan(p[1]).all() and np.isnan(p[2]).all()


def test_fair_odds_inverts_probabilities():
    fo = fair_odds(ODDS_1X2, method="multiplicative")
    assert np.allclose(1.0 / fo, devig(ODDS_1X2, method="multiplicative"))
    # Fair odds must be longer than quoted odds (margin removed).
    assert (fo > ODDS_1X2).all()


def test_shin_margin_split_more_uneven_than_multiplicative():
    """Shin's haircut on the longshot exceeds its proportional share."""
    pi = 1 / ODDS_1X2
    p_shin = devig(ODDS_1X2, method="shin")
    haircut = pi / pi.sum() - p_shin  # multiplicative minus shin
    # Haircut should increase from favourite to longshot.
    assert haircut[2] > 0 > haircut[0]
