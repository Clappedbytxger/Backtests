"""Monte-Carlo: how long to reach +8% with the two batch-4 leads under the CTI
5% balance-based trailing drawdown.

Time-to-target is NOT mean/target — it is governed by the sizing (capped by the 5%
trailing DD) and the variance/skew of the bets. We resample the REAL per-trade
(I0076) and per-event (I0075) net return distributions, combine them equal-risk,
scale the book to a target annual vol, and simulate the account path bet-by-bet
(balance-based = checked at each closed bet, matching CTI's trailing rule).

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/sim_time_to_target.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import _common as C
from quantlab.data import get_prices
import e1_monthend_fx as e1
import e2_index_rsi2 as e2

RESULTS = Path(__file__).resolve().parent / "results"


def get_i0076_net() -> np.ndarray:
    nets = []
    for name, tk in e2.INDICES.items():
        d = e2.prep(get_prices(tk, start="1995-01-01"))
        trades = e2.run_index(d)
        nets.extend(e2.net_returns(trades).tolist())
    return np.array(nets)


def get_i0075_net() -> np.ndarray:
    eq = get_prices("^GSPC", start="2003-01-01")["Close"]
    eq_sign = e1.month_to_date_equity_sign(eq)
    closes = {t: get_prices(t, start="2003-01-01")["Close"] for t in e1.PAIRS}
    import pandas as pd
    rets = pd.DataFrame(closes).pct_change()
    ev = []
    for lbd, sgn in eq_sign.items():
        if lbd not in rets.index or np.isnan(sgn) or sgn == 0:
            continue
        row = rets.loc[lbd]
        legs = [usd_short * row.get(t, np.nan) for t, usd_short in e1.PAIRS.items()
                if not np.isnan(row.get(t, np.nan))]
        if legs:
            ev.append(sgn * np.mean(legs))
    s = np.array(ev)
    return s - C.SPREAD_RT["fx"] / 1e4  # net of FX spread


def _vol_to_lev(target_vol, std76, std75, n76_yr, n75_yr):
    s76_base, s75_base = 1.0, std76 / std75
    vol_base = np.sqrt(n76_yr * (std76 * s76_base) ** 2 + n75_yr * (std75 * s75_base) ** 2)
    L = target_vol / vol_base
    return s76_base * L, s75_base * L


def simulate(r76, r75, target_vol, n76_yr, n75_yr, horizon_yr=3, n_paths=20000,
             target=0.08, trail=0.05, dd_type="cti_lock", vol_late=None, seed=1) -> dict:
    """dd_type: 'trailing' (perpetual), 'static' (fixed floor at 1-trail),
    'cti_lock' (5% trail that locks at initial balance once HWM = initial+trail).
    vol_late: if set, switch to this target vol once eq >= 1+trail (the lock trick)."""
    rng = np.random.default_rng(seed)
    std76, std75 = r76.std(), r75.std()
    s76, s75 = _vol_to_lev(target_vol, std76, std75, n76_yr, n75_yr)
    s76L, s75L = (_vol_to_lev(vol_late, std76, std75, n76_yr, n75_yr)
                  if vol_late else (s76, s75))

    total_bets = (n76_yr + n75_yr) * horizon_yr
    bets_per_yr = n76_yr + n75_yr
    n76_tot, n75_tot = n76_yr * horizon_yr, n75_yr * horizon_yr

    pass_times, outcomes = [], []
    for _ in range(n_paths):
        flags = np.array([True] * n76_tot + [False] * n75_tot)
        rng.shuffle(flags)
        is76 = flags
        d76 = rng.choice(r76, total_bets)
        d75 = rng.choice(r75, total_bets)
        eq, peak = 1.0, 1.0
        result, t_pass = "timeout", None
        for i in range(total_bets):
            late = eq >= (1.0 + trail)
            a76 = (s76L if late else s76)
            a75 = (s75L if late else s75)
            d = d76[i] * a76 if is76[i] else d75[i] * a75
            eq *= (1.0 + d)
            peak = max(peak, eq)
            if dd_type == "trailing":
                floor = peak - trail
            elif dd_type == "static":
                floor = 1.0 - trail
            else:  # cti_lock
                floor = min(peak - trail, 1.0)
            if eq <= floor:
                result = "bust"; break
            if eq >= 1.0 + target:
                result = "pass"; t_pass = (i + 1) / bets_per_yr * 12.0; break
        outcomes.append(result)
        if result == "pass":
            pass_times.append(t_pass)
    outcomes = np.array(outcomes); pass_times = np.array(pass_times)
    return {
        "target_vol_pct": round(target_vol * 100, 1),
        "vol_late_pct": round(vol_late * 100, 1) if vol_late else None,
        "ann_return_est_pct": round(float((n76_yr * r76.mean() * s76 + n75_yr * r75.mean() * s75) * 100), 1),
        "p_pass_8pct": round(float((outcomes == "pass").mean()), 3),
        "p_bust": round(float((outcomes == "bust").mean()), 3),
        "median_months": round(float(np.median(pass_times)), 1) if len(pass_times) else None,
        "p25_months": round(float(np.percentile(pass_times, 25)), 1) if len(pass_times) else None,
        "p75_months": round(float(np.percentile(pass_times, 75)), 1) if len(pass_times) else None,
    }


def main() -> None:
    r76 = get_i0076_net()
    r75 = get_i0075_net()
    n76_yr, n75_yr = 43, 12
    print(f"I0076: n={len(r76)} mean={r76.mean()*1e4:.1f}bps std={r76.std()*1e4:.0f}bps "
          f"Sharpe/trade={r76.mean()/r76.std():.3f}")
    print(f"I0075: n={len(r75)} mean={r75.mean()*1e4:.1f}bps std={r75.std()*1e4:.0f}bps "
          f"Sharpe/event={r75.mean()/r75.std():.3f}")
    # combined equal-risk annualised Sharpe
    std76, std75 = r76.std(), r75.std()
    s75b = std76 / std75
    mean_yr = n76_yr * r76.mean() + n75_yr * r75.mean() * s75b
    var_yr = n76_yr * std76 ** 2 + n75_yr * (std75 * s75b) ** 2
    print(f"Combined equal-risk annualised Sharpe ~ {mean_yr/np.sqrt(var_yr):.2f}\n")

    out = {}
    print("\n=== REAL CTI 1-Step: 8% target / 5% trailing, LOCKS at breakeven once +5% ===")
    rows = []
    for tv in [0.04, 0.06, 0.08, 0.10, 0.12, 0.15]:
        res = simulate(r76, r75, tv, n76_yr, n75_yr, dd_type="cti_lock")
        rows.append(res)
        print(f"vol {res['target_vol_pct']:>4}% | annRet ~{res['ann_return_est_pct']:>5}% | "
              f"P(pass)={res['p_pass_8pct']:.2f} P(bust)={res['p_bust']:.2f} | "
              f"median {res['median_months']} mo (P25 {res['p25_months']}, P75 {res['p75_months']})")
    out["cti_lock_single_vol"] = rows

    print("\n=== LOCK TRICK: small until +5% (floor locks), then size up for last +3% ===")
    rows2 = []
    for tv_early, tv_late in [(0.04, 0.10), (0.04, 0.15), (0.05, 0.20), (0.06, 0.20), (0.05, 0.30)]:
        res = simulate(r76, r75, tv_early, n76_yr, n75_yr, dd_type="cti_lock", vol_late=tv_late)
        rows2.append(res)
        print(f"early {res['target_vol_pct']:>4}% -> late {res['vol_late_pct']:>4}% | "
              f"P(pass)={res['p_pass_8pct']:.2f} P(bust)={res['p_bust']:.2f} | "
              f"median {res['median_months']} mo (P25 {res['p25_months']}, P75 {res['p75_months']})")
    out["cti_lock_two_stage"] = rows2
    (RESULTS / "sim_time_to_target.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
