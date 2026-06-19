"""Deterministic signal engine for the frozen CTI CORE book (0108).

Two jobs:
  1. VALIDATION: reconstruct each sleeve's daily-net stream from raw data and check it
     matches the saved research streams (correlation) and that the inverse-vol book
     reproduces the in-sample Sharpe 1.214. If this fails, the engine is not faithful.
  2. LIVE SIGNAL: emit today's target position per instrument (fraction of account
     equity, signed), book-combined (inverse-vol) and scaled to the frozen 6% target vol.

Rules are ported bit-for-bit from the generating scripts (see FROZEN_SPEC.md):
  i0092 -> 0106/e1_monthend_fx.py            i0100 -> 0106/e9_carry_riskgated.py
  i0076 -> 0103/e4_vix_gate.py::rsi2_stream  i0099 -> 0106/e8_crypto_vol_gate.py (x i0080)
  i0080 -> 0103/e1_crypto_tsmom.py

No look-ahead beyond what the research used; all signals decide on Close[t], hold t+1.
Run: .venv/Scripts/python.exe strategies/0108_cti_core_book_live/signal_engine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices  # noqa: E402

ANN = np.sqrt(252)
TARGET_ACCOUNT_VOL = 0.06
S5 = ROOT / "strategies/0103_prop_challenge_batch5/results/streams"
S9 = ROOT / "strategies/0106_prop_challenge_batch9/results/streams"


# ---------- helpers (self-contained, frozen) ----------
def close(t, start="2005-01-01"):
    s = get_prices(t, start=start)["Close"].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s


def wilder_rsi(c, period=2):
    d = c.diff()
    up = d.clip(lower=0.0); dn = -d.clip(upper=0.0)
    ru = up.ewm(alpha=1.0 / period, adjust=False).mean()
    rd = dn.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = ru / rd.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def scale_factor(daily, target=0.10):
    rv = pd.Series(daily).dropna().std() * ANN
    return target / rv if rv > 0 else 1.0


def ann_sharpe(r):
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std(ddof=1) * ANN) if r.std(ddof=1) else 0.0


# ---------- sleeve 1: I0092 month-end FX ----------
FX92 = {"EUR": ("EURUSD=X", +1), "JPY": ("USDJPY=X", -1), "AUD": ("AUDUSD=X", +1), "CHF": ("USDCHF=X", -1)}


def sleeve_i0092():
    spread = 1.6 / 1e4
    px = {c: close(p) for c, (p, _) in FX92.items()}
    rets = {c: px[c].pct_change() * sgn for c, (p, sgn) in FX92.items()}
    fx = pd.DataFrame(rets).dropna(how="all")
    spx_m = close("^GSPC").resample("ME").last().pct_change()
    efa_m = close("EFA").resample("ME").last().pct_change()
    sig = (efa_m - spx_m).dropna()
    idx = fx.index
    lbd = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).max()
    daily = pd.Series(0.0, index=idx)
    for d in lbd:
        nxt = idx[idx > d]
        if len(nxt) == 0:
            continue
        d1 = nxt[0]
        cur = [k for k in sig.index if (k.year, k.month) == (d.year, d.month)]
        if not cur:
            continue
        direction = np.sign(sig.loc[cur[-1]]); size = 2.0 if d.month in (3, 6, 9, 12) else 1.0
        daily.loc[d1] = direction * fx.loc[d1].mean() * size - spread * size
    daily = daily[daily != 0]
    k = scale_factor(daily, 0.10)
    stream = daily * k
    # today's target (held tomorrow) ONLY if today is the calendar last business day of its
    # month (next business day falls in a new month). idx[-1] is trivially the max of its
    # partial month, so we must check the forward calendar, not the data index.
    today = idx[-1]
    is_lbd_today = (today + pd.offsets.BDay(1)).month != today.month
    cur_w = pd.Series(0.0, index=[p for p, _ in FX92.values()])
    if is_lbd_today:
        cur = [m for m in sig.index if (m.year, m.month) == (today.year, today.month)]
        if cur:
            direction = np.sign(sig.loc[cur[-1]]); size = 2.0 if today.month in (3, 6, 9, 12) else 1.0
            for c, (p, sgn) in FX92.items():
                cur_w[p] = k * direction * size * 0.25 * sgn
    return stream, cur_w, {"today_is_month_end": bool(is_lbd_today)}


# ---------- sleeve 2: I0076 index RSI-2 (e4_vix_gate.rsi2_stream, ungated book) ----------
IDX76 = {"US500": "^GSPC", "US30": "^DJI", "NAS100": "^NDX", "GER40": "^GDAXI"}


def _rsi2_pos_net(c):
    sma200 = c.rolling(200).mean(); sma5 = c.rolling(5).mean(); rsi = wilder_rsi(c, 2)
    entry = (c > sma200) & (rsi < 10); exit_sig = c > sma5
    pos = np.zeros(len(c)); cur = 0
    ev, xv = entry.values, exit_sig.values
    for i in range(len(c)):
        if cur == 0 and ev[i]:
            cur = 1
        elif cur == 1 and xv[i]:
            cur = 0
        pos[i] = cur
    pos = pd.Series(pos, index=c.index)
    held = pos.shift(1).fillna(0.0)
    ret = c.pct_change(); turn = held.diff().abs().fillna(held.abs())
    net = held * ret - turn * (3.0 / 1e4 / 2) - held.abs() * (2.0 / 1e4)
    return pos, net


def sleeve_i0076():
    closes = {n: close(t, start="1995-01-01") for n, t in IDX76.items()}
    nets, cur_pos = {}, {}
    for n, c in closes.items():
        pos, net = _rsi2_pos_net(c)
        nets[n] = net; cur_pos[n] = float(pos.iloc[-1])
    book = pd.concat(nets.values(), axis=1).fillna(0.0).mean(axis=1)
    book = book[book.index >= "2000-01-01"]
    cur_w = pd.Series({IDX76[n]: 0.25 * cur_pos[n] for n in IDX76})  # held tomorrow
    return book, cur_w, {"in_position": {n: cur_pos[n] for n in IDX76}}


# ---------- sleeve 3: I0100 risk-gated carry ----------
PAIRS100 = {"AUDJPY=X": +1, "NZDJPY=X": +1, "AUDCHF=X": +1, "CADJPY=X": +1, "EURJPY=X": +1}


def sleeve_i0100(carry_yr=0.013):
    spread = 2.2 / 1e4
    rets = pd.DataFrame({p: close(p).pct_change() * s for p, s in PAIRS100.items()}).dropna()
    basket = rets.mean(axis=1)
    vix = close("^VIX").reindex(rets.index).ffill()
    vsma = vix.rolling(50).mean()
    risk_on = ((vix < vsma) & (vix < 25) & (vix / vix.shift(5) < 1.3)).shift(1).fillna(False)
    swap_d = carry_yr / 252.0
    gated = risk_on.astype(float) * (basket + swap_d) - risk_on.astype(float).diff().abs().fillna(0) * spread
    g = gated.loc[rets.index[50]:]
    k = scale_factor(g, 0.10)
    stream = g * k
    # today's gate (held tomorrow) from TODAY's vix (live = the un-shifted condition)
    on_today = bool((vix.iloc[-1] < vsma.iloc[-1]) and (vix.iloc[-1] < 25)
                    and (vix.iloc[-1] / vix.iloc[-6] < 1.3))
    cur_w = pd.Series({p: (k * 0.2 if on_today else 0.0) for p in PAIRS100})
    return stream, cur_w, {"risk_on_tomorrow": on_today, "vix": float(vix.iloc[-1])}


# ---------- sleeve 4: I0099 = I0080 crypto TSMOM x vol/trend gate ----------
COINS80 = {"BTC-USD": "2015-01-01", "ETH-USD": "2017-01-01"}


def _coin_w(c):
    sma = c.rolling(100).mean(); ts = c - c.shift(90)
    sig = ((c > sma) & (ts > 0)).astype(float)
    sigma = c.pct_change().rolling(20).std() * ANN
    return (sig * (0.10 / sigma)).replace([np.inf, -np.inf], np.nan)


def sleeve_i0099():
    closes = {t: close(t, start=st) for t, st in COINS80.items()}
    W = pd.DataFrame({t: _coin_w(c).shift(1) for t, c in closes.items()})
    R = pd.DataFrame({t: c.pct_change() for t, c in closes.items()}).reindex(W.index)
    valid = W.notna().any(axis=1); W = W[valid].fillna(0.0); R = R[valid].fillna(0.0)
    gross = (W * R).sum(axis=1) / 2
    spread_cost = W.diff().abs().fillna(W.abs()).sum(axis=1) / 2 * (10.0 / 1e4)
    swap_cost = W.abs().sum(axis=1) / 2 * (8.0 / 1e4)
    net80 = gross - spread_cost - swap_cost
    # vol/trend gate on BTC
    btc = closes["BTC-USD"]; ret = btc.pct_change()
    trend = np.where(btc > btc.rolling(200).mean(), 1.0, 0.4)
    rv = ret.rolling(20).std() / ret.rolling(100).std()
    volm = np.where(rv > 1.5, 0.5, 1.0)
    mult = pd.Series(trend * volm, index=btc.index).shift(1)
    j = pd.concat([net80.rename("s"), mult.rename("m")], axis=1).dropna()
    stream = j["s"] * j["m"]
    # today's target weights (held tomorrow): coin vol-target weight (today) x gate mult (today)
    mult_today = float((np.where(btc.iloc[-1] > btc.rolling(200).mean().iloc[-1], 1.0, 0.4))
                       * (0.5 if (ret.rolling(20).std().iloc[-1] / ret.rolling(100).std().iloc[-1]) > 1.5 else 1.0))
    cur_w = pd.Series(0.0, index=list(COINS80))
    for t, c in closes.items():
        w_today = _coin_w(c).iloc[-1]
        cur_w[t] = (0.0 if np.isnan(w_today) else w_today) / 2 * mult_today
    return stream, cur_w, {"gate_mult_tomorrow": mult_today}


# ---------- book assembly + live targets ----------
def build_book(target_vol=TARGET_ACCOUNT_VOL):
    """Return the combined inverse-vol book as a daily-return series, scaled to target_vol.
    Same assembly as compute_targets/main; used by the forward tracker (forward_track.py)."""
    s092, _, _ = sleeve_i0092()
    s076, _, _ = sleeve_i0076()
    s100, _, _ = sleeve_i0100()
    s099, _, _ = sleeve_i0099()
    df = pd.DataFrame({"i0092": s092, "i0076": s076, "i0100": s100, "i0099": s099})
    df = df.sort_index().fillna(0.0)
    df = df.loc[df.index >= df.apply(lambda c: c.ne(0).idxmax()).max()]
    invvol = 1.0 / (df.std() * ANN); w_sleeve = invvol / invvol.sum()
    book = (df * w_sleeve).sum(axis=1)
    K = target_vol / (book.std() * ANN)
    return book * K


def compute_targets(target_vol=TARGET_ACCOUNT_VOL):
    """Return (positions, context). positions: {engine_ticker: target weight as fraction
    of account equity, signed}. Same book math as main() but returns instead of printing."""
    s092, w092, i92 = sleeve_i0092()
    s076, w076, i76 = sleeve_i0076()
    s100, w100, i100 = sleeve_i0100()
    s099, w099, i99 = sleeve_i0099()
    df = pd.DataFrame({"i0092": s092, "i0076": s076, "i0100": s100, "i0099": s099})
    df = df.sort_index().fillna(0.0)
    df = df.loc[df.index >= df.apply(lambda c: c.ne(0).idxmax()).max()]
    invvol = 1.0 / (df.std() * ANN); w_sleeve = invvol / invvol.sum()
    book = (df * w_sleeve).sum(axis=1)
    K = target_vol / (book.std() * ANN)
    pos = {}
    for sl, wser in {"i0092": w092, "i0076": w076, "i0100": w100, "i0099": w099}.items():
        for instr, wt in wser.items():
            pos[instr] = pos.get(instr, 0.0) + w_sleeve[sl] * float(wt)
    pos = {k: K * v for k, v in pos.items() if abs(K * v) > 1e-9}
    ctx = {"month_end": i92["today_is_month_end"], "carry_on": i100["risk_on_tomorrow"],
           "vix": i100["vix"], "crypto_gate": i99["gate_mult_tomorrow"],
           "idx_in_pos": i76["in_position"], "book_sharpe": ann_sharpe(book),
           "K": float(K), "asof": str(df.index[-1].date())}
    return pos, ctx


def validate(stream, saved_path, name):
    saved = pd.read_parquet(saved_path).iloc[:, 0]
    saved.index = pd.to_datetime(saved.index).tz_localize(None)
    al = stream.index.intersection(saved.index)
    corr = float(np.corrcoef(stream.reindex(al).fillna(0), saved.reindex(al).fillna(0))[0, 1])
    print(f"  {name:10s} | recon Sharpe {ann_sharpe(stream):+.3f} vs saved {ann_sharpe(saved):+.3f} "
          f"| corr={corr:.4f} | overlap {len(al)}d (recon→{stream.index[-1].date()}, saved→{saved.index[-1].date()})")
    return corr


def main():
    print("=== rebuild sleeves from raw data ===")
    s092, w092, i92 = sleeve_i0092()
    s076, w076, i76 = sleeve_i0076()
    s100, w100, i100 = sleeve_i0100()
    s099, w099, i99 = sleeve_i0099()

    print("\n=== validation vs saved research streams ===")
    c092 = validate(s092, S9 / "i0092_monthend_fx.parquet", "i0092")
    c076 = validate(s076, S5 / "i0076_rsi2_ungated.parquet", "i0076")
    c100 = validate(s100, S9 / "i0100_carry_riskgated.parquet", "i0100")
    c099 = validate(s099, S9 / "i0099_crypto_gated.parquet", "i0099")

    streams = {"i0092": s092, "i0076": s076, "i0100": s100, "i0099": s099}
    df = pd.DataFrame(streams).sort_index().fillna(0.0)   # fill BEFORE first-nonzero detection
    df = df.loc[df.index >= df.apply(lambda c: c.ne(0).idxmax()).max()]
    vols = df.std() * ANN
    invvol = (1.0 / vols); w_sleeve = invvol / invvol.sum()
    book = (df * w_sleeve).sum(axis=1)
    book_sharpe = ann_sharpe(book)
    K = TARGET_ACCOUNT_VOL / (book.std() * ANN)
    print(f"\n=== book ({df.index[0].date()}..{df.index[-1].date()}) ===")
    print("  sleeve weights (inverse-vol):", {k: round(v, 3) for k, v in w_sleeve.items()})
    print(f"  reproduced book Sharpe = {book_sharpe:+.3f}  (target 1.214)  | account-vol scale K={K:.3f} for {TARGET_ACCOUNT_VOL:.0%}")

    # ---- today's target positions per instrument (fraction of account equity) ----
    sleeve_w = {"i0092": w092, "i0076": w076, "i0100": w100, "i0099": w099}
    pos = {}
    for sl, wser in sleeve_w.items():
        for instr, wt in wser.items():
            pos[instr] = pos.get(instr, 0.0) + w_sleeve[sl] * float(wt)
    pos = {k: K * v for k, v in pos.items()}
    print(f"\n=== TODAY'S TARGET POSITIONS (hold next session, % of equity) ===")
    print(f"  context: month_end_today={i92['today_is_month_end']} carry_risk_on={i100['risk_on_tomorrow']} "
          f"(VIX {i100['vix']:.1f}) crypto_gate={i99['gate_mult_tomorrow']:.1f} idx_in_pos={i76['in_position']}")
    for instr in sorted(pos, key=lambda x: -abs(pos[x])):
        if abs(pos[instr]) > 1e-5:
            print(f"  {instr:10s} {pos[instr]*100:+7.2f}% of equity")
    gross = sum(abs(v) for v in pos.values())
    print(f"  gross exposure = {gross*100:.1f}% of equity")

    ok = min(c092, c076, c100, c099) > 0.99 and abs(book_sharpe - 1.214) < 0.05
    print(f"\n{'PASS' if ok else 'CHECK'}: sleeve corr>0.99 and book Sharpe~1.21 -> "
          f"{'engine is faithful' if ok else 'investigate divergence'}")


if __name__ == "__main__":
    main()
