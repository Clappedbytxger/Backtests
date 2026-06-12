"""The Odds API client + eingefrorene Value-Bet-Logik für den Live-Paper-Forward.

API: https://the-odds-api.com (v4). Gratis-Tier ~500 Credits/Monat.
Kosten: ``/sports`` und ``/events`` = 0 Credits; ``/odds`` = 1 Credit je
Region×Markt; ``/scores`` mit ``daysFrom`` = 2 Credits. Der Client liest das
verbleibende Kontingent aus den Response-Headern.

Key: Env ``ODDS_API_KEY`` oder gitignored ``D:/Backtests/.oddsapi.key``
(Registrierung gratis auf the-odds-api.com).

Die reine Alert-/CLV-Logik (``h2h_odds``, ``find_value_bets``, ``fair_close_prob``)
ist netzfrei und in ``tests/test_odds_live.py`` abgesichert. Eingefrorene Regel
aus 0063/0064: Shin-De-Vig auf Pinnacle, EV > 2 %, EV-Cap 20 %.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import requests

from quantlab.devig import devig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://api.the-odds-api.com/v4"

OUTCOMES = ("H", "D", "A")

# Soft Books (Allowlist) — scharfe Bücher/Exchanges bewusst NICHT dabei
# (pinnacle, betfair, matchbook, smarkets). Unbekannte Keys matchen einfach nie.
SOFT_BOOKS = (
    "bet365", "tipico", "winamax_de", "winamax_fr", "unibet_eu", "betsson",
    "betway", "sport888", "betclic", "onexbet", "williamhill", "marathonbet",
    "betano", "leovegas", "coolbet", "nordicbet",
)


def read_odds_api_key(explicit: str | None = None) -> str:
    """Key-Auflösung: explizit > Env ``ODDS_API_KEY`` > ``.oddsapi.key``."""
    if explicit:
        return explicit
    env = os.environ.get("ODDS_API_KEY")
    if env:
        return env
    keyfile = _PROJECT_ROOT / ".oddsapi.key"
    if keyfile.exists():
        return keyfile.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "Kein Odds-API-Key. Gratis registrieren auf https://the-odds-api.com, "
        f"dann Key in {keyfile} legen oder $ODDS_API_KEY setzen."
    )


class OddsApiClient:
    """Dünner v4-Client mit Quota-Tracking aus den Response-Headern."""

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = read_odds_api_key(api_key)
        self.timeout = timeout
        self.remaining: int | None = None
        self.used: int | None = None

    def _get(self, path: str, **params) -> list | dict:
        params["apiKey"] = self.api_key
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        if "x-requests-remaining" in resp.headers:
            self.remaining = int(float(resp.headers["x-requests-remaining"]))
            self.used = int(float(resp.headers["x-requests-used"]))
        return resp.json()

    def get_sports(self) -> list[dict]:
        """Alle Sport-Keys (kostenlos)."""
        return self._get("/sports", all="true")

    def get_events(self, sport_key: str) -> list[dict]:
        """Kommende Events einer Liga OHNE Quoten (kostenlos) — für den
        Vorab-Check, ob sich ein /odds-Call (1 Credit) lohnt."""
        return self._get(f"/sports/{sport_key}/events")

    def get_odds(self, sport_key: str) -> list[dict]:
        """H2H-Quoten (EU-Region inkl. Pinnacle + Soft Books). Kostet 1 Credit."""
        return self._get(
            f"/sports/{sport_key}/odds",
            regions="eu",
            markets="h2h",
            oddsFormat="decimal",
        )

    def get_scores(self, sport_key: str, days_from: int = 3) -> list[dict]:
        """Ergebnisse der letzten ``days_from`` Tage. Kostet 2 Credits."""
        return self._get(f"/sports/{sport_key}/scores", daysFrom=days_from)


# --------------------------------------------------------------------------
# Reine Logik (netzfrei, getestet)
# --------------------------------------------------------------------------

def h2h_odds(event: dict, book_key: str) -> np.ndarray | None:
    """1X2-Dezimalquoten eines Buchmachers als ``[H, D, A]`` oder None."""
    for bm in event.get("bookmakers", []):
        if bm.get("key") != book_key:
            continue
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            prices = {o["name"]: o["price"] for o in market.get("outcomes", [])}
            h = prices.get(event["home_team"])
            d = prices.get("Draw")
            a = prices.get(event["away_team"])
            if h and d and a:
                return np.array([h, d, a], dtype=float)
    return None


def fair_close_prob(pinnacle_close: np.ndarray, outcome: str) -> float:
    """Shin-de-viggte faire Wahrscheinlichkeit eines Outcomes aus [H,D,A]-Quoten."""
    p = devig(np.asarray(pinnacle_close, dtype=float), method="shin")
    return float(p[OUTCOMES.index(outcome)])


def find_value_bets(
    event: dict,
    threshold: float = 0.02,
    ev_cap: float = 0.20,
    soft_books: tuple[str, ...] = SOFT_BOOKS,
) -> list[dict]:
    """Eingefrorene 0063-Regel auf einem Odds-API-Event.

    Shin-de-vigt Pinnacle, sucht je Outcome die BESTE Soft-Book-Quote und
    alarmiert bei ``threshold < EV <= ev_cap`` (Cap = Datenfehler-Guard).
    Eine Wette je (Event, Outcome) — die beste Quote, wie ein Bettor mit
    mehreren Konten sie nähme.
    """
    pin = h2h_odds(event, "pinnacle")
    if pin is None:
        return []
    fair_p = devig(pin, method="shin")

    alerts: list[dict] = []
    for i, outcome in enumerate(OUTCOMES):
        best_odds, best_book = 0.0, None
        for book in soft_books:
            odds = h2h_odds(event, book)
            if odds is not None and odds[i] > best_odds:
                best_odds, best_book = float(odds[i]), book
        if best_book is None:
            continue
        ev = best_odds * float(fair_p[i]) - 1.0
        if threshold < ev <= ev_cap:
            alerts.append({
                "event_id": event["id"],
                "sport_key": event.get("sport_key", ""),
                "commence_time": event["commence_time"],
                "home": event["home_team"],
                "away": event["away_team"],
                "outcome": outcome,
                "bookmaker": best_book,
                "odds": best_odds,
                "fair_p_bet": float(fair_p[i]),
                "ev": float(ev),
                "pin_h": float(pin[0]),
                "pin_d": float(pin[1]),
                "pin_a": float(pin[2]),
            })
    return alerts


def kelly_stake(fair_p: float, odds: float, fraction: float = 0.25, cap: float = 0.02) -> float:
    """¼-Kelly-Anteil der Bankroll, Cap 2 % (eingefroren aus 0064)."""
    f = fraction * (fair_p * odds - 1.0) / (odds - 1.0)
    return float(np.clip(f, 0.0, cap))
