"""Live adapter: engine targets -> IBKR paper orders (reconcile + place).

Pipeline:
  1. compute_targets() -> {engine_ticker: target weight (fraction of equity, signed)}
  2. connect to IBKR paper, read NetLiquidation (equity) + current positions
  3. apply safety risk caps (per-instrument + total gross) to the targets
  4. size each target to a contract quantity (per-type FX/CFD/crypto, with the FX
     base->USD conversion so cross-pair notionals are correct)
  5. diff vs current positions -> order list
  6. DRY_RUN (default): print the order list, send NOTHING.
     --arm: margin pre-flight (whatIfOrder), then placeOrder() each, log fills to ledger.

Order type: MARKETABLE LIMIT on the next session. We price the limit aggressively through
the market (last close +/- a small per-type buffer) so it fills like a market order BUT
(a) survives IBKR's "no market data" precaution that rejects blind market orders on this
paper account (Error 354), and (b) caps slippage -- matching the 0070 finding that an
IBKR Adaptive/limit fill (~half-spread) beats a blind taker. Backtest-faithful for the
daily-close signals (cost model = spread). Crypto uses IOC, FX/CFD use DAY.

Safety: hard paper-account assert (managed accounts must start with 'DU'); readonly socket
unless --arm; module DRY_RUN stays True in git so an armed bot can never be committed.

Sizing/limit prices = latest yfinance close (a real recent price). Equity + positions are
live from IBKR. Limit prices are rounded to each contract's minTick.

Run (dry-run):   .venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_adapter.py
Run (LIVE/arm):  .venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_adapter.py --arm
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from ib_async import IB, Forex, Crypto, CFD, LimitOrder, util

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quantlab.data import get_prices  # noqa: E402
import signal_engine as eng  # noqa: E402
from ib_instruments import MAPPING  # noqa: E402

# --- safety / config -------------------------------------------------------
DRY_RUN = True                 # hard safety: True => never sends orders. Flip via --arm only.
PORT = 7497                    # TWS paper
CLIENT_ID = 20

# marketable-limit buffer through the market, per sec type (fraction of price). The limit is
# the WORST fill; expected fill is at/near the market. Wide enough to fill at EOD, tight
# enough to cap slippage near the backtest's spread assumption.
LIMIT_BUF = {"CASH": 0.0025, "CFD": 0.005, "CRYPTO": 0.015}

# risk caps (safety net; the 6% book rarely approaches these). Capping warns + clamps.
MAX_INSTRUMENT_WEIGHT = 0.60   # |target| per instrument, fraction of equity
MAX_GROSS_WEIGHT = 6.0         # sum |target| over all instruments, fraction of equity
MARGIN_USE_LIMIT = 0.90        # abort placement if init-margin need > this * AvailableFunds
MIN_ORDER_USD = 200.0          # skip dust orders below this notional

LEDGER = Path(__file__).resolve().parent / "results" / "fills_ledger.csv"

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


def tick_decimals(tick):
    """Number of decimals implied by a minTick (e.g. 0.00005 -> 5, 0.25 -> 2, 1.0 -> 0)."""
    s = f"{tick:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s and s.split(".")[1] else 0


def round_to_tick(price, tick):
    if tick and tick > 0:
        return round(round(price / tick) * tick, tick_decimals(tick))
    return round(price, 2)


def build_contracts(ib):
    """Return ({tk: contract}, {tk: minTick}). Qualifies each + grabs its tick size."""
    out, ticks = {}, {}
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
        cds = ib.reqContractDetails(c)
        ticks[tk] = float(cds[0].minTick) if cds else 0.0
        out[tk] = c
    return out, ticks


def apply_risk_caps(targets):
    """Clamp per-instrument weight, then total gross. Returns capped copy + flags."""
    capped = dict(targets)
    flags = []
    for tk, w in list(capped.items()):
        if abs(w) > MAX_INSTRUMENT_WEIGHT:
            flags.append(f"{tk} {w*100:+.1f}% -> capped to {MAX_INSTRUMENT_WEIGHT*100:.0f}%")
            capped[tk] = MAX_INSTRUMENT_WEIGHT * (1 if w > 0 else -1)
    gross = sum(abs(v) for v in capped.values())
    if gross > MAX_GROSS_WEIGHT and gross > 0:
        scale = MAX_GROSS_WEIGHT / gross
        flags.append(f"gross {gross*100:.0f}% -> scaled x{scale:.3f} to {MAX_GROSS_WEIGHT*100:.0f}%")
        capped = {k: v * scale for k, v in capped.items()}
    return capped, flags


def quote_price(tk):
    """Per-unit price in the contract's quote currency (FX pair rate / index level / USD)."""
    return last_close(tk)


