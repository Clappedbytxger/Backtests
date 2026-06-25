"""Daily gate for the I0038 USD-regime overlay (strategy 0086).

Frozen rule: when the US-Dollar index (DXY) 63-trading-day momentum is NEGATIVE,
hold a long, equal-weight commodity/EM basket (Gold GC, Copper HG, WTI CL, EM
equities EEM); when DXY momentum turns positive, go flat. The structural USD-
commodity inverse relationship is timeable (0086: timed Sharpe 0.86 vs B&H 0.34,
permutation p=0.002). Uses the prior close, matching the backtest.

CAVEAT (in calendar.yaml too): regime overlay with FEW independent episodes →
testing/Lead, size small. Alerts only on a regime flip.

Standalone: .venv/Scripts/python.exe live/signals/dxy_regime_signal.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

LOOKBACK = 63
BASKET = ["GC=F", "HG=F", "CL=F", "EEM"]
STATE_FILE = ROOT / "live" / "state" / "dxy_regime_state.json"


def check(refresh: bool = True) -> dict:
    from quantlab.data import get_prices
    try:
        dxy = get_prices("DX-Y.NYB", start="2024-01-01", force_refresh=refresh)["Close"]
    except Exception:
        dxy = get_prices("UUP", start="2024-01-01", force_refresh=refresh)["Close"]
    mom = dxy.pct_change(LOOKBACK).dropna()
    asof = mom.index[-1]
    m = float(mom.iloc[-1])
    state = "long_basket" if m < 0 else "flat"

    prev = json.loads(STATE_FILE.read_text()).get("state") if STATE_FILE.exists() else None
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"state": state, "dxy_63d_mom": round(m, 4),
                                      "asof": str(asof.date())}, indent=2))
    flipped = prev is not None and prev != state
    if state == "long_basket":
        msg = (f"USD-Regime RISK-ON (DXY 63d-Momentum {m:+.1%} < 0): LONG gleichgewichteter "
               f"Korb {'/'.join(BASKET)} (klein sizen — Regime-Lead, wenige Episoden).")
    else:
        msg = (f"USD-Regime RISK-OFF (DXY 63d-Momentum {m:+.1%} >= 0): Korb FLAT / schliessen.")
    return {"state": state, "mom": m, "asof": asof, "flipped": flipped,
            "prev_state": prev, "message": msg}


if __name__ == "__main__":
    r = check()
    print(f"[{r['asof']:%Y-%m-%d}] {r['message']}{' (FLIP!)' if r['flipped'] else ''}")
