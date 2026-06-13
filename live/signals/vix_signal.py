"""Daily gate check for the 0056 VIX-carry sleeve.

Frozen rule (0056, linear-sized variant): short VIXY at 14.9% of the sleeve
whenever VIX3M/VIX > 1.03 (term structure in contango with buffer), flat
otherwise. Vol-targeting is deliberately NOT used (0056 lesson: it destroys
the gap-driven edge). The gate uses the PRIOR close, matching the backtest.

``check()`` compares today's gate state against the persisted last state and
returns an alert only on a flip — so the daily run stays quiet most days.

Standalone:
    .venv/Scripts/python.exe live/signals/vix_signal.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

GATE_RATIO = 1.03
SLEEVE_FACTOR = 0.149
STATE_FILE = ROOT / "live" / "state" / "vix_state.json"


def check(refresh: bool = True) -> dict:
    """Evaluate the gate; returns {state, ratio, asof, flipped, message}."""
    from quantlab.data import get_prices

    vix = get_prices("^VIX", start="2025-01-01", force_refresh=refresh)["Close"]
    vix3m = get_prices("^VIX3M", start="2025-01-01", force_refresh=refresh)["Close"]
    ratio = (vix3m / vix).dropna()
    asof = ratio.index[-1]
    r = float(ratio.iloc[-1])
    state = "short" if r > GATE_RATIO else "flat"

    prev = None
    if STATE_FILE.exists():
        prev = json.loads(STATE_FILE.read_text()).get("state")
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(
        {"state": state, "ratio": round(r, 4), "asof": str(asof.date())}, indent=2))

    flipped = prev is not None and prev != state
    if state == "short":
        msg = (f"VIX-Gate OFFEN (VIX3M/VIX = {r:.3f} > {GATE_RATIO}): "
               f"SHORT VIXY mit Sleeve-Faktor {SLEEVE_FACTOR:.1%}.")
    else:
        msg = (f"VIX-Gate ZU (VIX3M/VIX = {r:.3f} <= {GATE_RATIO}): "
               f"VIXY-Short schliessen / flat bleiben.")
    return {"state": state, "ratio": r, "asof": asof, "flipped": flipped,
            "prev_state": prev, "message": msg}


if __name__ == "__main__":
    res = check()
    flip = " (FLIP!)" if res["flipped"] else ""
    print(f"[{res['asof']:%Y-%m-%d}] {res['message']}{flip}")
