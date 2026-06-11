"""Live-Signal der eingefrorenen 0059/0060-Regel — aktuelles Monats-Buch.

Reproduziert den Walk-Forward-Zustand bis heute und druckt das aktuelle
Zielbuch (inkl. Buffer-Zustand, der sich aus der Pfad-Historie ergibt —
stateless korrekt, solange immer dieselbe Pipeline läuft).

Primäre Live-Variante (registriert 2026-06-11): LGBM0, h=28, Monats-
Rebalance, Dezil long-only mit min. Buchgröße 12, Hold-Band-Buffer 2x,
Liquiditäts-Floor $5M, inverse-Vol-Gewichte. Sekundär: dasselbe ohne
min_k-Floor (Original-0059-Regel).

Aufruf (monatlich nach Monatsende, Sandbox off für den Refresh):
    python scripts/crypto_live_signal.py --refresh   # Daten aktualisieren
    python scripts/crypto_live_signal.py             # nur Cache
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="X does not have valid feature names")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "strategies" / "0060_crypto_walkforward"))

import pandas as pd  # noqa: E402

from quantlab import crypto_features as cf  # noqa: E402
from quantlab import crypto_xsection as cx  # noqa: E402


def refresh_caches() -> None:
    """Re-pull CMC snapshots (new weeks only) and ALL kline series (full)."""
    print("Refreshe CMC-Snapshots ...")
    cx.get_cmc_history()
    uni = cx.build_universe()
    pairs = list(uni["membership"].columns)
    print(f"Refreshe {len(pairs)} Kline-Serien (force) ...")
    for i, p in enumerate(pairs):
        cx.get_binance_daily(p, force_refresh=True)
        if i % 50 == 0:
            print(f"  {i}/{len(pairs)}")


def main() -> None:
    if "--refresh" in sys.argv:
        refresh_caches()

    from run import (  # 0060 pipeline — single source of truth
        HORIZON, MIN_NAMES, TOP_N, frozen_portfolio, make_lgbm,
        walk_forward_predictions,
    )

    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    ret, vol30 = fp["returns"], fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol = fp["dvol_med21"]

    df = cf.assemble_design_matrix(fp, horizon=HORIZON, min_names=MIN_NAMES)
    df_score = cf.assemble_design_matrix(
        fp, horizon=HORIZON, min_names=MIN_NAMES, require_target=False
    )
    preds = walk_forward_predictions(
        df, make_lgbm, fillna_zero=False, score_df=df_score
    )

    for label, min_k in [("PRIMÄR (min. Buch 12)", 12), ("sekundär (0059-Original)", 1)]:
        port = frozen_portfolio(preds, ret, vol30, costs, dvol, min_k=min_k)
        held = port["weights"]
        book = held.iloc[-1]
        book = book[book > 0].sort_values(ascending=False)
        changes = held.diff().abs().sum(axis=1)
        formed = changes[changes > 1e-12].index[-1] if (changes > 1e-12).any() else held.index[0]
        print(f"\n=== {label} — aktuelles Buch (geformt {formed:%Y-%m-%d}, "
              f"Stand {held.index[-1]:%Y-%m-%d}) ===")
        for pair, w in book.items():
            print(f"  {pair:14s} {w:6.1%}")
        print(f"  ({len(book)} Namen, Summe {book.sum():.0%})")


if __name__ == "__main__":
    main()
