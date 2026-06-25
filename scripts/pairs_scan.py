"""Statistical-Arbitrage Explorer — terminal validation of the pairs engine.

Two modes:
  1. Validate well-known pairs (Chevron/Exxon, Gold/Silver, Coke/Pepsi, ...):
     prints correlation, hedge ratio, ADF p-value, half-life and the current
     z-score + signal — a sanity check that the math finds the textbook pairs.
  2. Scan a whole group (``--group commodities``) through the two-stage filter
     and print the opportunity list, sorted by absolute z-score.

Run:
    .venv/Scripts/python.exe scripts/pairs_scan.py
    .venv/Scripts/python.exe scripts/pairs_scan.py --group commodities
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from quantlab import pairs  # noqa: E402
from quantlab.data import get_multiple_closes  # noqa: E402

# textbook cointegration candidates (same sector / same underlying driver)
KNOWN_PAIRS = [
    ("CVX", "XOM", "Chevron / Exxon (integrated oil)"),
    ("GLD", "SLV", "Gold / Silver (precious metals)"),
    ("KO", "PEP", "Coca-Cola / PepsiCo (beverages)"),
    ("HD", "LOW", "Home Depot / Lowe's (home improvement)"),
    ("MA", "V", "Mastercard / Visa (card networks)"),
    ("EWA", "EWC", "Australia / Canada ETFs (commodity econ.)"),
]

GROUPS = {
    "commodities": ["GLD", "SLV", "GDX", "GDXJ", "USO", "UNG", "DBA", "CPER", "PPLT", "PALL", "WEAT", "CORN"],
    "energy": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY", "PSX", "VLO", "MPC", "HES"],
    "tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "ORCL", "CRM", "ADBE", "INTC"],
    "banks": ["JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "SCHW"],
    "etf_index": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "XLK", "XLF", "XLE", "XLV"],
    "crypto": ["BTC-USD", "ETH-USD", "LTC-USD", "BCH-USD", "XRP-USD", "ADA-USD", "SOL-USD", "DOGE-USD"],
}

_G = "\033[92m"; _R = "\033[91m"; _Y = "\033[93m"; _RST = "\033[0m"; _B = "\033[1m"


def _sig_str(sig: str, z: float) -> str:
    if sig == "long_spread":
        return f"{_G}LONG spread (buy A / sell B){_RST}"
    if sig == "short_spread":
        return f"{_R}SHORT spread (sell A / buy B){_RST}"
    return f"{_Y}neutral{_RST}"


def validate_known(years: int) -> None:
    start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")
    print(f"\n{_B}╔══ KNOWN-PAIR VALIDATION ══ ({years}y, daily) ═════════════════════════╗{_RST}\n")
    print(f"  {'Pair':22s} {'corr':>5s} {'β':>6s} {'ADF p':>8s} {'half-life':>9s} {'z':>7s}  coint  signal")
    print("  " + "─" * 92)
    for a, b, desc in KNOWN_PAIRS:
        px = get_multiple_closes([a, b], start=start)
        if px.shape[1] < 2 or px.dropna().shape[0] < 100:
            print(f"  {a}/{b:<8s} — insufficient data")
            continue
        st = pairs.engle_granger(px[a], px[b])
        if st is None:
            print(f"  {a}/{b:<8s} — could not align")
            continue
        coint = f"{_G}YES{_RST}" if st.cointegrated else f"{_R}no {_RST}"
        hl = f"{st.half_life:6.0f}d" if st.half_life < 1e4 else "   inf"
        print(f"  {a+'/'+b:22s} {st.correlation:5.2f} {st.hedge_ratio:6.2f} "
              f"{st.adf_pvalue:8.3f} {hl:>9s} {st.z_score:7.2f}  {coint}   {_sig_str(st.signal(), st.z_score)}")
        print(f"  {'':22s} {desc}")
    print()


def scan_group(group: str, years: int, corr: float) -> None:
    tickers = GROUPS[group]
    start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")
    px = get_multiple_closes(tickers, start=start).dropna(how="all")
    n = px.shape[1]
    print(f"\n{_B}╔══ SCAN · {group} ══ {n} assets ({n*(n-1)//2} possible pairs) ═════════╗{_RST}\n")
    cands = pairs.correlation_prefilter(px, threshold=corr)
    print(f"  Stage 1 (corr ≥ {corr:.2f}): {len(cands)} candidate pairs survive the pre-filter")
    res = pairs.scan_pairs(px, corr_threshold=corr)
    print(f"  Stage 2 (ADF p < 0.05): {_B}{len(res)} cointegrated pairs{_RST}\n")
    if not res:
        print("  (no cointegrated pairs in this group/window)\n")
        return
    print(f"  {'A':8s} {'B':8s} {'corr':>5s} {'ADF p':>7s} {'half-life':>9s} {'z':>7s}  signal")
    print("  " + "─" * 70)
    for st in res:
        hl = f"{st.half_life:6.0f}d" if st.half_life < 1e4 else "   inf"
        print(f"  {st.a:8s} {st.b:8s} {st.correlation:5.2f} {st.adf_pvalue:7.3f} {hl:>9s} "
              f"{st.z_score:7.2f}  {_sig_str(st.signal(), st.z_score)}")
    print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Statistical-arbitrage pairs scanner (terminal)")
    ap.add_argument("--group", choices=sorted(GROUPS), default=None, help="scan a whole asset group")
    ap.add_argument("--years", type=int, default=6)
    ap.add_argument("--corr", type=float, default=0.70, help="stage-1 correlation threshold")
    args = ap.parse_args(argv)
    if args.group:
        scan_group(args.group, args.years, args.corr)
    else:
        validate_known(args.years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
