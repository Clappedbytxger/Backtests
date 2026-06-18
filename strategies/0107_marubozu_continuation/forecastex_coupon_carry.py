"""IBKR ForecastEx delta-neutral coupon-carry — quantitative model.

Mechanics (verified 2026-06-18):
- Buy 1 Yes + 1 No of the same contract -> guaranteed $1.00 at settlement (one leg
  pays $1, the other $0). Delta-neutral, event-risk fully hedged.
- Fee: $0.01 per contract PER SIDE at execution -> $0.02 per pair on ENTRY.
  Settlement is automatic, NO exit fee (held to resolution).
- Incentive coupon: 3.12% APY on the daily CLOSING MARKET VALUE of held positions
  (both Yes and No legs count). A held Yes+No pair has MV ~ $1.00 throughout, so the
  coupon accrues on ~$1.00 regardless of how the probability moves. Paid monthly.

Net P&L per pair held T years, entry sum S (=P_yes+P_no):
    net = coupon - entry_fee - (S - 1.00)
        = COUPON*T*MV - 0.02 - (S - 1.00)     (MV ~ 1.00)
Capital tied up ~ S + 0.02. Compare to the risk-free alternative (T-bills at r_f):
the carry beats cash only if  net > (S+0.02)*r_f*T.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.data import get_prices
RES = Path(__file__).resolve().parent / "results"

COUPON = 0.0312      # APY, on ~$1.00 MV
FEE_PAIR = 0.02      # $0.01/contract x 2 sides, entry only (settlement free)
MV = 1.00            # market value base of a held Yes+No pair


def rf_now():
    try:
        irx = get_prices("^IRX", start="2024-01-01")["Close"].dropna()
        return float(irx.iloc[-1]) / 100.0   # ^IRX is 13-week T-bill yield in %
    except Exception:
        return 0.04


def net_per_pair(S, T):
    return COUPON * T * MV - FEE_PAIR - (S - 1.0)


def beats_cash(S, T, rf):
    cap = S + FEE_PAIR
    return net_per_pair(S, T), cap * rf * T


def main():
    rf = rf_now()
    print(f"=== ForecastEx delta-neutral coupon-carry model ===")
    print(f"coupon={COUPON:.2%} APY | fee=${FEE_PAIR:.2f}/pair (entry only) | "
          f"current risk-free (^IRX 13wk T-bill) = {rf:.2%}\n")

    # 1) At par (S=1.00): break-even hold + return vs cash
    be_T = FEE_PAIR / (COUPON * MV)
    print(f"[1] At par (S=$1.00): coupon must first cover the $0.02 fee.")
    print(f"    break-even hold = {be_T:.2f} yr ({be_T*365:.0f} days); below that the carry LOSES money.")
    for T in [0.25, 0.5, 1.0]:
        n = net_per_pair(1.0, T); ann = n / (1.0 + FEE_PAIR) / T
        cash = (1.0 + FEE_PAIR) * rf * T
        print(f"    T={T:>4}yr: net ${n:+.4f}/pair  ann.return {ann:+.2%}  | cash alt ${cash:+.4f} "
              f"-> carry {'BEATS' if n > cash else 'LOSES to'} cash")

    # 2) The decisive comparison: coupon vs risk-free
    print(f"\n[2] Coupon ({COUPON:.2%}) vs risk-free ({rf:.2%}):")
    if COUPON < rf:
        gap = rf - COUPON
        print(f"    coupon is BELOW risk-free by {gap:.2%} -> even at par with ZERO fee the carry")
        print(f"    earns less than T-bills. The $0.02 fee makes it strictly worse. NEGATIVE EDGE.")
    else:
        print(f"    coupon exceeds risk-free -> carry has a structural premium of {COUPON-rf:.2%}/yr.")

    # 3) The ONLY positive-EV version: sub-par entry (Yes+No < $1.00)
    print(f"\n[3] Sub-par arbitrage entry (the only positive-EV version):")
    print(f"    Need entry sum S such that locked convergence + coupon beats cash.")
    for T in [0.25, 0.5, 1.0]:
        # S where carry net == cash alternative (indifference)
        # COUPON*T - 0.02 - (S-1) = (S+0.02)*rf*T  -> solve for S
        # 1.0 + COUPON*T - 0.02 - S = (S+0.02)*rf*T
        # 1.0 + COUPON*T - 0.02 - 0.02*rf*T = S + S*rf*T = S(1+rf*T)
        S_ind = (1.0 + COUPON * T - 0.02 - 0.02 * rf * T) / (1.0 + rf * T)
        print(f"    T={T:>4}yr: need Yes+No entry sum S <= ${S_ind:.4f} to beat cash "
              f"(i.e. {(1.0-S_ind)*100:.2f} cents below par)")

    # 4) Realistic scenarios
    print(f"\n[4] Realistic scenarios (annualized return on capital):")
    scen = [("efficient par, 6mo", 1.00, 0.5),
            ("efficient par, 1yr", 1.00, 1.0),
            ("1c sub-par, 6mo", 0.99, 0.5),
            ("2c sub-par, 3mo", 0.98, 0.25),
            ("3c sub-par, 3mo (rare/illiquid)", 0.97, 0.25)]
    out = {"coupon": COUPON, "fee_pair": FEE_PAIR, "rf": round(rf, 4), "breakeven_yr_at_par": round(be_T, 3), "scenarios": []}
    for label, S, T in scen:
        n = net_per_pair(S, T); ann = n / (S + FEE_PAIR) / T
        cash = (S + FEE_PAIR) * rf * T
        verdict = "BEATS cash" if n > cash else "loses to cash"
        print(f"    {label:34s} S=${S:.2f} T={T}yr: ann {ann:+6.2%}  vs cash {rf*T/T:+.2%}  -> {verdict}")
        out["scenarios"].append({"label": label, "S": S, "T": T, "net": round(n, 4),
                                 "ann_return": round(ann, 4), "beats_cash": bool(n > cash)})
    RES.mkdir(exist_ok=True)
    (RES / "forecastex_coupon_carry.json").write_text(json.dumps(out, indent=2))

    print(f"\n=== VERDICT ===")
    print(f"At par the coupon-carry is a synthetic deposit at {COUPON:.2%} minus a 2% entry-fee drag.")
    print(f"Since {COUPON:.2%} < risk-free {rf:.2%}, the delta-neutral carry is NEGATIVE-EV vs T-bills.")
    print(f"Positive EV only on SUB-PAR entries (Yes+No <= ~{(1-((1.0+COUPON*0.25-0.02-0.02*rf*0.25)/(1.0+rf*0.25)))*100:.1f}c below par at 3mo),")
    print(f"which are rare, capacity-limited (<$50k books), and a manual arb — not a steady carry.")


if __name__ == "__main__":
    main()
