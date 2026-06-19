"""Dry-run reconciliation: engine targets -> IBKR order list. NO orders are sent.

Pipeline:
  1. compute_targets() -> {engine_ticker: target weight (fraction of equity, signed)}
  2. connect to IBKR paper, read NetLiquidation (equity) + current positions
  3. size each target to a contract quantity (per-type FX/CFD/crypto, with the FX
     base->USD conversion so cross-pair notionals are correct)
  4. diff vs current positions -> order list, printed. DRY_RUN=True => nothing sent.

Sizing prices = latest yfinance close (a real recent price; live execution re-prices
via IBKR at order time). Equity + positions are live from IBKR.
Run: .venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_adapter.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from ib_async import IB, Forex, Crypto, CFD, util

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quantlab.data import get_prices  # noqa: E402
import signal_engine as eng  # noqa: E402
from ib_instruments import MAPPING  # noqa: E402

DRY_RUN = True  # hard safety: never sends orders while True

# yfinance tickers needed to price the book + derive base->USD FX rates
CFD_PX = {"^GSPC": "^GSPC", "^DJI": "^DJI", "^NDX": "^NDX", "^GDAXI": "^GDAXI"}
CRYPTO_PX = {"BTC-USD": "BTC-USD", "ETH-USD": "ETH-USD"}
FX_SPOTS = {"EURUSD=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "USDJPY=X"}


def last_close(tk):
    return float(get_prices(tk, start="2024-01-01")["Close"].dropna().iloc[-1])


def fx_to_usd(ccy, spot):
    """Value of 1 unit of ccy in USD."""
    if ccy == "USD":
        return 1.0
    if ccy == "EUR":
        return spot["EURUSD=X"]
    if ccy == "AUD":
        return spot["AUDUSD=X"]
    if ccy == "NZD":
        return spot["NZDUSD=X"]
    if ccy == "CAD":
        return 1.0 / spot["USDCAD=X"]
    if ccy == "CHF":
        return 1.0 / spot["USDCHF=X"]
    if ccy == "JPY":
        return 1.0 / spot["USDJPY=X"]
    raise ValueError(ccy)


def build_contracts(ib):
    out = {}
    for tk, (kind, spec) in MAPPING.items():
        if kind == "forex":
            c = Forex(spec)
        elif kind == "crypto":
            c = Crypto(spec, "PAXOS", "USD")
        else:  # cfd: first qualifying candidate
            c = None
            for sym, ccy in spec:
                cand = CFD(sym, "SMART", ccy)
                if ib.reqContractDetails(cand):
                    c = cand; break
        ib.qualifyContracts(c)
        out[tk] = c
    return out


def size(tk, weight, contract, equity, ref_px, spot):
    """Return (target_qty, implied_usd_notional). weight = fraction of equity (signed)."""
    notional_usd = weight * equity
    st = contract.secType
    if st == "CASH":  # forex: trade base-currency units
        base = contract.symbol
        qty = notional_usd / fx_to_usd(base, spot)
        implied = qty * fx_to_usd(base, spot)
    elif st == "CFD":  # index CFD priced in its currency
        ccy = contract.currency
        notional_ccy = notional_usd / fx_to_usd(ccy, spot)
        qty = notional_ccy / ref_px[tk]
        implied = qty * ref_px[tk] * fx_to_usd(ccy, spot)
    else:  # crypto, USD-priced
        qty = notional_usd / ref_px[tk]
        implied = qty * ref_px[tk]
    return qty, implied


def round_qty(contract):
    return {"CASH": 0, "CFD": 0, "CRYPTO": 6}.get(contract.secType, 0)


def reconcile(targets, label):
    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=19, timeout=8, readonly=True)
    accounts = ib.managedAccounts()
    assert accounts and all(a.startswith("DU") for a in accounts), "NOT a paper account -- abort"
    equity = float(next(s.value for s in ib.accountSummary() if s.tag == "NetLiquidation"))

    contracts = build_contracts(ib)
    spot = {t: last_close(t) for t in FX_SPOTS}
    ref_px = {t: last_close(t) for t in list(CFD_PX) + list(CRYPTO_PX)}

    cur = {}  # conId -> signed position qty
    for p in ib.positions():
        cur[p.contract.conId] = cur.get(p.contract.conId, 0.0) + p.position

    print(f"\n===== {label} =====")
    print(f"equity (NetLiquidation) = ${equity:,.0f} | DRY_RUN={DRY_RUN} | targets: {len(targets)}")
    print(f"{'instrument':10s} {'sec':6s} {'wt%':>6s} {'tgt_notional$':>14s} {'tgt_qty':>14s} "
          f"{'cur_qty':>12s} {'order':>14s}  side")
    orders = []
    for tk in sorted(targets, key=lambda x: -abs(targets[x])):
        w = targets[tk]; c = contracts[tk]
        tgt_qty, implied = size(tk, w, c, equity, ref_px, spot)
        nd = round_qty(c)
        tgt_qty_r = round(tgt_qty, nd) if nd else round(tgt_qty)
        cur_qty = cur.get(c.conId, 0.0)
        order_qty = tgt_qty_r - cur_qty
        order_qty_r = round(order_qty, nd) if nd else round(order_qty)
        side = "BUY" if order_qty_r > 0 else ("SELL" if order_qty_r < 0 else "-")
        if abs(order_qty_r) > (10 ** -nd if nd else 1) * 0.5:
            orders.append((tk, c, order_qty_r, side))
        print(f"{tk:10s} {c.secType:6s} {w*100:6.2f} {w*equity:14,.0f} {tgt_qty_r:14,.2f} "
              f"{cur_qty:12,.2f} {order_qty_r:14,.2f}  {side}")
        # sanity: implied USD notional must match weight*equity
        if abs(implied - w * equity) > abs(w * equity) * 1e-6 + 1:
            print(f"    !! sizing mismatch on {tk}: implied ${implied:,.0f} vs target ${w*equity:,.0f}")

    print(f"\n{len(orders)} order(s) to place." + ("  [DRY_RUN -> nothing sent]" if DRY_RUN else ""))
    ib.disconnect()
    return orders


def main():
    print("Computing engine targets (this rebuilds + validates the book)...")
    pos, ctx = eng.compute_targets()
    print(f"as-of {ctx['asof']} | book Sharpe {ctx['book_sharpe']:.3f} | K={ctx['K']:.2f} "
          f"| month_end={ctx['month_end']} carry_on={ctx['carry_on']} (VIX {ctx['vix']:.1f}) "
          f"crypto_gate={ctx['crypto_gate']:.1f}")
    reconcile(pos, f"LIVE TARGETS (today, {ctx['asof']})")

    # --- synthetic target to exercise the sizing math (CFD-USD, crypto, cross-FX, major-FX short)
    synth = {"^GSPC": 0.10, "BTC-USD": 0.05, "EURJPY=X": 0.08, "AUDUSD=X": -0.06, "^GDAXI": 0.07}
    reconcile(synth, "SYNTHETIC SIZING TEST (not the strategy -- verifies conversion)")


if __name__ == "__main__":
    util.logToConsole(level=40)
    main()
