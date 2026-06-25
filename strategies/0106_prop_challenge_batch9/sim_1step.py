"""CTI 1-Step pass-rate MC for the CORE book (I0092+I0076+I0100+I0099).

The report's 0.53 pass rate is for the 2-Step (10% static + 5% daily). This runs
the 1-Step instead: single phase, +8% target, 5% BALANCE-BASED TRAILING drawdown
that LOCKS at the initial balance once the peak reaches +5% (CTI's actual rule),
and NO daily limit. Same daily-net CORE streams + moving-block bootstrap as
book_integration.py, so the two products are compared apples-to-apples.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"
ANN = np.sqrt(252)
S5 = ROOT / "strategies/0103_prop_challenge_batch5/results/streams"
S9 = ROOT / "strategies/0106_prop_challenge_batch9/results/streams"

SLEEVES = {
    "I0092 monthend-FX":  S9 / "i0092_monthend_fx.parquet",
    "I0076 index-RSI2":   S5 / "i0076_rsi2_ungated.parquet",
    "I0100 carry-gated":  S9 / "i0100_carry_riskgated.parquet",
    "I0099 crypto-gated": S9 / "i0099_crypto_gated.parquet",
}


def load_book():
    out = {}
    for name, p in SLEEVES.items():
        if p.exists():
            s = pd.read_parquet(p).iloc[:, 0]
            s.index = pd.to_datetime(s.index).tz_localize(None)
            out[name] = s
    df = pd.DataFrame(out).sort_index().fillna(0.0)
    df = df.loc[df.index >= df.apply(lambda c: c.ne(0).idxmax()).max()]
    vols = df.std() * ANN
    invvol = (1.0 / vols).replace([np.inf, np.nan], 0.0)
    w = invvol / invvol.sum()
    return (df * w).sum(axis=1)


def mc_1step(book, target_vol=0.08, horizon_yr=3.0, n_paths=30000, seed=1,
             target=0.08, trail=0.05, block=5):
    r = book.dropna().values
    r = r * (target_vol / (r.std() * ANN))   # scale to account vol
    rng = np.random.default_rng(seed)
    days = int(252 * horizon_yr)
    nblk = days // block + 1
    pool = np.arange(len(r) - block)
    passes = busts = 0
    times = []
    for _ in range(n_paths):
        st = rng.choice(pool, nblk)
        path = np.concatenate([r[s:s + block] for s in st])[:days]
        eq = peak = 1.0
        res = "timeout"
        for i, d in enumerate(path):
            eq *= (1.0 + d)
            peak = max(peak, eq)
            floor = min(peak - trail, 1.0)     # trailing, then locks at breakeven once peak>=1+trail
            if eq <= floor:
                res = "bust"; break
            if eq >= 1.0 + target:
                res = "pass"; times.append((i + 1) / 252 * 12); break
        if res == "pass": passes += 1
        elif res == "bust": busts += 1
    return {
        "target_vol_pct": round(target_vol * 100, 1),
        "p_pass": round(passes / n_paths, 3),
        "p_bust": round(busts / n_paths, 3),
        "p_timeout": round(1 - (passes + busts) / n_paths, 3),
        "median_months": round(float(np.median(times)), 1) if times else None,
        "worst_day_pct": round(float(book.min() / (book.std() * ANN) * target_vol * 100), 2),
    }


def main():
    book = load_book()
    sharpe = book.mean() / book.std() * ANN
    print(f"CORE book daily Sharpe = {sharpe:+.2f}  (n={len(book)} days, "
          f"{book.index[0].date()}..{book.index[-1].date()})\n")
    print("=== CTI 1-STEP: +8% target / 5% balance-based trailing (locks at breakeven once +5%) "
          "/ NO daily limit ===")
    out = {"core_sharpe": round(sharpe, 3), "mc_1step": []}
    for tv in [0.04, 0.06, 0.08, 0.10, 0.12]:
        res = mc_1step(book, target_vol=tv)
        out["mc_1step"].append(res)
        print(f"  vol {res['target_vol_pct']:>4}% | P(pass)={res['p_pass']:.2f} "
              f"P(bust)={res['p_bust']:.2f} P(timeout)={res['p_timeout']:.2f} | "
              f"median {res['median_months']} mo | worst-day {res['worst_day_pct']}%")
    (RESULTS / "sim_1step.json").write_text(json.dumps(out, indent=2))
    print("\nsaved results/sim_1step.json")
    print("\n(compare: 2-Step @8% vol from book_integration.json = P(pass both) 0.53 / bust 0.05)")


if __name__ == "__main__":
    main()
