"""Data-availability probe for an extended futures universe.

We can only backtest a future if yfinance returns a continuous front-month series
with enough history for the IS(2000-2015)/OOS(2016+) split used in 0005/0008.
IBKR tradeability is necessary but NOT sufficient — the binding constraint is the
data source. This probe attempts each candidate, reports coverage, and flags
whether it passes the same length filter the screen uses, plus the non-positive
price guard (continuous futures can print <=0, e.g. WTI 2020).

Run:
    .venv/Scripts/python.exe strategies/0011_extended_futures_screen/probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices  # noqa: E402

IS_END = "2015-12-31"
OOS_START = "2016-01-01"

# (ticker, name, IBKR exchange). Candidates deliberately NOT already tested in
# 0005 (NG,CL,BZ,RB,GC,SI,ZC,ZW,ZS) or 0008 (PL,PA,HG,HO,ZL,ZM,ZO,KE,KC,CT,SB,
# CC,OJ,LE,HE,GF,ES,NQ,6E,ZB). All listed contracts trade on IBKR.
CANDIDATES = [
    # --- Commodities with a real physical supply/demand seasonality (new) ---
    ("ZR=F", "Rough Rice", "CBOT"),
    ("DC=F", "Milch Class III", "CME"),
    ("RS=F", "Canola/Raps", "ICE-CA"),
    ("LBS=F", "Bauholz (Lumber)", "CME"),
    ("LB=F", "Bauholz (alt)", "CME"),
    ("ALI=F", "Aluminium", "COMEX"),
    ("QC=F", "Kupfer (e-mini?)", "COMEX"),
    ("MW=F", "Minneapolis-Weizen", "MGEX"),
    # --- Equity-index futures (financial controls) ---
    ("YM=F", "Dow Jones", "CBOT"),
    ("RTY=F", "Russell 2000", "CME"),
    ("EMD=F", "S&P Midcap 400", "CME"),
    ("NKD=F", "Nikkei 225", "CME"),
    # --- Interest-rate futures (financial controls) ---
    ("ZN=F", "10Y T-Note", "CBOT"),
    ("ZF=F", "5Y T-Note", "CBOT"),
    ("ZT=F", "2Y T-Note", "CBOT"),
    ("UB=F", "Ultra T-Bond", "CBOT"),
    ("TN=F", "Ultra 10Y", "CBOT"),
    ("ZQ=F", "30D Fed Funds", "CBOT"),
    ("GE=F", "Eurodollar (delisted 2023)", "CME"),
    # --- FX futures (financial controls) ---
    ("6B=F", "Britisches Pfund", "CME"),
    ("6J=F", "Japanischer Yen", "CME"),
    ("6C=F", "Kanadischer Dollar", "CME"),
    ("6A=F", "Australischer Dollar", "CME"),
    ("6S=F", "Schweizer Franken", "CME"),
    ("6N=F", "Neuseeland-Dollar", "CME"),
    ("6M=F", "Mexikanischer Peso", "CME"),
    ("6L=F", "Brasilianischer Real", "CME"),
    ("DX=F", "US-Dollar-Index", "ICE-US"),
    # --- Crypto futures (expected: too short for IS 2000-2015) ---
    ("BTC=F", "Bitcoin", "CME"),
    ("ETH=F", "Ethereum", "CME"),
    # --- Micro contracts (REDUNDANT — same underlying/seasonality as full size) ---
    ("MES=F", "Micro S&P 500 (=ES)", "CME"),
    ("MNQ=F", "Micro Nasdaq (=NQ)", "CME"),
    ("MYM=F", "Micro Dow (=YM)", "CME"),
    ("M2K=F", "Micro Russell (=RTY)", "CME"),
    ("MGC=F", "Micro Gold (=GC)", "COMEX"),
    ("SIL=F", "Micro Silver (=SI)", "COMEX"),
    ("MCL=F", "Micro WTI (=CL)", "NYMEX"),
    ("QM=F", "E-mini Crude (=CL)", "NYMEX"),
    ("QG=F", "E-mini NatGas (=NG)", "NYMEX"),
    ("QO=F", "E-mini Gold (=GC)", "COMEX"),
    ("QI=F", "E-mini Silver (=SI)", "COMEX"),
]


def main() -> None:
    rows = []
    for ticker, name, exch in CANDIDATES:
        try:
            px = get_prices(ticker, start="2000-01-01")
        except Exception as exc:  # noqa: BLE001
            rows.append({"ticker": ticker, "name": name, "exch": exch,
                         "status": f"NO DATA ({type(exc).__name__})",
                         "first": "-", "last": "-", "n_IS": 0, "n_OOS": 0,
                         "nonpos": "-", "usable": False})
            continue
        is_n = len(px.loc[:IS_END])
        oos_n = len(px.loc[OOS_START:])
        nonpos = bool((px["Close"] <= 0).any())
        usable = (is_n >= 252 * 5) and (oos_n >= 252) and (not nonpos)
        rows.append({
            "ticker": ticker, "name": name, "exch": exch,
            "status": "ok",
            "first": str(px.index[0].date()), "last": str(px.index[-1].date()),
            "n_IS": is_n, "n_OOS": oos_n,
            "nonpos": "YES" if nonpos else "no",
            "usable": usable,
        })
    df = pd.DataFrame(rows)
    with pd.option_context("display.width", 200, "display.max_columns", None,
                           "display.max_rows", None):
        print(df.to_string(index=False))
    usable = df[df["usable"]]
    print(f"\n  USABLE (pass IS>=5y, OOS>=1y, no non-positive price): {len(usable)} / {len(df)}")
    print("  ->", ", ".join(usable["ticker"]))


if __name__ == "__main__":
    main()
