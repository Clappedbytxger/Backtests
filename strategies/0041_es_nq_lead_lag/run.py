"""Strategy 0041 — ES <-> NQ lead-lag / relative-value reversion (1-minute).

Prop-Edge-Framework.md hypothesis #5 (the last on the list): related instruments
do not move perfectly in sync; temporary dislocations mean-revert. Market-neutral
(long one leg, short the other) -> lower tail risk, the framework's pick for the
cleanest remaining prop class.

Data: ES + NQ 1-minute (Databento GLBX.MDP3, 2010-2026, 1.55M aligned RTH minutes).
Two flavours tested:
  (A) Lead-lag momentum: does one index lead the other minute-to-minute?
  (B) Relative-value reversion: beta-hedged spread, z-score, fade extremes.

Result: REJECTED — but the most informative reject of the program.
  (A) is empty: corr(ES[t], NQ[t+1]) = +0.001, corr(NQ[t], ES[t+1]) = -0.001.
      At the two most liquid index futures the lead-lag is fully HFT-arbitraged.
  (B) is a GENUINE statistical edge — the only real signal found intraday: the
      spread reverts (1-min autocorr -0.107), win rate rises monotonically with
      the z-threshold to 59% at k=2.5. BUT the magnitude is 0.3-0.5 bps/trade
      against a ~6 bps two-leg round-trip -> net ~ -5.5 bps. The edge lives in the
      sub-basis-point microstructure only a co-located, maker-rebate HFT can
      harvest; for a retail prop account it is hopelessly uneconomic.

This is the framework's #1 lesson in its purest form: a real, robust, high-win-rate
intraday edge that cost makes untradeable. Cost is the absolute binding constraint.

Run:
    .venv/Scripts/python.exe strategies/0041_es_nq_lead_lag/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FUT = ROOT / "data" / "cache" / "futures"
ES_1M = FUT / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
NQ_1M = FUT / "NQ_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# One leg ~1.5 bps/side -> a two-leg pairs round-trip is ~6 bps (2 legs x 2 sides).
COST_2LEG = 0.0006
ZS = [1.5, 2.0, 2.5]
HOLDS = [3, 5, 15]


def aligned_rth_returns() -> pd.DataFrame:
    es = pd.read_parquet(ES_1M, columns=["Close"]).tz_convert("US/Eastern")
    nq = pd.read_parquet(NQ_1M, columns=["Close"]).tz_convert("US/Eastern")
    j = es["Close"].rename("ES").to_frame().join(nq["Close"].rename("NQ"), how="inner")
    t = j.index.time
    j = j[(t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())].copy()
    j["date"] = j.index.normalize()
    j["ESr"] = j["ES"].pct_change()
    j["NQr"] = j["NQ"].pct_change()
    fb = j["date"] != j["date"].shift(1)        # null the first bar of each session
    j.loc[fb, ["ESr", "NQr"]] = np.nan
    return j.dropna(subset=["ESr", "NQr"]).copy()


def main() -> None:
    d = aligned_rth_returns()
    n = len(d)
    out = {"cost_2leg": COST_2LEG, "n_minutes": int(n), "lead_lag": {}, "reversion": {}}
    print(f"Aligned ES/NQ RTH 1-min returns: {n:,}\n")

    # ---- (A) lead-lag ----
    contemp = float(d["ESr"].corr(d["NQr"]))
    print(f"contemporaneous corr(ES, NQ) = {contemp:.4f}")
    print("lead-lag:  corr(ES[t], NQ[t+k])   corr(NQ[t], ES[t+k])")
    ll = {}
    for k in range(0, 6):
        c1 = float(d["ESr"].corr(d["NQr"].shift(-k)))
        c2 = float(d["NQr"].corr(d["ESr"].shift(-k)))
        ll[k] = (c1, c2)
        print(f"  k={k}:   {c1:+.4f}            {c2:+.4f}")
    out["lead_lag"] = {"contemporaneous": contemp,
                       "es_leads_nq": {k: v[0] for k, v in ll.items()},
                       "nq_leads_es": {k: v[1] for k, v in ll.items()}}
    print("=> no lead-lag: one cannot predict the other from its past minute.\n")

    # ---- (B) relative-value reversion ----
    beta = float((d["ESr"] * d["NQr"]).sum() / (d["ESr"] ** 2).sum())
    d["spr"] = d["NQr"] - beta * d["ESr"]          # market-neutral spread return
    spr_ac1 = float(d["spr"].autocorr(1))
    print(f"hedge beta (NQ on ES) = {beta:.3f}   spread 1-min autocorr = {spr_ac1:+.4f} "
          f"(negative = reversion)")
    g = d.groupby("date")
    d["cum"] = g["spr"].cumsum()
    d["mu"] = g["cum"].transform(lambda x: x.rolling(30, min_periods=10).mean())
    d["sd"] = g["cum"].transform(lambda x: x.rolling(30, min_periods=10).std())
    d["z"] = (d["cum"] - d["mu"]) / d["sd"]
    for H in HOLDS:
        d[f"fwd{H}"] = g["cum"].shift(-H) - d["cum"]

    print("\nz-score reversion (short spread if z>k, long if z<-k); net at 6 bps RT (2 legs):")
    grid = {}
    best = {"gross": -1e9}
    for k in ZS:
        for H in HOLDS:
            sig = pd.Series(np.where(d["z"] > k, -1.0, np.where(d["z"] < -k, 1.0, 0.0)),
                            index=d.index)
            r = (sig * d[f"fwd{H}"]).where(sig != 0).dropna()
            gross = float(r.mean())
            grid[f"k{k}_H{H}"] = {"n": int(len(r)), "gross_bps": gross * 1e4,
                                  "net_bps": (gross - COST_2LEG) * 1e4,
                                  "win": float((r > 0).mean())}
            print(f"  k={k} H={H:2d}m: n={len(r):6d}  gross/tr={gross*1e4:5.2f}bps  "
                  f"net={ (gross-COST_2LEG)*1e4:6.2f}bps  win={(r>0).mean()*100:4.1f}%")
            if gross > best["gross"]:
                best = {"gross": gross, "k": k, "H": H, "win": float((r > 0).mean())}
    out["reversion"] = {"beta": beta, "spread_autocorr1": spr_ac1, "grid": grid}

    # break-even cost: what round-trip would the best gross edge need?
    be = best["gross"]  # per round-trip on the 2-leg notional
    out["best"] = {"k": best["k"], "H": best["H"], "gross_bps": best["gross"] * 1e4,
                   "win": best["win"], "breakeven_rt_bps": be * 1e4,
                   "breakeven_per_side_per_leg_bps": be * 1e4 / 4}
    print(f"\nBest cell k={best['k']} H={best['H']}: gross {best['gross']*1e4:.2f} bps, "
          f"win {best['win']*100:.1f}%.")
    print(f"Break-even needs RT <= {be*1e4:.2f} bps total = {be*1e4/4:.3f} bps/side/leg "
          f"-> only a maker-rebate HFT clears it; retail pays ~6 bps. UNECONOMIC.")

    # ---- plots ----
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    ks = list(range(0, 6))
    ax[0].bar([k - 0.18 for k in ks], [ll[k][0] for k in ks], 0.36, label="ES leads NQ", color="steelblue")
    ax[0].bar([k + 0.18 for k in ks], [ll[k][1] for k in ks], 0.36, label="NQ leads ES", color="indianred")
    ax[0].set_xlabel("lag k (minutes)")
    ax[0].set_ylabel("cross-correlation")
    ax[0].set_title("ES<->NQ lead-lag: spike only at k=0 (contemp.),\nzero at every lag — no lead-lag to trade")
    ax[0].legend(); ax[0].grid(alpha=0.3)
    # reversion: win-rate & gross vs z, with cost line
    k_axis = ZS
    gross_by_k = [grid[f"k{k}_H5"]["gross_bps"] for k in ZS]
    win_by_k = [grid[f"k{k}_H5"]["win"] * 100 for k in ZS]
    ax2 = ax[1]
    ax2.plot(k_axis, gross_by_k, "o-", color="seagreen", label="gross bps/trade")
    ax2.axhline(COST_2LEG * 1e4, color="crimson", ls="--", label="2-leg cost (6 bps)")
    ax2.set_xlabel("z-score entry threshold")
    ax2.set_ylabel("gross bps/trade", color="seagreen")
    ax2.set_ylim(0, 7)
    ax3 = ax2.twinx()
    ax3.plot(k_axis, win_by_k, "s--", color="navy", label="win rate")
    ax3.set_ylabel("win rate (%)", color="navy")
    ax2.set_title("Reversion is REAL (win 55-59%) but tiny:\ngross stays far under the 6 bps cost line")
    ax2.legend(loc="upper left"); ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "lead_lag_reversion.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2))
    print("\nVerdict: REJECTED (uneconomic). Lead-lag empty; RV reversion is a real, "
          "robust edge buried under cost — the framework's #1 lesson in pure form.")


if __name__ == "__main__":
    main()
