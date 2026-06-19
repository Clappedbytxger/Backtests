"""CTI execution adapter: frozen CORE-book targets -> MetaTrader 5 orders.

This is the MT5 sibling of ib_adapter.py. The IBKR adapter is the *paper* forward test;
CTI (City Traders Imperium) runs on MetaTrader 5, so the real-money challenge/funded leg
executes here. Same engine, same weights -- only the broker plumbing differs.

What MT5 changes vs IBKR:
  - Sizing is in LOTS, not units. lots are derived from symbol_info (trade_contract_size,
    currency_base/profit, volume_min/step) so it is broker-agnostic.
  - Symbol names are broker-specific (US500 vs SPX500, DE40 vs GER40, ...). resolve_symbol
    tries candidates against the terminal's symbol list and selects the one that exists.
  - Orders are market deals with a `deviation` slippage cap (the MT5 equivalent of the
    marketable-limit slippage cap used on IBKR).
  - CTI's binding rule is a TRAILING max drawdown. dd_guard() enforces it and the
    monitor() loop is the emergency "Notaus": poll equity (default 60s) and flatten +
    halt before the hard limit is breached.

Safety: DRY_RUN=True by default and stays True in git (arm only via --arm). Refuses REAL
trade-mode accounts unless ALLOW_REAL=True (challenge accounts are demo/contest). All
sizing math is pure + offline-testable via --selftest (no terminal needed).

Run (offline sizing self-test): .venv/Scripts/python.exe strategies/0108_cti_core_book_live/mt5_adapter.py --selftest
Run (dry-run, terminal open):   .venv/Scripts/python.exe strategies/0108_cti_core_book_live/mt5_adapter.py
Run (LIVE/arm):                 .venv/Scripts/python.exe strategies/0108_cti_core_book_live/mt5_adapter.py --arm
Run (DD emergency monitor):     .venv/Scripts/python.exe strategies/0108_cti_core_book_live/mt5_adapter.py --monitor
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quantlab.data import get_prices  # noqa: E402
import signal_engine as eng  # noqa: E402

# --- safety / config -------------------------------------------------------
DRY_RUN = True                 # True => never sends orders. Flip via --arm only.
ALLOW_REAL = False             # refuse REAL trade-mode accounts unless True
DEVIATION_POINTS = 30          # max slippage (points) on a market deal
MAGIC = 1080092                # order tag for this strategy
MIN_ORDER_USD = 200.0          # skip dust orders below this notional

# risk caps (safety net; mirror the IBKR adapter)
MAX_INSTRUMENT_WEIGHT = 0.60
MAX_GROSS_WEIGHT = 6.0

# CTI trailing-drawdown rule. SET THESE TO YOUR EXACT CTI PLAN before going live.
DD_MODE = "trailing"           # "trailing" (peak-to-equity) or "static" (from initial balance)
MAX_DD_PCT = 0.06              # CTI 1-Step hard max total drawdown (verify on your plan!)
DD_FLATTEN_AT = 0.80           # flatten at 80% of the hard limit -> keeps a buffer
MONITOR_POLL_SEC = 60          # equity poll interval for the emergency Notaus loop

RESULTS = Path(__file__).resolve().parent / "results"
LEDGER = RESULTS / "mt5_fills_ledger.csv"
DD_STATE = RESULTS / "mt5_dd_state.json"

# engine ticker -> (kind, [candidate MT5 symbols]). First existing candidate wins.
MAPPING = {
    "EURUSD=X": ("fx", ["EURUSD"]),
    "USDJPY=X": ("fx", ["USDJPY"]),
    "AUDUSD=X": ("fx", ["AUDUSD"]),
    "USDCHF=X": ("fx", ["USDCHF"]),
    "AUDJPY=X": ("fx", ["AUDJPY"]),
    "NZDJPY=X": ("fx", ["NZDJPY"]),
    "AUDCHF=X": ("fx", ["AUDCHF"]),
    "CADJPY=X": ("fx", ["CADJPY"]),
    "EURJPY=X": ("fx", ["EURJPY"]),
    "^GSPC": ("index", ["US500", "SPX500", "SP500", "USA500", "US500.cash"]),
    "^DJI":  ("index", ["US30", "DJ30", "DJI30", "USA30", "US30.cash"]),
    "^NDX":  ("index", ["USTEC", "NAS100", "NDX100", "US100", "USTEC.cash"]),
    "^GDAXI": ("index", ["DE40", "GER40", "GER30", "DAX40", "DE40.cash"]),
    "BTC-USD": ("crypto", ["BTCUSD", "BTCUSD.", "BTC/USD"]),
    "ETH-USD": ("crypto", ["ETHUSD", "ETHUSD.", "ETH/USD"]),
}

FX_SPOTS = {"EURUSD=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "USDJPY=X"}


def last_close(tk):
    return float(get_prices(tk, start="2024-01-01")["Close"].dropna().iloc[-1])


def fx_to_usd(ccy, spot):
    """USD value of 1 unit of ccy (from yfinance majors)."""
    if ccy == "USD":
        return 1.0
    table = {"EUR": spot["EURUSD=X"], "AUD": spot["AUDUSD=X"], "NZD": spot["NZDUSD=X"],
             "CAD": 1.0 / spot["USDCAD=X"], "CHF": 1.0 / spot["USDCHF=X"],
             "JPY": 1.0 / spot["USDJPY=X"]}
    if ccy in table:
        return table[ccy]
    raise ValueError(f"no USD rate for {ccy}")


# ---------- pure sizing math (offline-testable) ----------
def lots_for_target(kind, weight, equity, price, contract_size, base_usd, quote_usd):
    """Target lots for a signed weight (fraction of equity).

    FX: 1 lot = contract_size base-ccy units -> USD value = contract_size * base_usd.
    index/crypto CFD: 1 lot = contract_size * price (quote ccy) -> USD = * quote_usd.
    Returns signed lots (sign = weight sign).
    """
    notional_usd = weight * equity
    if kind == "fx":
        denom = contract_size * base_usd
    else:
        denom = contract_size * price * quote_usd
    return notional_usd / denom if denom else 0.0


def round_lots(lots, vol_step, vol_min):
    """Round |lots| to the broker volume step; 0 if below the minimum lot."""
    sign = 1.0 if lots >= 0 else -1.0
    n = round(abs(lots) / vol_step) * vol_step
    n = round(n, 8)
    if n < vol_min - 1e-12:
        return 0.0
    return sign * n


def order_usd(kind, lots, price, contract_size, base_usd, quote_usd):
    """USD notional of a lot quantity (for dust filtering + reporting)."""
    if kind == "fx":
        return abs(lots) * contract_size * base_usd
    return abs(lots) * contract_size * price * quote_usd


def apply_risk_caps(targets):
    capped = dict(targets)
    flags = []
    for tk, w in list(capped.items()):
        if abs(w) > MAX_INSTRUMENT_WEIGHT:
            flags.append(f"{tk} {w*100:+.1f}% -> cap {MAX_INSTRUMENT_WEIGHT*100:.0f}%")
            capped[tk] = MAX_INSTRUMENT_WEIGHT * (1 if w > 0 else -1)
    gross = sum(abs(v) for v in capped.values())
    if gross > MAX_GROSS_WEIGHT and gross > 0:
        sc = MAX_GROSS_WEIGHT / gross
        flags.append(f"gross {gross*100:.0f}% -> x{sc:.3f}")
        capped = {k: v * sc for k, v in capped.items()}
    return capped, flags


# ---------- MT5 plumbing ----------
def connect():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()} "
                           "(is the CTI terminal open + logged in?)")
    ai = mt5.account_info()
    if ai is None:
        mt5.shutdown()
        raise RuntimeError("MT5 account_info() is None (not logged in)")
    real = ai.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL
    if real and not ALLOW_REAL:
        mt5.shutdown()
        raise RuntimeError(f"REAL account {ai.login} -- refusing (set ALLOW_REAL=True to override)")
    mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(ai.trade_mode, "?")
    print(f"MT5 connected: login {ai.login} [{mode}] {ai.server} | "
          f"equity {ai.equity:,.2f} {ai.currency} | balance {ai.balance:,.2f}")
    return mt5, ai


def resolve_symbol(mt5, candidates):
    for sym in candidates:
        info = mt5.symbol_info(sym)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(sym, True)
            return sym
    return None


def build_symbols(mt5):
    """engine ticker -> {symbol, kind, spec}. spec = sizing fields from symbol_info."""
    out = {}
    for tk, (kind, cands) in MAPPING.items():
        sym = resolve_symbol(mt5, cands)
        if sym is None:
            print(f"  !! {tk}: none of {cands} exist on this broker -- SKIPPED")
            continue
        si = mt5.symbol_info(sym)
        out[tk] = {"symbol": sym, "kind": kind, "contract_size": si.trade_contract_size,
                   "base": si.currency_base, "quote": si.currency_profit,
                   "vol_min": si.volume_min, "vol_step": si.volume_step,
                   "vol_max": si.volume_max, "digits": si.digits}
    return out


def current_net_lots(mt5, symbol):
    """Signed net lots currently open for a symbol (BUY +, SELL -). Netting assumed."""
    poss = mt5.positions_get(symbol=symbol) or []
    net = 0.0
    for p in poss:
        net += p.volume if p.type == mt5.ORDER_TYPE_BUY else -p.volume
    return net


def price_for(mt5, symbol, side, fallback):
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        px = tick.ask if side == "BUY" else tick.bid
        if px and px > 0:
            return px
    return fallback


# ---------- drawdown guard / emergency stop ----------
def load_dd_state():
    if DD_STATE.exists():
        return json.loads(DD_STATE.read_text())
    return {}


def save_dd_state(state):
    RESULTS.mkdir(exist_ok=True)
    DD_STATE.write_text(json.dumps(state, indent=2))


def dd_guard(ai):
    """Update peak/initial state, return (breached, info). Flatten threshold is the SOFT
    limit (DD_FLATTEN_AT of the hard CTI limit) so we exit with a buffer before a breach."""
    st = load_dd_state()
    equity, balance = ai.equity, ai.balance
    st.setdefault("initial_balance", balance)
    st["peak_equity"] = max(st.get("peak_equity", equity), equity)
    reference = st["peak_equity"] if DD_MODE == "trailing" else st["initial_balance"]
    soft = MAX_DD_PCT * DD_FLATTEN_AT
    soft_limit = reference * (1 - soft)
    hard_limit = reference * (1 - MAX_DD_PCT)
    breached = equity <= soft_limit
    st["last_equity"] = equity
    st["last_check_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_dd_state(st)
    dd_now = (reference - equity) / reference if reference else 0.0
    info = {"equity": equity, "reference": reference, "dd_now_pct": dd_now * 100,
            "soft_limit": soft_limit, "hard_limit": hard_limit, "mode": DD_MODE}
    return breached, info


# ---------- ledger ----------
def log_fill(row):
    RESULTS.mkdir(exist_ok=True)
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts_utc", "label", "engine_ticker", "symbol", "kind", "side",
                        "lots", "price", "deviation", "retcode", "comment", "order_usd", "equity"])
        w.writerow(row)


# ---------- order placement ----------
def send_market(mt5, symbol, side, lots, price, label, kind, usd, equity):
    si = mt5.symbol_info(symbol)
    fm = si.filling_mode
    filling = (mt5.ORDER_FILLING_IOC if fm & 2 else
               mt5.ORDER_FILLING_FOK if fm & 1 else mt5.ORDER_FILLING_RETURN)
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": round(abs(lots), 8),
        "type": mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": DEVIATION_POINTS,
        "magic": MAGIC,
        "comment": label[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }
    res = mt5.order_send(req)
    rc = res.retcode if res else -1
    ok = rc == mt5.TRADE_RETCODE_DONE
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fill_px = res.price if res and ok else price
    print(f"  {symbol:8s} {side:4s} {abs(lots):>8.2f} lots @ {fill_px} -> "
          f"retcode {rc} {'OK' if ok else (res.comment if res else 'no result')}")
    log_fill([ts, label, "", symbol, kind, side, lots, fill_px, DEVIATION_POINTS, rc,
              (res.comment if res else ""), round(usd, 2), round(equity, 2)])
    return ok


def reconcile(mt5, targets, symbols, equity, spot, label):
    print(f"\n===== {label} =====")
    print(f"equity ~${equity:,.0f} | DRY_RUN={DRY_RUN} | targets: {len(targets)}")
    print(f"{'ticker':10s} {'symbol':8s} {'kind':6s} {'wt%':>6s} {'tgt_lots':>10s} "
          f"{'cur_lots':>10s} {'order':>10s}  side")
    orders = []
    for tk in sorted(targets, key=lambda x: -abs(targets[x])):
        if tk not in symbols:
            print(f"{tk:10s} (no broker symbol -- skipped)")
            continue
        s = symbols[tk]; w = targets[tk]
        price = price_for(mt5, s["symbol"], "BUY", last_close(tk)) if mt5 else last_close(tk)
        base_usd = fx_to_usd(s["base"], spot)
        quote_usd = fx_to_usd(s["quote"], spot)
        tgt = lots_for_target(s["kind"], w, equity, price, s["contract_size"], base_usd, quote_usd)
        tgt_r = round_lots(tgt, s["vol_step"], s["vol_min"])
        cur = current_net_lots(mt5, s["symbol"]) if mt5 else 0.0
        delta = round_lots(tgt_r - cur, s["vol_step"], s["vol_min"])
        side = "BUY" if delta > 0 else ("SELL" if delta < 0 else "-")
        usd = order_usd(s["kind"], delta, price, s["contract_size"], base_usd, quote_usd)
        if side != "-" and usd >= MIN_ORDER_USD:
            orders.append((tk, s, side, abs(delta), price, usd))
        elif side != "-":
            side += "*"
        print(f"{tk:10s} {s['symbol']:8s} {s['kind']:6s} {w*100:6.2f} {tgt_r:10.2f} "
              f"{cur:10.2f} {delta:10.2f}  {side}")
    print(f"\n{len(orders)} order(s) to place (>= ${MIN_ORDER_USD:.0f}). "
          f"{'[DRY_RUN]' if DRY_RUN else '[ARMED]'}  (* = dust)")
    return orders


def place_orders(mt5, orders, equity, label):
    print(f"\n--- PLACING {len(orders)} order(s) [ARMED] ---")
    for tk, s, side, lots, price, usd in orders:
        px = price_for(mt5, s["symbol"], side, price)
        send_market(mt5, s["symbol"], side, lots, px, label, s["kind"], usd, equity)


def flatten_all(mt5, label="EMERGENCY FLATTEN"):
    poss = mt5.positions_get() or []
    print(f"\n--- {label}: closing {len(poss)} position(s) ---")
    ai = mt5.account_info()
    for p in poss:
        side = "SELL" if p.type == mt5.ORDER_TYPE_BUY else "BUY"
        px = price_for(mt5, p.symbol, side, p.price_current)
        send_market(mt5, p.symbol, side, p.volume, px, label, "?", 0.0, ai.equity if ai else 0.0)


# ---------- run modes ----------
def run(arm=False):
    global DRY_RUN
    if arm:
        DRY_RUN = False
    print("Computing engine targets (rebuilds + validates the book)...")
    pos, ctx = eng.compute_targets()
    print(f"as-of {ctx['asof']} | book Sharpe {ctx['book_sharpe']:.3f} | "
          f"month_end={ctx['month_end']} carry_on={ctx['carry_on']} (VIX {ctx['vix']:.1f}) "
          f"crypto_gate={ctx['crypto_gate']:.1f}")
    capped, flags = apply_risk_caps(pos)
    for fl in flags:
        print(f"  RISK CAP: {fl}")

    mt5, ai = connect()
    try:
        breached, info = dd_guard(ai)
        print(f"DD guard [{info['mode']}]: equity {info['equity']:,.0f} | dd now "
              f"{info['dd_now_pct']:.2f}% | soft-flatten <= {info['soft_limit']:,.0f} | "
              f"hard <= {info['hard_limit']:,.0f}")
        if breached:
            print("!! DRAWDOWN SOFT LIMIT BREACHED -- flattening, no new targets.")
            if not DRY_RUN:
                flatten_all(mt5)
            return

        symbols = build_symbols(mt5)
        spot = {t: last_close(t) for t in FX_SPOTS}
        orders = reconcile(mt5, capped, symbols, ai.equity, spot, f"CTI TARGETS ({ctx['asof']})")
        if not DRY_RUN and orders:
            place_orders(mt5, orders, ai.equity, f"CTI TARGETS ({ctx['asof']})")
        elif not orders:
            print("\nNo orders (book flat / within tolerance).")
    finally:
        mt5.shutdown()


def monitor(arm=False):
    """Emergency Notaus loop: poll equity every MONITOR_POLL_SEC, flatten on DD breach."""
    global DRY_RUN
    if arm:
        DRY_RUN = False
    mt5, _ = connect()
    print(f"DD monitor running (poll {MONITOR_POLL_SEC}s, mode {DD_MODE}, "
          f"flatten at {MAX_DD_PCT*DD_FLATTEN_AT*100:.1f}% / hard {MAX_DD_PCT*100:.1f}%). "
          f"DRY_RUN={DRY_RUN}. Ctrl-C to stop.")
    try:
        while True:
            ai = mt5.account_info()
            breached, info = dd_guard(ai)
            stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"  [{stamp}] equity {info['equity']:,.0f} dd {info['dd_now_pct']:.2f}% "
                  f"(flatten<= {info['soft_limit']:,.0f})")
            if breached:
                print("!! DD SOFT LIMIT BREACHED")
                if not DRY_RUN:
                    flatten_all(mt5)
                else:
                    print("   [DRY_RUN -> would flatten all positions]")
                break
            time.sleep(MONITOR_POLL_SEC)
    except KeyboardInterrupt:
        print("\nmonitor stopped.")
    finally:
        mt5.shutdown()


def selftest():
    """Offline check of the lot-sizing math against hand-computed expectations (no terminal)."""
    print("=== lot-sizing self-test (offline) ===")
    spot = {"EURUSD=X": 1.08, "AUDUSD=X": 0.66, "NZDUSD=X": 0.60,
            "USDCAD=X": 1.36, "USDCHF=X": 0.88, "USDJPY=X": 158.0}
    equity = 100_000.0
    # 10% weight on each, contract_size 100k FX / 1 index / 1 crypto
    cases = [
        # (name, kind, base, quote, price, cs, expected_lots_at_10pct)
        ("EURUSD", "fx", "EUR", "USD", 1.08, 100_000, 10_000 / (100_000 * 1.08)),
        ("USDJPY", "fx", "USD", "JPY", 158.0, 100_000, 10_000 / (100_000 * 1.0)),
        ("EURJPY", "fx", "EUR", "JPY", 170.0, 100_000, 10_000 / (100_000 * 1.08)),
        ("US500", "index", "USD", "USD", 7500.0, 1, 10_000 / (1 * 7500.0 * 1.0)),
        ("DE40", "index", "EUR", "EUR", 18000.0, 1, 10_000 / (1 * 18000.0 * 1.08)),
        ("BTCUSD", "crypto", "BTC", "USD", 65000.0, 1, 10_000 / (1 * 65000.0 * 1.0)),
    ]
    ok = True
    for name, kind, base, quote, price, cs, exp in cases:
        base_usd = 1.0 if base in ("USD", "BTC", "ETH") else fx_to_usd(base, spot)
        quote_usd = fx_to_usd(quote, spot) if quote != "USD" else 1.0
        lots = lots_for_target(kind, 0.10, equity, price, cs, base_usd, quote_usd)
        match = abs(lots - exp) < 1e-9
        ok &= match
        print(f"  {name:7s} {kind:6s} 10% of ${equity:,.0f} -> {lots:.4f} lots "
              f"(expect {exp:.4f}) {'OK' if match else 'MISMATCH'}")
    # rounding
    r = round_lots(0.834, 0.01, 0.01)
    r2 = round_lots(0.004, 0.01, 0.01)
    print(f"  round 0.834@step0.01 -> {r} (0.83)  | round 0.004 below min -> {r2} (0.0)")
    ok &= (r == 0.83 and r2 == 0.0)
    print(f"\n{'PASS' if ok else 'FAIL'}: sizing math {'is correct' if ok else 'has a bug'}")
    return ok


if __name__ == "__main__":
    try:
        if "--selftest" in sys.argv:
            selftest()
        elif "--monitor" in sys.argv:
            monitor(arm="--arm" in sys.argv)
        else:
            run(arm="--arm" in sys.argv)
    except RuntimeError as e:
        print(f"\nABORT: {e}")
        sys.exit(1)
