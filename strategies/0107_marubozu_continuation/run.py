"""Marubozu continuation study (Robin's idea — NOT a CTI sleeve, pure edge research).

Hypothesis: a big RED wick-less candle (Low~Close, High~Open) whose body is much
larger than recent candles signals continuation -> go SHORT. Variants: single vs
two consecutive such candles; exits incl. 1:1 RR. Tested intraday + daily, multiple
markets. We test SHORT (continuation, the hypothesis) AND LONG (exhaustion/fade) to
let the data decide which it is, GROSS first then net of cost.

Marubozu (signal bar i, decision at its close):
  red:        Close < Open
  body:       Open - Close              range: High - Low
  body_ratio: body / range  >= MIN_RATIO   ("almost no wicks")
  big:        body > BIG_K * SMA(|Open-Close|, 10)[i-1]   ("much larger than recent")
Entry next bar open. R = signal body. 1:1 -> stop = entry + R, target = entry - R
(short). Resolve on subsequent bars' High/Low; if both hit same bar -> stop first
(conservative). Time cap MAX_HOLD bars -> exit at close (PnL in R).
"""
from __future__ import annotations
import sys
from pathlib import Path
import json
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices
CACHE = ROOT / "data" / "cache"
RES = Path(__file__).resolve().parent / "results"

MIN_RATIO = 0.92      # body/range: almost no wicks
BIG_K = 1.5           # body > 1.5x recent average body
MAX_HOLD = 20         # bars


def marubozu_flags(df, color, min_ratio=MIN_RATIO, big_k=BIG_K):
    O, H, L, C = df["Open"], df["High"], df["Low"], df["Close"]
    rng = (H - L).replace(0, np.nan)
    if color == "red":
        body = O - C; is_color = C < O
    else:
        body = C - O; is_color = C > O
    body_ratio = body / rng
    recent = (O - C).abs().rolling(10).mean().shift(1)
    big = body > big_k * recent
    return (is_color & (body_ratio >= min_ratio) & big & (body > 0)).fillna(False)


def backtest(df, side, double=False, tp_mult=1.0, sl_mult=1.0, cost_rt=0.0):
    """side: 'short' (after red marubozu, continuation) or 'long' (after green)."""
    O, H, L, C = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
    color = "red" if side == "short" else "green"
    flag = marubozu_flags(df, color).values
    sig = flag.copy()
    if double:
        sig = flag & np.r_[False, flag[:-1]]   # two consecutive
    body = np.abs(O - C)
    trades = []
    n = len(df)
    i = 0
    while i < n - 1:
        if sig[i] and body[i] > 0:
            entry = O[i + 1]
            R = body[i]
            if side == "short":
                stop = entry + sl_mult * R; tgt = entry - tp_mult * R
            else:
                stop = entry - sl_mult * R; tgt = entry + tp_mult * R
            out = None
            for j in range(i + 1, min(i + 1 + MAX_HOLD, n)):
                hi, lo, cl = H[j], L[j], C[j]
                if side == "short":
                    hit_stop = hi >= stop; hit_tgt = lo <= tgt
                else:
                    hit_stop = lo <= stop; hit_tgt = hi >= tgt
                if hit_stop:            # conservative: stop first if both
                    out = -sl_mult; break
                if hit_tgt:
                    out = +tp_mult; break
            if out is None:            # time exit at last close, PnL in R
                last = C[min(i + MAX_HOLD, n - 1)]
                out = ((entry - last) if side == "short" else (last - entry)) / R
            cost_R = entry * cost_rt / R    # round-trip cost expressed in R
            trades.append(out - cost_R)
            i = j + 1 if out is not None else i + 1
        else:
            i += 1
    return np.array(trades, float)


def stats(tr):
    if len(tr) < 5:
        return dict(n=len(tr), win=np.nan, meanR=np.nan, spt=np.nan, expect=np.nan)
    return dict(n=len(tr), win=float((tr > 0).mean()),
                meanR=float(tr.mean()), spt=float(tr.mean() / tr.std()) if tr.std() else 0.0,
                sumR=float(tr.sum()))


def load_intraday(fname):
    df = pd.read_parquet(CACHE / "futures" / fname)
    return df[["Open", "High", "Low", "Close"]].dropna()


