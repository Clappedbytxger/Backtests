"""Batch-5 book integration (spec cross-cutting gates 3-5).

1. Load every batch-5 sleeve stream + reconstruct the existing book legs
   (I0075 month-end FX, I0076 RSI-2 equity book).
2. Standalone Sharpe + the REAL correlation matrix (verify the claimed decorrelation).
3. Build the book from SURVIVORS only, inverse-vol (equal-risk) weighted ->
   combined daily stream -> combined Sharpe (measured, NOT summed).
4. Run the prop Monte-Carlo (1-step cti_lock + 2-step) at the achieved combined Sharpe.

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/book_integration.py
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

ANN = C.ANN
BETS_PER_YEAR = 60
SKEW_WINRATE = 0.66


# ── reconstruct I0075 month-end FX daily stream (sparse: one event per LBD) ────
def i0075_stream() -> pd.Series:
    PAIRS = {"EURUSD=X": +1, "GBPUSD=X": +1, "AUDUSD=X": +1, "USDCHF=X": -1, "USDJPY=X": -1}
    eq = get_prices("^GSPC", start="2003-01-01")["Close"]
    grp = eq.groupby([eq.index.year, eq.index.month])
    sign = {}
    for _, s in grp:
        s = s.sort_index()
        if len(s) < 3:
            continue
        sign[s.index[-1]] = np.sign(s.iloc[-2] / s.iloc[0] - 1.0)
    sign = pd.Series(sign).sort_index()
    closes = {t: get_prices(t, start="2003-01-01")["Close"] for t in PAIRS}
    rets = pd.DataFrame(closes).pct_change()
    ev = {}
    for lbd, sg in sign.items():
        if lbd not in rets.index or not sg:
            continue
        row = rets.loc[lbd]
        legs = [usd_short * row[t] for t, usd_short in PAIRS.items() if not np.isnan(row[t])]
        if legs:
            ev[lbd] = sg * np.mean(legs) - C.SPREAD_RT["fx"] / 1e4
    s = pd.Series(ev).sort_index()
    # daily series over the full calendar (zeros on non-event days)
    idx = rets.index
    daily = pd.Series(0.0, index=idx)
    daily.loc[s.index] = s.values
    return daily


def load_streams() -> dict[str, pd.Series]:
    out = {}
    for f in sorted(C.STREAMS.glob("*.parquet")):
        s = pd.read_parquet(f).iloc[:, 0]
        idx = pd.DatetimeIndex(s.index)
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        s.index = idx.normalize()
        s = s.groupby(s.index).sum()
        out[f.stem] = s
    out["i0075_monthend_fx"] = i0075_stream()
    return out


def mc_phase(eq0, target, floor_frac, sharpe, vol, max_bets, rng, dd):
    per_mean = sharpe * vol / BETS_PER_YEAR
    per_std = vol / np.sqrt(BETS_PER_YEAR)
    p = SKEW_WINRATE
    b = np.sqrt(p / (1 - p)); a = (1 - p) / p * b
    raw = np.where(rng.random(max_bets) < p, a, -b)
    raw = (raw - raw.mean()) / raw.std()
    d = per_mean + per_std * raw
    eq, peak = eq0, eq0
    for i in range(max_bets):
        eq *= (1 + d[i]); peak = max(peak, eq)
        floor = eq0 * (1 - floor_frac) if dd == "static" else min(peak - floor_frac * eq0, eq0)
        if eq <= floor:
            return "bust", i + 1
        if eq >= eq0 * (1 + target):
            return "pass", i + 1
    return "timeout", max_bets


def mc(sharpe, vol, n, rng, mode):
    mb = BETS_PER_YEAR * 4
    res = []
    for _ in range(n):
        if mode == "1step":
            res.append(mc_phase(1.0, 0.08, 0.05, sharpe, vol, mb, rng, "cti_lock"))
        else:
            r1, b1 = mc_phase(1.0, 0.10, 0.10, sharpe, vol, mb, rng, "static")
            if r1 != "pass":
                res.append((r1, b1)); continue
            res.append(mc_phase(1.0, 0.05, 0.10, sharpe, vol, mb - b1, rng, "static"))
    oc = np.array([r for r, _ in res])
    mo = np.array([b for r, b in res if r == "pass"]) / BETS_PER_YEAR * 12
    return {"p_pass": round(float((oc == "pass").mean()), 3),
            "p_bust": round(float((oc == "bust").mean()), 3),
            "median_months": round(float(np.median(mo)), 1) if len(mo) else None}


def main():
    streams = load_streams()
    # align on common daily calendar
    df = pd.concat(streams, axis=1).sort_index()
    df = df[df.index >= "2017-11-09"]   # crypto-era overlap for a fair joint window

    # standalone sharpe (raw)
    standalone = {k: round(C.ann_sharpe(df[k].dropna()), 3) for k in df.columns}
    # correlation on days where at least one sleeve trades
    corr = df.fillna(0.0).corr().round(2)

    # SURVIVORS: positive standalone Sharpe + economic rationale
    survivors = ["i0075_monthend_fx", "i0076_rsi2_ungated", "i0080_crypto_tsmom"]
    sub = df[survivors].fillna(0.0)
    # inverse-vol (equal-risk) weights
    vol = sub.std()
    w = (1.0 / vol) / (1.0 / vol).sum()
    book = (sub * w).sum(axis=1)
    m = compute_metrics(C.scale_to_vol(book, 0.10))
    book_sharpe = C.ann_sharpe(book)

    # also a variant adding the gated RSI-2 instead of ungated
    survivors_g = ["i0075_monthend_fx", "i0083_rsi2_gated", "i0080_crypto_tsmom"]
    sub_g = df[survivors_g].fillna(0.0)
    wg = (1.0 / sub_g.std()) / (1.0 / sub_g.std()).sum()
    book_g = (sub_g * wg).sum(axis=1)
    book_g_sharpe = C.ann_sharpe(book_g)

    out = {
        "joint_window": f"{df.index.min().date()}..{df.index.max().date()}",
        "standalone_sharpe": standalone,
        "correlation_matrix": corr.to_dict(),
        "book_survivors": survivors,
        "inverse_vol_weights": {k: round(float(v), 3) for k, v in w.items()},
        "book_combined_sharpe_raw": round(book_sharpe, 3),
        "book_sharpe_at10vol": round(m["sharpe"], 3),
        "book_maxdd_at10vol": round(m["max_drawdown"], 4),
        "book_gated_variant_sharpe": round(book_g_sharpe, 3),
        "naive_sqrtK_expectation": round(float(np.mean([standalone[s] for s in survivors]) * np.sqrt(len(survivors))), 3),
    }

    # ── Monte-Carlo at the achieved combined Sharpe ──
    rng = np.random.default_rng(7)
    out["monte_carlo"] = {}
    for s_label, s_val in [("achieved_book", round(book_sharpe, 2)), ("target_1.5", 1.5)]:
        for vv in (0.10, 0.12, 0.15):
            for mode in ("1step", "2step"):
                r = mc(s_val, vv, 6000, rng, mode)
                out["monte_carlo"][f"{s_label}_s{s_val}_v{int(vv*100)}_{mode}"] = r

    print("=== BATCH-5 BOOK INTEGRATION ===")
    print("Standalone Sharpe:", json.dumps(standalone, indent=2))
    print("\nCorrelation matrix:\n", corr.to_string())
    print(f"\nSurvivor book ({survivors}) inv-vol weights:",
          {k: round(float(v), 2) for k, v in w.items()})
    print(f"Book combined Sharpe (raw): {book_sharpe:.3f}  | naive sqrt-K would be {out['naive_sqrtK_expectation']}")
    print(f"Book Sharpe @10% vol: {m['sharpe']:.3f}  MaxDD: {m['max_drawdown']:.3f}")
    print(f"Gated-RSI2 variant book Sharpe: {book_g_sharpe:.3f}")
    print("\nMonte-Carlo (achieved book vs target 1.5):")
    for k, v in out["monte_carlo"].items():
        print(f"  {k}: {v}")
    (C.RESULTS / "book_integration.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