def unit_usd(contract, tk, spot, ref_px):
    """USD value of 1 contract unit (for dust filtering + notional reporting)."""
    st = contract.secType
    if st == "CASH":
        return fx_to_usd(contract.symbol, spot)
    if st == "CFD":
        return ref_px[tk] * fx_to_usd(contract.currency, spot)
    return ref_px[tk]  # crypto, USD-priced


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


def limit_price(contract, side, qpx, tick):
    """Marketable limit: priced through the market by the per-type buffer, rounded to tick."""
    buf = LIMIT_BUF.get(contract.secType, 0.005)
    raw = qpx * (1 + buf) if side == "BUY" else qpx * (1 - buf)
    return round_to_tick(raw, tick)


def make_order(contract, qty, limit):
    """Marketable limit order. Crypto on PAXOS uses IOC; FX/CFD use DAY."""
    action = "BUY" if qty > 0 else "SELL"
    o = LimitOrder(action, abs(qty), limit)
    o.tif = "IOC" if contract.secType == "CRYPTO" else "DAY"
    return o


def reconcile(targets, label, ib, equity, contracts, ticks, spot, ref_px):
    """Compute the order list (pure: prints the table, sends nothing). Returns order list."""
    cur = {}  # conId -> signed position qty
    for p in ib.positions():
        cur[p.contract.conId] = cur.get(p.contract.conId, 0.0) + p.position

    print(f"\n===== {label} =====")
    print(f"equity (NetLiquidation) = ${equity:,.0f} | DRY_RUN={DRY_RUN} | targets: {len(targets)}")
    print(f"{'instrument':10s} {'sec':6s} {'wt%':>6s} {'tgt_notional$':>14s} {'tgt_qty':>14s} "
          f"{'cur_qty':>12s} {'order':>14s}  {'limit':>12s}  side")
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
        order_usd = abs(order_qty_r) * unit_usd(c, tk, spot, ref_px)
        lim = limit_price(c, side, quote_price(tk), ticks[tk]) if side != "-" else 0.0
        nonzero = abs(order_qty_r) > (10 ** -nd if nd else 1) * 0.5
        if nonzero and order_usd >= MIN_ORDER_USD:
            orders.append((tk, c, order_qty_r, side, order_usd, lim))
        elif nonzero:
            side += "*"  # below dust threshold -> skipped
        print(f"{tk:10s} {c.secType:6s} {w*100:6.2f} {w*equity:14,.0f} {tgt_qty_r:14,.2f} "
              f"{cur_qty:12,.2f} {order_qty_r:14,.2f}  {lim:12,.5f}  {side}")
        if abs(implied - w * equity) > abs(w * equity) * 1e-6 + 1:
            print(f"    !! sizing mismatch on {tk}: implied ${implied:,.0f} vs target ${w*equity:,.0f}")

    print(f"\n{len(orders)} order(s) to place (>= ${MIN_ORDER_USD:.0f}). "
          f"{'[DRY_RUN -> nothing sent]' if DRY_RUN else '[ARMED]'}  (* = dust, skipped)")
    return orders


def margin_preflight(ib, orders):
    """Sum whatIf init-margin change; return (need_usd, available_usd, ok)."""
    available = float(next((s.value for s in ib.accountSummary() if s.tag == "AvailableFunds"), 0.0))
    need = 0.0
    print("\n--- margin pre-flight (whatIfOrder) ---")
    for tk, c, qty, side, usd, lim in orders:
        try:
            st = ib.whatIfOrder(c, make_order(c, qty, lim))
            init = float(st.initMarginChange or 0.0)
        except Exception as e:  # noqa: BLE001
            print(f"  {tk:10s} whatIf failed ({type(e).__name__}) -> treat as 0 margin")
            init = 0.0
        need += max(init, 0.0)
        print(f"  {tk:10s} {side:4s} init-margin change ${init:,.0f}")
    ok = need <= MARGIN_USE_LIMIT * available
    print(f"  total init-margin need ${need:,.0f} vs available ${available:,.0f} "
          f"(limit {MARGIN_USE_LIMIT:.0%}) -> {'OK' if ok else 'ABORT'}")
    return need, available, ok