MARKETS = []  # (label, df-loader, cost_rt)
def build_markets():
    out = []
    # daily (yfinance)
    daily = {"SPY": 2e-4, "QQQ": 2e-4, "GLD": 2e-4, "BTC-USD": 20e-4, "EURUSD=X": 1.6e-4, "ES=F": 0.5e-4}
    for t, c in daily.items():
        try:
            d = get_prices(t, start="2005-01-01")[["Open", "High", "Low", "Close"]].dropna()
            out.append((f"{t} daily", d, c))
        except Exception:
            pass
    # intraday futures (Databento cache), MES/MNQ-style 3 bps RT
    for lbl, fn in [("ES 1h", "ES_c_0_ohlcv-1h_2010-06-06_2026-06-06.parquet"),
                    ("NQ 1h", "NQ_c_0_ohlcv-1h_2010-06-06_2026-06-06.parquet"),
                    ("ES 15m", "ES_c_0_ohlcv-15m_RTH.parquet"),
                    ("NQ 15m", "NQ_c_0_ohlcv-15m_RTH.parquet")]:
        try:
            out.append((lbl, load_intraday(fn), 3e-4))
        except Exception:
            pass
    return out


def main():
    markets = build_markets()
    summary = {}
    print(f"{'market':12s} {'variant':22s} {'n':>5} {'win%':>6} {'meanR':>7} {'spt':>6}")
    print("-" * 64)
    for label, df, cost in markets:
        summary[label] = {}
        for side in ["short", "long"]:
            for double in [False, True]:
                for tp in [1.0, 2.0]:
                    gross = backtest(df, side, double, tp_mult=tp, sl_mult=1.0, cost_rt=0.0)
                    net = backtest(df, side, double, tp_mult=tp, sl_mult=1.0, cost_rt=cost)
                    g, nstat = stats(gross), stats(net)
                    if g["n"] < 5:
                        continue
                    tag = f"{side}{'x2' if double else ''} tp{tp:g}:1"
                    summary[label][tag] = {"gross": g, "net": nstat}
                    # print only the headline single-candle 1:1 + notable
                    if (not double and tp == 1.0) or (g.get("win") and g["win"] > 0.55):
                        print(f"{label:12s} {tag:22s} {g['n']:>5} {g['win']*100:>5.1f} "
                              f"{g['meanR']:>+7.3f} {g['spt']:>+6.3f}  (net meanR {nstat['meanR']:+.3f})")
    RES.mkdir(exist_ok=True)
    (RES / "marubozu_results.json").write_text(json.dumps(summary, indent=2, default=float))
    # aggregate verdict for the headline variant (single red marubozu, short, 1:1)
    print("\n=== Headline: single RED marubozu -> SHORT, 1:1 (GROSS win% vs 50% breakeven) ===")
    wins = []
    for label, df, cost in markets:
        g = stats(backtest(df, "short", False, 1.0, 1.0, 0.0))
        n = stats(backtest(df, "short", False, 1.0, 1.0, cost))
        if g["n"] >= 5:
            wins.append(g["win"])
            edge = "EDGE?" if g["win"] > 0.53 else ("fade?" if g["win"] < 0.47 else "~coin")
            print(f"  {label:12s} n={g['n']:>4} grossWin={g['win']*100:4.1f}% netMeanR={n['meanR']:+.3f}  {edge}")
    if wins:
        print(f"  -> mean gross win-rate across markets = {np.mean(wins)*100:.1f}% "
              f"(1:1 needs >50% gross, >~52-53% net)")

    # The inverse the equity data implies: red marubozu -> FADE (go LONG, bounce)
    print("\n=== Inverse test: single RED marubozu -> LONG (FADE/bounce), 1:1 ===")
    fadewins = []
    for label, df, cost in markets:
        # reuse backtest with side='long' but force the GREEN detector off: build a red-fade
        O, H, L, C = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
        flag = marubozu_flags(df, "red").values
        body = np.abs(O - C); tr = []
        i = 0; n = len(df)
        while i < n - 1:
            if flag[i] and body[i] > 0:
                e = O[i + 1]; R = body[i]; stop = e - R; tgt = e + R; out = None
                for j in range(i + 1, min(i + 1 + MAX_HOLD, n)):
                    if L[j] <= stop: out = -1.0; break
                    if H[j] >= tgt: out = 1.0; break
                if out is None:
                    out = (C[min(i + MAX_HOLD, n - 1)] - e) / R
                tr.append(out - e * cost / R); i = j + 1
            else:
                i += 1
        s = stats(np.array(tr))
        if s["n"] >= 5:
            fadewins.append(s["win"])
            print(f"  {label:12s} n={s['n']:>4} grossWin={s['win']*100:4.1f}% netMeanR={s['meanR']:+.3f}")
    if fadewins:
        print(f"  -> mean fade(long) gross win-rate = {np.mean(fadewins)*100:.1f}%")


if __name__ == "__main__":
    main()
