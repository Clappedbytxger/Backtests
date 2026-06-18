"""Map the 13 CORE-book instruments to IBKR contracts and verify tradability.

Read-only: uses reqContractDetails only, NO orders. For each engine instrument
(yfinance ticker) we build the candidate IBKR contract and report whether it
qualifies, its conId/exchange/longName and min size/increment (sizing info).

Mapping rationale:
  - FX majors (i0092) + carry crosses (i0100) -> Forex / IDEALPRO (fractional).
  - Indices (i0076) -> IBKR Index CFDs (match the backtest's CFD_INDEX cost model:
    3 bps RT + 2 bps/night). Fallback to ETF/future if a CFD symbol won't qualify.
  - Crypto (i0099/i0080) -> Paxos (secType CRYPTO).
Run: .venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_instruments.py
"""
from __future__ import annotations

import json
from pathlib import Path

from ib_async import IB, Forex, Crypto, CFD, util

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

# engine ticker -> (kind, IBKR contract spec). For CFDs we list candidate symbols.
MAPPING = {
    # FX majors (i0092)
    "EURUSD=X": ("forex", "EURUSD"),
    "USDJPY=X": ("forex", "USDJPY"),
    "AUDUSD=X": ("forex", "AUDUSD"),
    "USDCHF=X": ("forex", "USDCHF"),
    # carry crosses (i0100)
    "AUDJPY=X": ("forex", "AUDJPY"),
    "NZDJPY=X": ("forex", "NZDJPY"),
    "AUDCHF=X": ("forex", "AUDCHF"),
    "CADJPY=X": ("forex", "CADJPY"),
    "EURJPY=X": ("forex", "EURJPY"),
    # indices (i0076) -> Index CFD candidates (symbol, currency)
    "^GSPC": ("cfd", [("IBUS500", "USD"), ("SPY", "USD")]),
    "^DJI":  ("cfd", [("IBUS30", "USD"), ("DIA", "USD")]),
    "^NDX":  ("cfd", [("IBUST100", "USD"), ("QQQ", "USD")]),
    "^GDAXI": ("cfd", [("IBDE40", "EUR"), ("IBGER40", "EUR")]),
    # crypto (i0099/i0080)
    "BTC-USD": ("crypto", "BTC"),
    "ETH-USD": ("crypto", "ETH"),
}


def describe(ib, contract):
    try:
        cds = ib.reqContractDetails(contract)
    except Exception as e:  # noqa: BLE001
        return None, f"error: {type(e).__name__}"
    if not cds:
        return None, "no contract details"
    cd = cds[0]
    c = cd.contract
    info = {
        "conId": c.conId, "symbol": c.symbol, "secType": c.secType,
        "exchange": c.exchange or cd.validExchanges.split(",")[0],
        "currency": c.currency, "longName": getattr(cd, "longName", ""),
        "minSize": getattr(cd, "minSize", None), "sizeIncrement": getattr(cd, "sizeIncrement", None),
    }
    return info, "ok"


def main():
    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=18, timeout=8, readonly=True)
    out = {}
    print(f"{'engine':10s} {'kind':7s} {'IBKR':10s} {'qualified':10s} conId / longName")
    for tk, (kind, spec) in MAPPING.items():
        contract = None
        info = None
        status = ""
        if kind == "forex":
            info, status = describe(ib, Forex(spec))
        elif kind == "crypto":
            info, status = describe(ib, Crypto(spec, "PAXOS", "USD"))
        elif kind == "cfd":
            for sym, ccy in spec:
                info, status = describe(ib, CFD(sym, "SMART", ccy))
                if info:
                    break
        out[tk] = {"kind": kind, "status": status, "ibkr": info}
        if info:
            print(f"{tk:10s} {kind:7s} {info['symbol']:10s} {'YES':10s} "
                  f"{info['conId']} {info['secType']}@{info['exchange']} "
                  f"minSize={info['minSize']} inc={info['sizeIncrement']} | {info['longName'][:32]}")
        else:
            print(f"{tk:10s} {kind:7s} {str(spec)[:10]:10s} {'NO':10s} ({status})")
    ib.disconnect()
    (RESULTS / "ib_instruments.json").write_text(json.dumps(out, indent=2, default=str))
    ok = sum(1 for v in out.values() if v["ibkr"])
    print(f"\n{ok}/{len(out)} instruments qualified. -> results/ib_instruments.json")


if __name__ == "__main__":
    util.logToConsole(level=40)
    main()