def log_fill(row):
    LEDGER.parent.mkdir(exist_ok=True)
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts_utc", "label", "instrument", "secType", "conId", "side",
                        "order_qty", "order_type", "tif", "limit", "status", "fill_qty",
                        "avg_fill_px", "order_usd", "equity_at_order"])
        w.writerow(row)


def place_orders(ib, orders, equity, label):
    """Place each order, wait for terminal state, log to the fill ledger."""
    need, available, ok = margin_preflight(ib, orders)
    if not ok:
        print("!! ABORT: margin pre-flight failed -- no orders sent.")
        return
    # subscribe to market data so the (paper) fill engine has a price to fill against.
    # FX has data on the paper account; index CFDs / crypto need their own subscription
    # (else bid/ask = -1 and the order rests Submitted without filling).
    for tk, c, qty, side, usd, lim in orders:
        ib.reqMktData(c, "", False, False)
    for _ in range(8):
        ib.waitOnUpdate(timeout=0.5)
    print(f"\n--- PLACING {len(orders)} order(s) [ARMED] ---")
    for tk, c, qty, side, usd, lim in orders:
        o = make_order(c, qty, lim)
        trade = ib.placeOrder(c, o)
        for _ in range(40):  # ~20s max wait for a terminal state
            ib.waitOnUpdate(timeout=0.5)
            if trade.isDone():
                break
        st = trade.orderStatus
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"  {tk:10s} {side:4s} {abs(qty):>14,.4f} @lim {lim:,.5f} -> {st.status} "
              f"(filled {st.filled:g} @ {st.avgFillPrice or '-'})")
        log_fill([ts, label, tk, c.secType, c.conId, side, qty, o.orderType, o.tif, lim,
                  st.status, st.filled, st.avgFillPrice, round(usd, 2), round(equity, 2)])
    print(f"-> fills logged to {LEDGER}")


def main(arm=False):
    global DRY_RUN
    if arm:
        DRY_RUN = False

    print("Computing engine targets (this rebuilds + validates the book)...")
    pos, ctx = eng.compute_targets()
    print(f"as-of {ctx['asof']} | book Sharpe {ctx['book_sharpe']:.3f} | K={ctx['K']:.2f} "
          f"| month_end={ctx['month_end']} carry_on={ctx['carry_on']} (VIX {ctx['vix']:.1f}) "
          f"crypto_gate={ctx['crypto_gate']:.1f}")

    capped, flags = apply_risk_caps(pos)
    if flags:
        print("RISK CAPS triggered:")
        for fl in flags:
            print(f"  - {fl}")

    ib = IB()
    ib.connect("127.0.0.1", PORT, clientId=CLIENT_ID, timeout=8, readonly=DRY_RUN)
    ib.reqMarketDataType(1)  # live; TWS falls back to frozen/delayed if unsubscribed
    accounts = ib.managedAccounts()
    assert accounts and all(a.startswith("DU") for a in accounts), "NOT a paper account -- abort"
    equity = float(next(s.value for s in ib.accountSummary() if s.tag == "NetLiquidation"))

    contracts, ticks = build_contracts(ib)
    spot = {t: last_close(t) for t in FX_SPOTS}
    ref_px = {t: last_close(t) for t in list(CFD_PX) + list(CRYPTO_PX)}

    label = f"LIVE TARGETS ({ctx['asof']})"
    orders = reconcile(capped, label, ib, equity, contracts, ticks, spot, ref_px)

    if not DRY_RUN:
        if orders:
            place_orders(ib, orders, equity, label)
        else:
            print("\nNo orders to place (book flat / all within tolerance).")
    else:
        # exercise the sizing math on a synthetic non-flat book (read-only, never placed)
        synth = {"^GSPC": 0.10, "BTC-USD": 0.05, "EURJPY=X": 0.08, "AUDUSD=X": -0.06, "^GDAXI": 0.07}
        reconcile(synth, "SYNTHETIC SIZING TEST (not the strategy -- verifies conversion)",
                  ib, equity, contracts, ticks, spot, ref_px)

    ib.disconnect()


if __name__ == "__main__":
    util.logToConsole(level=40)
    main(arm="--arm" in sys.argv)
