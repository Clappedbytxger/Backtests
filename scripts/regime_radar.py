"""Market Weather Radar — terminal demo of the regime classifier.

Classifies a basket of liquid assets into the four market regimes and prints:
  1. a current-regime snapshot per asset (the "weather" right now),
  2. the most recent regime transitions for one asset (when it flipped),
  3. the share of time each asset spent in each regime.

Run:
    .venv/Scripts/python.exe scripts/regime_radar.py
    .venv/Scripts/python.exe scripts/regime_radar.py SPY QQQ GLD --years 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from quantlab import regime  # noqa: E402
from quantlab.data import get_close, get_prices  # noqa: E402

DEFAULT_TICKERS = ["SPY", "QQQ", "GLD", "TLT", "BTC-USD"]

# tiny ANSI helpers so the radar reads like a terminal, not a log dump
_HEX = {"high_vol_trend": "\033[91m", "low_vol_trend": "\033[92m",
        "high_vol_range": "\033[93m", "low_vol_range": "\033[90m"}
_RESET = "\033[0m"
_BOLD = "\033[1m"


def _swatch(code: str | None) -> str:
    if not code:
        return "·"
    return f"{_HEX.get(code, '')}██{_RESET}"


def run(tickers: list[str], years: int) -> None:
    start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")

    # VIX once, reused for equity-style assets (blended into their vol axis)
    try:
        vix = get_close("^VIX", start=start)
    except Exception:  # noqa: BLE001 - VIX is optional
        vix = None

    print(f"\n{_BOLD}╔══ MARKET WEATHER RADAR ══════════════════════════════════════════╗{_RESET}")
    print(f"{_BOLD}║ as of {pd.Timestamp.today().strftime('%Y-%m-%d')}  ·  {years}y lookback  ·  daily bars{' ' * 21}║{_RESET}")
    print(f"{_BOLD}╚══════════════════════════════════════════════════════════════════╝{_RESET}\n")

    classified: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = get_prices(t, start=start)
        except Exception as e:  # noqa: BLE001
            print(f"  {t:10s}  — kein Datenfeed ({e})")
            continue
        use_vix = vix if t in {"SPY", "QQQ", "DIA", "IWM", "^GSPC"} else None
        cls = regime.classify(df, vix=use_vix)
        classified[t] = cls
        snap = regime.current_regime(cls)
        m = snap["metrics"]
        print(f"  {_swatch(snap['regime'])}  {_BOLD}{t:10s}{_RESET} "
              f"{snap['label']:22s} [{snap['direction_label']:7s}]  "
              f"ADX {m['adx']:5.1f}  vol-rank {m['vol_rank']:.2f}  ATR {m['atr_pct']*100:4.2f}%")

    if not classified:
        print("\n  (keine Daten geladen)\n")
        return

    # ── recent transitions for the first asset ───────────────────────────────
    lead = next(iter(classified))
    print(f"\n{_BOLD}── Letzte Regime-Wechsel · {lead} ─────────────────────────────────{_RESET}")
    spans = regime.segments(classified[lead])
    for s in spans[-8:]:
        print(f"  {_swatch(s['regime'])}  {s['start']} → {s['end']}  "
              f"{s['label']:22s} ({s['bars']:>4d} Bars)")

    # ── regime distribution table (share of time) ────────────────────────────
    print(f"\n{_BOLD}── Zeitanteil je Regime (Verteilung) ──────────────────────────────{_RESET}")
    header = "  " + " " * 10 + "".join(f"{REG_SHORT[c]:>16s}" for c in regime.REGIMES)
    print(header)
    for t, cls in classified.items():
        dist = regime.regime_distribution(cls)
        cells = "".join(f"{_swatch(c)} {dist[c]['pct']*100:11.1f}%" for c in regime.REGIMES)
        print(f"  {t:10s}{cells}")

    print(f"\n  Legende:  {_swatch('high_vol_trend')} High-Vol-Trend   "
          f"{_swatch('low_vol_trend')} Low-Vol-Trend   "
          f"{_swatch('high_vol_range')} Choppy   "
          f"{_swatch('low_vol_range')} Quiet\n")


REG_SHORT = {
    "high_vol_trend": "HiVol-Trend",
    "low_vol_trend": "LoVol-Trend",
    "high_vol_range": "Choppy",
    "low_vol_range": "Quiet",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Market Weather Radar — terminal regime demo")
    ap.add_argument("tickers", nargs="*", default=None, help="yfinance tickers (default: a liquid basket)")
    ap.add_argument("--years", type=int, default=6, help="history lookback in years")
    args = ap.parse_args(argv)
    run(args.tickers or DEFAULT_TICKERS, args.years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
