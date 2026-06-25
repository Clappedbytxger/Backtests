"""I0078 - USD-regime directional overlay (Gold & index CFD), port of 0086 I0038.

0086 I0038 (LIVING edge, p=0.002): DXY 63d momentum < 0 -> long commodity/EM basket.
Batch-4 reframes onto CTI-tradable direction with a confirmed-regime definition:
  USD_down = (DXY < SMA(DXY,200)) AND (DXY < DXY[t-63])   -> long XAUUSD/US500/NAS100/AUDUSD
  USD_up   = inverse                                        -> short Gold / flat indices

Reject-not-final: first reproduce the 0086 original (does the regime timing beat
random same-count timing on the basket?), then test the batch-4 confirmed variant.
Drift-trap permutation throughout.

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/e4_usd_regime.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.significance import permutation_test

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def get_dxy() -> pd.Series:
    for tk in ("DX-Y.NYB", "DX=F"):
        try:
            return get_prices(tk, start="2003-01-01")["Close"].rename("DXY")
        except Exception:
            continue
    return get_prices("UUP", start="2007-01-01")["Close"].rename("DXY")


def timed(target_ret: pd.Series, signal_pos: pd.Series):
    pos = signal_pos.shift(1).reindex(target_ret.index).fillna(0.0)
    return pos * target_ret, pos


def main() -> None:
    out = {"idea": "I0078", "name": "USD-regime directional overlay"}
    dxy = get_dxy()

    # ── reproduce 0086 I0038: DXY 63d momentum < 0 -> long commodity/EM basket ──
    basket = pd.DataFrame({t: get_prices(t, start="2003-01-01")["Close"]
                           for t in ["GC=F", "HG=F", "CL=F", "EEM"]})
    bret = basket.pct_change().mean(axis=1)
    sig_orig = (dxy.pct_change(63) < 0).astype(float)
    strat, pos = timed(bret, sig_orig)
    perm = permutation_test(strat, bret.reindex(strat.index).fillna(0),
                            pos.reindex(strat.index).fillna(0), n_perm=4000)
    out["repro_0086_I0038"] = {
        "timed_sharpe": round(C.ann_sharpe(strat), 3),
        "bh_basket_sharpe": round(C.ann_sharpe(bret), 3),
        "perm_p": round(perm["p_value"], 4),
        "frac_long": round(float(pos.mean()), 3),
    }
    print("Repro 0086 I0038:", out["repro_0086_I0038"])

    # ── batch-4 confirmed regime: DXY<SMA200 AND DXY<DXY[-63] ──
    usd_down = ((dxy < dxy.rolling(200).mean()) & (dxy < dxy.shift(63))).astype(float)
    usd_up = ((dxy > dxy.rolling(200).mean()) & (dxy > dxy.shift(63))).astype(float)

    targets = {
        "XAUUSD": get_prices("GC=F", start="2003-01-01")["Close"].pct_change(),
        "US500": get_prices("^GSPC", start="2003-01-01")["Close"].pct_change(),
        "NAS100": get_prices("^NDX", start="2003-01-01")["Close"].pct_change(),
        "AUDUSD": get_prices("AUDUSD=X", start="2003-01-01")["Close"].pct_change(),
    }
    variant = {}
    # combined overlay: long all four when USD_down; gold also short when USD_up
    for name, tr in targets.items():
        # long when USD_down; for gold allow short when USD_up, indices/AUD flat otherwise
        if name == "XAUUSD":
            sig = usd_down.reindex(tr.index).fillna(0) - usd_up.reindex(tr.index).fillna(0)
        else:
            sig = usd_down.reindex(tr.index).fillna(0)
        strat_v, pos_v = timed(tr, sig)
        perm_v = permutation_test(strat_v, tr.reindex(strat_v.index).fillna(0),
                                  pos_v.reindex(strat_v.index).fillna(0), n_perm=4000)
        variant[name] = {
            "timed_sharpe": round(C.ann_sharpe(strat_v), 3),
            "bh_sharpe": round(C.ann_sharpe(tr), 3),
            "perm_p": round(perm_v["p_value"], 4),
            "frac_active": round(float((pos_v != 0).mean()), 3),
        }
        print(f"  batch4 {name}: timed {variant[name]['timed_sharpe']:+.2f} vs B&H "
              f"{variant[name]['bh_sharpe']:+.2f}, perm p={variant[name]['perm_p']:.3f}")
    out["batch4_confirmed_regime"] = variant

    # equal-weight overlay book (the intended use: a Gold/risk overlay)
    legs = []
    for name, tr in targets.items():
        if name == "XAUUSD":
            sig = usd_down.reindex(tr.index).fillna(0) - usd_up.reindex(tr.index).fillna(0)
        else:
            sig = usd_down.reindex(tr.index).fillna(0)
        s, _ = timed(tr, sig)
        legs.append(s)
    book = pd.concat(legs, axis=1).mean(axis=1)
    out["overlay_book"] = {
        "sharpe": round(C.ann_sharpe(book), 3),
        "period": f"{book.index.min().date()}..{book.index.max().date()}",
    }
    print("Overlay book (EW) Sharpe:", out["overlay_book"]["sharpe"])
    (RESULTS / "e4_usd_regime.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
