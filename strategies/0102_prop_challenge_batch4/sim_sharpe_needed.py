"""What combined Sharpe is required to pass CTI in <=2 months at <15% bust?

Extends sim_time_to_target.py / sim_2step.json (which stop at Sharpe 1.05).
Parametric per-bet Monte-Carlo so Sharpe is the explicit knob. The per-bet
distribution carries a realistic NEGATIVE skew (high-win / occasional larger
loss, like the I0076 RSI-2 mean-reversion leg) so bust is not understated vs a
naive GBM. Calibrated to reproduce the existing real-distribution sim
(Sharpe 0.88, 8% vol, 2-step => p_bust ~0.16) as a sanity gate.

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/sim_sharpe_needed.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"
BETS_PER_YEAR = 60          # ~ I0076 (43) + I0075 (12) + small sleeves
SKEW_WINRATE = 0.66         # fraction of bets that are the "small positive" type


def make_bet_dist(sharpe, ann_vol, n, rng):
    """Per-bet returns with target annualized Sharpe + vol and negative skew.
    Two-point mixture: frequent small wins, rarer larger losses, then affine-
    rescaled to hit the exact target per-bet mean and std."""
    per_mean = sharpe * ann_vol / BETS_PER_YEAR
    per_std = ann_vol / np.sqrt(BETS_PER_YEAR)
    p = SKEW_WINRATE
    # raw skewed shape (mean 0, std 1-ish): win=+a, loss=-b with p*a=(1-p)*b
    b = np.sqrt(p / (1 - p))
    a = (1 - p) / p * b
    raw = np.where(rng.random(n) < p, a, -b)
    raw = (raw - raw.mean()) / raw.std()
    return per_mean + per_std * raw


def run_phase(eq0, target, floor_frac, sharpe, ann_vol, max_bets, rng, dd="static"):
    """Simulate one phase from eq0. floor_frac: static floor = eq0*(1-floor_frac).
    Returns (result, bets_used). dd='static' (2-step) or 'cti_lock' (1-step)."""
    eq, peak = eq0, eq0
    d = make_bet_dist(sharpe, ann_vol, max_bets, rng)
    for i in range(max_bets):
        eq *= (1.0 + d[i])
        peak = max(peak, eq)
        if dd == "static":
            floor = eq0 * (1.0 - floor_frac)
        else:  # cti_lock: 5% trail that locks at initial once +5% reached
            floor = min(peak - floor_frac * eq0, eq0)
        if eq <= floor:
            return "bust", i + 1
        if eq >= eq0 * (1.0 + target):
            return "pass", i + 1
    return "timeout", max_bets


def sim_1step(sharpe, ann_vol, n_paths, rng, horizon_yr=4):
    mb = int(BETS_PER_YEAR * horizon_yr)
    res = [run_phase(1.0, 0.08, 0.05, sharpe, ann_vol, mb, rng, dd="cti_lock") for _ in range(n_paths)]
    return _summ(res)


def sim_2step(sharpe, ann_vol, n_paths, rng, horizon_yr=4):
    mb = int(BETS_PER_YEAR * horizon_yr)
    out = []
    for _ in range(n_paths):
        r1, b1 = run_phase(1.0, 0.10, 0.10, sharpe, ann_vol, mb, rng, dd="static")
        if r1 != "pass":
            out.append((r1, b1)); continue
        r2, b2 = run_phase(1.0, 0.05, 0.10, sharpe, ann_vol, mb - b1, rng, dd="static")
        out.append((r2, b1 + b2) if r2 == "pass" else (r2, b1 + b2))
    return _summ(out)


def _summ(res):
    outcomes = np.array([r for r, _ in res])
    months = np.array([b for r, b in res if r == "pass"]) / BETS_PER_YEAR * 12.0
    return {
        "p_pass": round(float((outcomes == "pass").mean()), 3),
        "p_bust": round(float((outcomes == "bust").mean()), 3),
        "median_months": round(float(np.median(months)), 1) if len(months) else None,
        "p25_months": round(float(np.percentile(months, 25)), 1) if len(months) else None,
    }


def main():
    rng = np.random.default_rng(7)
    # --- calibration gate vs existing sim_2step.json (0.88 / 8% => bust ~0.16) ---
    cal = sim_2step(0.88, 0.08, 20000, rng)
    print(f"[calib] 2-step Sharpe0.88 vol8%: {cal}  (target bust~0.16, median~18mo)\n")

    sharpes = [0.88, 1.05, 1.3, 1.6, 2.0, 2.5, 3.0, 3.5]
    vols = [0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    out = {"one_step": {}, "two_step": {}}
    for label, fn in [("1-STEP (8% / 5% trail-lock)", sim_1step),
                      ("2-STEP (10%+5% / 10% static)", sim_2step)]:
        print(f"=== {label} ===")
        print("Sharpe |  vol  | P(pass) P(bust) | median mo (P25)  <-- want median<=2 & bust<0.15")
        key = "one_step" if "1-STEP" in label else "two_step"
        for s in sharpes:
            for v in vols:
                r = fn(s, v, 8000, rng)
                hit = "  <== FAST&SAFE" if (r["median_months"] is not None
                        and r["median_months"] <= 2.0 and r["p_bust"] < 0.15) else ""
                print(f" {s:>4} | {v*100:>4.0f}% |  {r['p_pass']:.2f}    {r['p_bust']:.2f}  | "
                      f"{str(r['median_months']):>5} mo (P25 {r['p25_months']}){hit}")
                out[key][f"s{s}_v{int(v*100)}"] = {"sharpe": s, "vol": v, **r}
            print()
    (RESULTS / "sim_sharpe_needed.json").write_text(json.dumps(out, indent=2))
    print("saved -> results/sim_sharpe_needed.json")


if __name__ == "__main__":
    main()
