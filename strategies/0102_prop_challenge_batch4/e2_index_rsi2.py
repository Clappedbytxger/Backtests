"""I0076 - Daily-bar index mean-reversion (Connors RSI-2 + SMA-200 trend filter).

CTI-native (no stock universe) RSI-2 on the index CFD itself, long-only:
  E1  Close > SMA(Close,200)             (only dips in a bull market)
  E2  RSI(Close,2) < 10                   (Connors oversold trigger)
  E3  Close > 0.90 * Close[t-5]           (no vertical-crash knife-catch)
  Entry at the close.
  Exit (at close): RSI(2) > 65  OR  Close > SMA(Close,5).
  Initial stop: Entry - 2.5*ATR(14) (intraday). Time-stop: 10 trading days.

Cost: CFD_INDEX spread 3 bps round-trip + overnight swap 2 bps/night held.
Drift-trap permutation: random-entry-same-count on eligible (uptrend) days with the
SAME exit mechanics -> isolates whether the RSI-2 oversold TIMING beats just being
long the index in an uptrend.

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/e2_index_rsi2.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

INDICES = {"US500": "^GSPC", "US30": "^DJI", "NAS100": "^NDX", "GER40": "^GDAXI"}
SPREAD_RT = C.SPREAD_RT["index"] / 1e4
SWAP_NIGHT = C.SWAP_PER_NIGHT["index"] / 1e4
MAX_HOLD = 10


def prep(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["sma200"] = d["Close"].rolling(200).mean()
    d["sma5"] = d["Close"].rolling(5).mean()
    d["rsi2"] = C.wilder_rsi(d["Close"], 2)
    d["atr14"] = C.atr(d, 14)
    d["c5"] = d["Close"].shift(5)
    return d.dropna()


def run_index(d: pd.DataFrame, entry_days: list | None = None) -> list[dict]:
    """Event sim. If entry_days is given (permutation), force entries on those days
    instead of the RSI-2 trigger (same exit mechanics)."""
    idx = d.index
    closes = d["Close"].values
    highs = d["High"].values
    lows = d["Low"].values
    rsi2 = d["rsi2"].values
    sma5 = d["sma5"].values
    sma200 = d["sma200"].values
    atr14 = d["atr14"].values
    c5 = d["c5"].values
    forced = set(entry_days) if entry_days is not None else None

    trades = []
    i = 0
    n = len(d)
    while i < n - 1:
        if forced is None:
            entry_ok = (closes[i] > sma200[i]) and (rsi2[i] < 10.0) and (closes[i] > 0.90 * c5[i])
        else:
            entry_ok = idx[i] in forced
        if not entry_ok:
            i += 1
            continue
        entry_px = closes[i]
        stop = entry_px - 2.5 * atr14[i]
        # hold from i+1
        exit_px = None
        nights = 0
        j = i + 1
        while j < n:
            nights = j - i
            # intraday stop
            if lows[j] <= stop:
                exit_px = stop if highs[j] >= stop else closes[j]  # gap-down -> fill at close approx
                # honest gap handling: if it opened/traded below stop, fill at min(stop, that bar's open-ish)
                exit_px = min(stop, closes[j]) if lows[j] <= stop and closes[j] < stop else stop
                break
            # close-based profit exit
            if rsi2[j] > 65.0 or closes[j] > sma5[j]:
                exit_px = closes[j]
                break
            # time-stop
            if nights >= MAX_HOLD:
                exit_px = closes[j]
                break
            j += 1
        if exit_px is None:
            break
        ret = exit_px / entry_px - 1.0
        trades.append({"ret": ret, "nights": nights})
        i = j + 1  # one position at a time per index
    return trades


def net_returns(trades: list[dict]) -> np.ndarray:
    out = []
    for t in trades:
        cost = SPREAD_RT + SWAP_NIGHT * t["nights"]
        out.append(t["ret"] - cost)
    return np.array(out)


def permutation_random_entry(d: pd.DataFrame, n_trades: int, real_mean: float,
                             n_perm: int = 500, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    eligible = list(d.index[d["Close"] > d["sma200"]])
    if n_trades == 0 or len(eligible) < n_trades:
        return float("nan")
    cnt = 0
    for _ in range(n_perm):
        days = list(rng.choice(eligible, size=n_trades, replace=False))
        trades = run_index(d, entry_days=days)
        if trades and np.mean([t["ret"] for t in trades]) >= real_mean:
            cnt += 1
    return (cnt + 1) / (n_perm + 1)


def main() -> None:
    out = {"idea": "I0076", "name": "Index RSI-2 mean-reversion (Connors + SMA200)"}
    all_gross, all_net, all_nights = [], [], []
    per_index = {}
    perm_inputs = []
    for name, tk in INDICES.items():
        try:
            raw = get_prices(tk, start="1995-01-01")
        except Exception as e:
            per_index[name] = {"error": str(e)}
            continue
        d = prep(raw)
        trades = run_index(d)
        if not trades:
            per_index[name] = {"n_trades": 0}
            continue
        gross = np.array([t["ret"] for t in trades])
        net = net_returns(trades)
        nights = np.array([t["nights"] for t in trades])
        per_index[name] = {
            "n_trades": len(trades),
            "gross_mean_bps": round(float(gross.mean() * 1e4), 2),
            "net_mean_bps": round(float(net.mean() * 1e4), 2),
            "gross_sharpe_per_trade": round(C.sharpe_per_trade(gross), 4),
            "net_sharpe_per_trade": round(C.sharpe_per_trade(net), 4),
            "win": round(float((net > 0).mean()), 4),
            "avg_nights": round(float(nights.mean()), 2),
            "period": f"{d.index.min().date()}..{d.index.max().date()}",
        }
        all_gross.extend(gross.tolist())
        all_net.extend(net.tolist())
        all_nights.extend(nights.tolist())
        perm_inputs.append((d, len(trades), float(gross.mean())))
        print(f"{name}: n={len(trades)} gross {gross.mean()*1e4:+.1f}bps net {net.mean()*1e4:+.1f}bps "
              f"win {(net>0).mean()*100:.1f}% avgNights {nights.mean():.1f}")

    out["per_index"] = per_index
    g = np.array(all_gross)
    nt = np.array(all_net)
    lo, hi = C.bootstrap_mean_ci(nt)
    # pooled permutation: run per index, combine p via averaging the real-vs-null pooled mean
    perm_ps = []
    for d, ntr, rm in perm_inputs:
        perm_ps.append(permutation_random_entry(d, ntr, rm))
    out["pooled"] = {
        "n_trades": int(len(nt)),
        "gross_mean_bps": round(float(g.mean() * 1e4), 2),
        "net_mean_bps": round(float(nt.mean() * 1e4), 2),
        "gross_sharpe_per_trade": round(C.sharpe_per_trade(g), 4),
        "net_sharpe_per_trade": round(C.sharpe_per_trade(nt), 4),
        "net_sharpe_ann_approx": round(C.sharpe_per_trade(nt) * np.sqrt(len(nt) / 23.0), 3),
        "win": round(float((nt > 0).mean()), 4),
        "boot_net_mean_ci_bps": [round(lo * 1e4, 2), round(hi * 1e4, 2)],
        "perm_p_random_entry_per_index": [round(p, 4) for p in perm_ps],
    }
    print("\nPOOLED:", json.dumps(out["pooled"], indent=2))
    (RESULTS / "e2_index_rsi2.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
