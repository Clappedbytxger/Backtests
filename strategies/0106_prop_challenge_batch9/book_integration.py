"""CTI 2-Step book integration with the batch-9 additions (I0100 lead + I0099 overlay).

Loads the confirmed lead/overlay daily-net streams, builds the correlation matrix,
an inverse-vol (equal-risk) combined book, the combo Sharpe, the equity-beta share,
and a daily-path 2-Step Monte-Carlo (Phase1 +10% / Phase2 +5%, 10% STATIC floor +
5% daily limit). All streams are daily NET returns (flat=0 on non-signal days).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import sys; sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices
RESULTS = Path(__file__).resolve().parent / "results"
ANN = np.sqrt(252)

S5 = ROOT / "strategies/0103_prop_challenge_batch5/results/streams"
S9 = ROOT / "strategies/0106_prop_challenge_batch9/results/streams"

# confirmed leads/overlays with saved streams. (i0092 = month-end FX flow, confirms I0075)
SLEEVES = {
    "I0092 monthend-FX":  (S9 / "i0092_monthend_fx.parquet",  "flow",   False),
    "I0076 index-RSI2":   (S5 / "i0076_rsi2_ungated.parquet", "MR",     True),   # equity-beta
    "I0100 carry-gated":  (S9 / "i0100_carry_riskgated.parquet", "carry", False),
    "I0099 crypto-gated": (S9 / "i0099_crypto_gated.parquet",  "crypto", False),
}
# optional diversifiers (marginal but decorrelated)
DIVERS = {
    "I0091 gap-reversal": (ROOT / "strategies/0105_prop_challenge_batch7/results/streams/i0091_gap_reversal.parquet", "MR", True),
    "I0095 commodity-FX": (S9 / "i0095_commodity_fx_leadlag.parquet", "RV", False),
}


def load(streams):
    out = {}
    for name, (p, _, _) in streams.items():
        if p.exists():
            s = pd.read_parquet(p).iloc[:, 0]
            s.index = pd.to_datetime(s.index).tz_localize(None)
            out[name] = s
    return pd.DataFrame(out)


def book_stats(df, label):
    # align on union of dates, flat (0) when a sleeve has no signal that day
    df = df.sort_index().fillna(0.0)
    df = df.loc[df.index >= df.apply(lambda c: c.ne(0).idxmax()).max()]  # start when all live
    vols = df.std() * ANN
    invvol = (1.0 / vols).replace([np.inf, np.nan], 0.0)
    w = invvol / invvol.sum()
    book = (df * w).sum(axis=1)
    sharpe = book.mean() / book.std() * ANN if book.std() else 0.0
    print(f"\n===== {label} =====")
    print("per-sleeve (scaled to 10% vol each): Sharpe")
    for c in df.columns:
        s = df[c]; sc = s / (s.std() * ANN) * 0.10 if s.std() else s
        print(f"  {c:22s} Sharpe={s.mean()/s.std()*ANN if s.std() else 0:+.2f}  weight={w[c]:.0%}")
    print("\ncorrelation matrix (daily):")
    corr = df.corr()
    print(corr.round(2).to_string())
    print(f"\nINVERSE-VOL COMBO BOOK Sharpe = {sharpe:+.2f}  (naive sqrt(K) ceiling ~ "
          f"{np.mean([df[c].mean()/df[c].std()*ANN if df[c].std() else 0 for c in df.columns])*np.sqrt(len(df.columns)):+.2f})")
    eqcols = [n for n in df.columns if SLEEVES.get(n, DIVERS.get(n, (None, None, False)))[2]]
    eq_beta_w = w[eqcols].sum() if eqcols else 0.0
    print(f"equity-beta sleeve weight = {eq_beta_w:.0%} (target <=30%)")
    return book, w, sharpe


def mc_2step(book, target_vol=0.08, horizon_yr=2.0, n_paths=20000, seed=1,
             p1_target=0.10, p2_target=0.05, static_dd=0.10, daily_dd=0.05, block=5):
    """Daily-path 2-Step MC. Phase1 +10% then Phase2 +5%, each with 10% static floor
    (from phase start) + 5% daily limit. Moving-block bootstrap of daily book returns."""
    r = book.dropna().values
    k = target_vol / (r.std() * ANN)       # scale to account vol
    r = r * k
    rng = np.random.default_rng(seed)
    days = int(252 * horizon_yr)
    nblk = days // block + 1
    starts_pool = np.arange(len(r) - block)

    def run_phase(path, target):
        eq = 1.0
        for d in path:
            if d <= -daily_dd:        # 5% daily limit (single-day)
                return "bust", None
            eq *= (1.0 + d)
            if eq <= 1.0 - static_dd:  # 10% static floor from phase start
                return "bust", None
            if eq >= 1.0 + target:
                return "pass", None
        return "timeout", None

    passes = 0; busts = 0; times = []
    for _ in range(n_paths):
        st = rng.choice(starts_pool, nblk)
        path = np.concatenate([r[s:s + block] for s in st])[:days]
        half = len(path) // 2
        r1, _ = run_phase(path[:half], p1_target)
        if r1 == "bust":
            busts += 1; continue
        if r1 != "pass":
            continue
        r2, _ = run_phase(path[half:], p2_target)
        if r2 == "bust":
            busts += 1
        elif r2 == "pass":
            passes += 1
            times.append(horizon_yr * 12)  # crude (path-length proxy)
    return {"target_vol_pct": round(target_vol * 100, 1),
            "p_pass_both": round(passes / n_paths, 3),
            "p_bust": round(busts / n_paths, 3),
            "worst_day_pct": round(float(book.min() / (book.std() * ANN) * target_vol * 100), 2)}


def main():
    print("################ CORE BOOK (4 confirmed leads/overlays) ################")
    core = load(SLEEVES)
    book, w, sh = book_stats(core, "CORE: I0092 + I0076 + I0100 + I0099")
    print("\n--- 2-Step Monte-Carlo (daily path, 10% static + 5% daily) ---")
    out = {"core_sharpe": round(sh, 3), "mc": []}
    for tv in [0.06, 0.08, 0.10]:
        res = mc_2step(book, target_vol=tv)
        out["mc"].append(res)
        print(f"  vol {res['target_vol_pct']:>4}% | P(pass both)={res['p_pass_both']:.2f} "
              f"P(bust)={res['p_bust']:.2f} | worst-day {res['worst_day_pct']}%")

    print("\n################ EXTENDED BOOK (+ diversifiers I0091/I0095) ################")
    ext = load({**SLEEVES, **DIVERS})
    book2, w2, sh2 = book_stats(ext, "EXTENDED: core + I0091 + I0095")
    out["extended_sharpe"] = round(sh2, 3)
    for tv in [0.08]:
        res = mc_2step(book2, target_vol=tv)
        print(f"  vol {res['target_vol_pct']:>4}% | P(pass both)={res['p_pass_both']:.2f} "
              f"P(bust)={res['p_bust']:.2f} | worst-day {res['worst_day_pct']}%")
    (RESULTS / "book_integration.json").write_text(json.dumps(out, indent=2))
    print("\nsaved results/book_integration.json")


if __name__ == "__main__":
    main()
