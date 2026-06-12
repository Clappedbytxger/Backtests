"""Guards für die Live-Paper-Logik (Phase 3, eingefrorene 0063/0064-Regel).

Netzfrei: gefakte Odds-API-Payloads. Abgesichert wird:
  * H2H-Extraktion liefert [H, D, A] in der richtigen Reihenfolge;
  * find_value_bets rechnet EV gegen Shin-faire Pinnacle-Probs, nimmt die
    BESTE Soft-Book-Quote, respektiert Schwelle und EV-Cap;
  * fehlender Pinnacle / fehlendes Draw-Outcome => kein Alert;
  * scharfe Bücher (Pinnacle selbst) zählen nie als Soft-Book-Quote;
  * fair_close_prob == Shin-De-Vig des Schluss-Tripels;
  * kelly_stake respektiert den 2%-Cap und ist 0 bei negativem Edge.
"""

import numpy as np
import pytest

from quantlab.devig import devig
from quantlab.odds_live import (
    fair_close_prob, find_value_bets, h2h_odds, kelly_stake,
)


def make_event(books: dict[str, list[float]], home="Heim FC", away="Gast SV") -> dict:
    """Fake-Event: books = {bookmaker_key: [oH, oD, oA]}."""
    return {
        "id": "ev1",
        "sport_key": "soccer_test",
        "commence_time": "2026-08-15T14:00:00Z",
        "home_team": home,
        "away_team": away,
        "bookmakers": [
            {
                "key": key,
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": home, "price": o[0]},
                        {"name": "Draw", "price": o[1]},
                        {"name": away, "price": o[2]},
                    ],
                }],
            }
            for key, o in books.items()
        ],
    }


PIN = [2.10, 3.40, 3.60]


def test_h2h_extraction_order():
    ev = make_event({"pinnacle": PIN})
    odds = h2h_odds(ev, "pinnacle")
    assert np.allclose(odds, PIN)  # [H, D, A]
    assert h2h_odds(ev, "bet365") is None


def test_value_bet_found_with_best_book():
    fair = devig(np.array(PIN), method="shin")
    # bet365 bietet Draw 3.40*(1.05/fair-Faktor) hoch genug für >2% EV,
    # tipico etwas weniger — der Alert muss bet365 (beste Quote) nehmen.
    draw_odds_365 = (1.03) / fair[1]  # EV = +3%
    draw_odds_tip = (1.025) / fair[1]
    ev = make_event({
        "pinnacle": PIN,
        "bet365": [2.05, draw_odds_365, 3.50],
        "tipico": [2.00, draw_odds_tip, 3.45],
    })
    alerts = find_value_bets(ev)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["outcome"] == "D"
    assert a["bookmaker"] == "bet365"
    assert a["ev"] == pytest.approx(0.03, abs=1e-9)
    assert a["fair_p_bet"] == pytest.approx(fair[1])


def test_threshold_and_cap():
    fair = devig(np.array(PIN), method="shin")
    below = make_event({"pinnacle": PIN, "bet365": [2.05, 1.01 / fair[1], 3.50]})
    assert find_value_bets(below) == []  # +1% < Schwelle
    typo = make_event({"pinnacle": PIN, "bet365": [2.05, 1.50 / fair[1], 3.50]})
    assert find_value_bets(typo) == []  # +50% > EV-Cap (Datenfehler-Guard)


def test_no_pinnacle_or_no_draw_means_no_alert():
    no_pin = make_event({"bet365": [2.50, 3.80, 4.00]})
    assert find_value_bets(no_pin) == []
    ev = make_event({"pinnacle": PIN, "bet365": [9.99, 9.99, 9.99]})
    ev["bookmakers"][0]["markets"][0]["outcomes"] = [
        {"name": "Heim FC", "price": 2.10},
        {"name": "Gast SV", "price": 3.60},  # kein Draw -> Pinnacle unvollständig
    ]
    assert find_value_bets(ev) == []


def test_sharp_books_never_count_as_soft():
    # Pinnacle selbst mit "zu hoher" Quote darf keinen Alert erzeugen.
    ev = make_event({"pinnacle": PIN})
    assert find_value_bets(ev) == []


def test_fair_close_prob_matches_shin():
    close = np.array([1.95, 3.50, 4.10])
    p = devig(close, method="shin")
    assert fair_close_prob(close, "H") == pytest.approx(p[0])
    assert fair_close_prob(close, "A") == pytest.approx(p[2])


def test_kelly_stake_cap_and_zero():
    assert kelly_stake(0.5, 2.5) == pytest.approx(0.02)  # großer Edge -> Cap
    assert kelly_stake(0.30, 3.5, fraction=0.25) == pytest.approx(
        0.25 * (0.30 * 3.5 - 1) / 2.5)
    assert kelly_stake(0.20, 3.0) == 0.0  # negativer Edge -> keine Wette
