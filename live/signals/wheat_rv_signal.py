"""Daily gate for the I0005 wheat inter-exchange RV spread (strategy 0087).

Frozen rule: z-score mean-reversion on the Chicago-minus-Kansas wheat spread
(log(ZW) - log(KE)), 252d rolling z. Enter at |z|>=2 (z>+2 -> SHORT spread =
short ZW / long KE; z<-2 -> LONG spread = long ZW / short KE), exit when z
returns to 0. Market-neutral within wheat (0087: net Sharpe 0.31, permutation
p=0.000). Stateful (the exit-at-0 needs the current position), so the position
is persisted. Uses prior close, matching the backtest.

CAVEAT: modest Sharpe (~0.31) — testing/weak lead, size small.

Standalone: .venv/Scripts/python.exe live/signals/wheat_rv_signal.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

LB, ENTRY, EXIT = 252, 2.0, 0.0
STATE_FILE = ROOT / "live" / "state" / "wheat_rv_state.json"


def check(refresh: bool = True) -> dict:
    from quantlab.data import get_prices
    zw = get_prices("ZW=F", start="2022-01-01", force_refresh=refresh)["Close"]
    ke = get_prices("KE=F", start="2022-01-01", force_refresh=refresh)["Close"]
    spread = (np.log(zw) - np.log(ke)).dropna()
    z = ((spread - spread.rolling(LB).mean()) / spread.rolling(LB).std()).dropna()
    asof = z.index[-1]
    zz = float(z.iloc[-1])

    prev = json.loads(STATE_FILE.read_text()).get("state") if STATE_FILE.exists() else "flat"
    prev = prev or "flat"
    state = prev
    if prev == "flat":
        if zz >= ENTRY:
            state = "short_spread"   # short ZW / long KE
        elif zz <= -ENTRY:
            state = "long_spread"    # long ZW / short KE
    elif prev == "long_spread" and zz >= EXIT:
        state = "flat"
    elif prev == "short_spread" and zz <= EXIT:
        state = "flat"

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"state": state, "z": round(zz, 2),
                                      "asof": str(asof.date())}, indent=2))
    flipped = state != prev
    label = {"flat": "FLAT (kein Spread)",
             "long_spread": "LONG Spread: LONG ZW (Chicago) / SHORT KE (Kansas)",
             "short_spread": "SHORT Spread: SHORT ZW (Chicago) / LONG KE (Kansas)"}[state]
    msg = f"Weizen-RV z={zz:+.2f} -> {label} (markt-neutral, klein sizen)."
    return {"state": state, "z": zz, "asof": asof, "flipped": flipped,
            "prev_state": prev, "message": msg}


if __name__ == "__main__":
    r = check()
    print(f"[{r['asof']:%Y-%m-%d}] {r['message']}{' (FLIP!)' if r['flipped'] else ''}")
