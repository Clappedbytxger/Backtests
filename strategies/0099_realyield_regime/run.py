"""Strategy 0099 — Real-Yield / Credit-Spread Regime Overlay (I0066).

Batch-2 idea I0066 from `D:\\Backtest Ideas` (#s24 + #s19). Extends the LIVING 0086
USD-regime overlay (p=0.002) with a SECOND, ideally-uncorrelated macro regime signal.

Two structural signals scale a target exposure (overlay, NOT a standalone bet, exactly
the living 0086 frame):
  (a) real-yield momentum (10y TIPS, FRED DFII10) negative -> tailwind for gold/duration
  (b) credit-spread momentum (HY OAS, FRED BAMLH0A0HYM2) NOT widening -> risk-on
Scale the target (GLD / TLT) long when both favourable, reduce/flat otherwise.

Judged like 0086: does the regime-scaled target beat the unscaled buy&hold AND a
drift-trap permutation (regime TIMING vs random same-count)? Plus: correlation to the
0086 USD-regime position must be LOW (else it is a redundant restatement, not a 2nd signal).

Free data: FRED (DFII10, BAMLH0A0HYM2, T10YIE) + yfinance (GLD/TLT/GC=F/DX-Y.NYB).

Run: .venv/Scripts/python.exe strategies/0099_realyield_regime/run.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import permutation_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def fred(sid: str, start="2003-01-01") -> pd.Series:
    key = (ROOT / ".fred.key").read_text().strip()
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
           f"&api_key={key}&file_type=json&observation_start={start}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return pd.Series({pd.Timestamp(o["date"]): float(o["value"])
                      for o in d["observations"] if o["value"] != "."}).sort_index()


def overlay(target_ret: pd.Series, pos: pd.Series) -> tuple[pd.Series, pd.Series]:
    p = pos.shift(1).reindex(target_ret.index).ffill().fillna(0.0)
    return p * target_ret, p


def main() -> None:
    out = {"idea_id": "I0066"}

    real = fred("DFII10")        # 10y real yield
    hyoas = fred("BAMLH0A0HYM2")  # HY OAS (credit spread)

    # signals (PIT: use levels known at close, momentum over 63d, decided -> shift in overlay)
    real_mom = real.diff(63)                # >0 rising real yield (bearish gold/dur)
    cred_mom = hyoas.diff(21)               # >0 widening spreads (risk-off)

    out["regimes"] = {}
    corr_records = {}
    for tgt_tk, start in [("GLD", "2004-11-19"), ("TLT", "2003-01-01"), ("GC=F", "2003-01-01")]:
        tgt = get_prices(tgt_tk, start=start)["Close"].pct_change().dropna()
        idx = tgt.index
        rm = real_mom.reindex(idx, method="ffill")
        cm = cred_mom.reindex(idx, method="ffill")
        # regime long when real-yield falling AND credit not widening
        favorable = ((rm < 0) & (cm <= 0)).astype(float)
        # variants: real-only, credit-only, combined
        pos_real = (rm < 0).astype(float)
        pos_cred = (cm <= 0).astype(float)
        recs = {}
        for nm, pos in [("real_only", pos_real), ("credit_only", pos_cred), ("combined", favorable)]:
            strat, held = overlay(tgt, pos)
            perm = permutation_test(strat, tgt.reindex(strat.index).fillna(0), held, n_perm=4000, metric="sharpe")
            recs[nm] = {"regime_sharpe": ns(strat), "bh_sharpe": ns(tgt),
                        "regime_cagr_pct": float(compute_metrics(strat)["cagr"] * 100),
                        "bh_cagr_pct": float(compute_metrics(tgt)["cagr"] * 100),
                        "regime_maxdd_pct": float(compute_metrics(strat)["max_drawdown"] * 100),
                        "bh_maxdd_pct": float(compute_metrics(tgt)["max_drawdown"] * 100),
                        "frac_long": float(held.mean()), "perm_p": perm["p_value"]}
            if nm == "combined":
                corr_records[tgt_tk] = held
        out["regimes"][tgt_tk] = recs
        c = recs["combined"]
        print(f"{tgt_tk}: combined regime Sharpe {c['regime_sharpe']:+.2f} vs B&H {c['bh_sharpe']:+.2f}, "
              f"MaxDD {c['regime_maxdd_pct']:.0f}% vs {c['bh_maxdd_pct']:.0f}%, "
              f"long {c['frac_long']:.0%}, perm p={c['perm_p']:.3f}")
        print(f"      (real-only Sharpe {recs['real_only']['regime_sharpe']:+.2f}, "
              f"credit-only {recs['credit_only']['regime_sharpe']:+.2f})")

    # ---- correlation to the living 0086 USD regime (must be LOW for a 2nd signal) ----
    try:
        dxy = get_prices("DX-Y.NYB", start="2003-01-01")["Close"]
    except Exception:  # noqa: BLE001
        dxy = get_prices("UUP", start="2007-01-01")["Close"]
    usd_pos = (dxy.pct_change(63) < 0).astype(float)
    if "GLD" in corr_records:
        gld_pos = corr_records["GLD"]
        c = usd_pos.reindex(gld_pos.index, method="ffill")
        corr = float(np.corrcoef(c.fillna(0), gld_pos.fillna(0))[0, 1])
        out["corr_to_0086_usd_regime"] = corr
        print(f"\nGLD-regime vs 0086 USD-regime position correlation: {corr:+.2f} "
              f"({'LOW -> genuine 2nd signal' if abs(corr) < 0.4 else 'HIGH -> redundant w/ 0086'})")

    # ---- plot ----
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for tgt_tk in ("GLD", "TLT"):
        if tgt_tk in out["regimes"]:
            tgt = get_prices(tgt_tk, start="2004-11-19" if tgt_tk == "GLD" else "2003-01-01")["Close"].pct_change().dropna()
            rm = real_mom.reindex(tgt.index, method="ffill"); cm = cred_mom.reindex(tgt.index, method="ffill")
            pos = ((rm < 0) & (cm <= 0)).astype(float)
            strat, _ = overlay(tgt, pos)
            eq = (1 + strat).cumprod(); bh = (1 + tgt).cumprod()
            ax.plot(eq.index, eq.values, label=f"{tgt_tk} regime (Sh {ns(strat):+.2f})")
            ax.plot(bh.index, bh.values, ls="--", alpha=0.5, label=f"{tgt_tk} B&H (Sh {ns(tgt):+.2f})")
    ax.set_yscale("log"); ax.legend(fontsize=8); ax.grid(alpha=0.3)
    ax.set_title("I0066 real-yield/credit regime overlay vs B&H")
    fig.tight_layout(); fig.savefig(RESULTS / "realyield_regime.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    gld = out["regimes"].get("GLD", {}).get("combined", {})
    lead = (gld.get("perm_p", 1) < 0.05 and gld.get("regime_sharpe", 0) > gld.get("bh_sharpe", 99)
            and abs(out.get("corr_to_0086_usd_regime", 1)) < 0.4)
    print("\nVerdict I0066:", "regime overlay beats B&H, timing significant, uncorrelated to 0086 — overlay candidate."
          if lead else "see REPORT — weak / redundant with 0086 / timing insignificant.")


if __name__ == "__main__":
    main()
