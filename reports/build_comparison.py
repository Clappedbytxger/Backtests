"""Cross-strategy comparison — global view over all tested strategies.

Scans every ``strategies/XXXX_*/results`` folder for the standardized artifacts
each run emits (``card.json`` with headline risk/return numbers and
``equity.csv`` with the net equity curve), then produces:

  * ``plots/all_equity.png``      — every strategy's equity curve, rebased to 1
  * ``plots/risk_return.png``     — volatility vs CAGR scatter (bubble = Sharpe)
  * ``OVERVIEW.md``               — a German summary table (aligned source)

Run:
    .venv/Scripts/python.exe reports/build_comparison.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import plotting  # noqa: E402
from quantlab.reporting import markdown_table  # noqa: E402

REPORTS = ROOT / "reports"
PLOTS = REPORTS / "plots"
STRAT_DIR = ROOT / "strategies"

# Pretty display names for any tickers that leak into a card label.
TICKER_NAMES = {
    "^GDAXI": "DAX", "^FTSE": "FTSE 100", "^N225": "Nikkei 225",
    "SPY": "S&P 500", "QQQ": "Nasdaq 100",
}


def prettify(label: str) -> str:
    for tk, name in TICKER_NAMES.items():
        label = label.replace(tk, name)
    return label


def collect() -> tuple[dict[str, pd.Series], list[dict]]:
    equities: dict[str, pd.Series] = {}
    cards: list[dict] = []
    for d in sorted(STRAT_DIR.glob("[0-9][0-9][0-9][0-9]_*")):
        res = d / "results"
        card_p, eq_p = res / "card.json", res / "equity.csv"
        if not card_p.exists() or not eq_p.exists():
            continue
        card = json.loads(card_p.read_text())
        card["label"] = f"{card['id']} {prettify(card['label'])}"
        cards.append(card)
        eq = pd.read_csv(eq_p, index_col=0, parse_dates=True).iloc[:, 0]
        equities[card["label"]] = eq
    return equities, cards


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    equities, cards = collect()
    if not cards:
        raise SystemExit("No strategy cards found — run the strategies first.")

    plotting.savefig(
        plotting.plot_strategy_comparison(
            equities,
            title="Alle Strategien im Vergleich — Kapitalkurven (OOS)",
            caption=("Netto-Kapitalkurven aller bisher getesteten Strategien, jeweils "
                     "auf 1 normiert und log-skaliert. So sind Strategien mit "
                     "unterschiedlichem Startkapital und Zeitraum direkt vergleichbar."),
        ),
        PLOTS / "all_equity.png")

    plotting.savefig(
        plotting.plot_risk_return(
            cards,
            title="Risiko-Rendite-Profil aller Strategien",
            caption=("Jede Blase ist eine Strategie: x = annualisierte Volatilität "
                     "(Risiko), y = CAGR (jährliche Rendite), Blasengröße = Sharpe "
                     "Ratio. Oben-links ist besser (mehr Rendite bei weniger Risiko)."),
        ),
        PLOTS / "risk_return.png")

    headers = ["ID", "Strategie", "CAGR", "Volatilität", "Sharpe", "Max DD"]
    rows = []
    for c in sorted(cards, key=lambda x: x["id"]):
        rows.append([
            c["id"],
            prettify(c["label"]).split(" ", 1)[1],
            f"{c['cagr']:.2%}",
            f"{c['annual_volatility']:.2%}",
            f"{c['sharpe']:.2f}",
            f"{c['max_drawdown']:.2%}",
        ])
    table = markdown_table(headers, rows, align=["l", "l", "r", "r", "r", "r"])

    overview = f"""# Strategie-Übersicht — globaler Vergleich

Automatisch erzeugt aus den Ergebnissen aller getesteten Strategien
(`reports/build_comparison.py`). Alle Zahlen sind **out-of-sample, netto nach
Kosten**.

## Kennzahlen im Vergleich

{table}

## Visualisierungen

![Kapitalkurven aller Strategien](plots/all_equity.png)

*Kapitalkurven aller Strategien, auf 1 normiert (log-Skala) — direkt vergleichbar
unabhängig vom Startkapital.*

![Risiko-Rendite-Profil](plots/risk_return.png)

*Risiko-Rendite-Profil: x = Volatilität (Risiko), y = CAGR (Rendite),
Blasengröße = Sharpe Ratio. Oben-links ist besser.*

## Einordnung

Bisher hat **keine** Strategie einen statistisch signifikanten Renditevorteil
gegenüber Buy & Hold gezeigt. Der gepoolte Sell-in-May-Ansatz (0002) hebt zwar
den Sharpe gegenüber jedem Einzelmarkt (Diversifikation) und senkt die
Volatilität, bleibt aber netto hinter Buy & Hold zurück und ist im
Permutationstest nicht signifikant. Der Wert des Effekts liegt damit in der
**Risikoreduktion** (Volatilitäts-Overlay), nicht in zusätzlicher Rendite.
"""
    (REPORTS / "OVERVIEW.md").write_text(overview, encoding="utf-8")
    print(f"  wrote {REPORTS / 'OVERVIEW.md'}")
    print(f"  plots -> {PLOTS}")
    for c in cards:
        print(f"   {c['id']}  Sharpe {c['sharpe']:.2f}  CAGR {c['cagr']:.2%}")


if __name__ == "__main__":
    main()
