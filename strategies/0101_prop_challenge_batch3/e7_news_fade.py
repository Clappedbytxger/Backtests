"""I0074 - Post-news volatility-stabilization (FOMC subset).

Trade the DECAY after a release, not the spike. The full idea needs intraday tick
around NFP/CPI/FOMC plus a PIT consensus-surprise feed (no free survivorship-safe
source -> NFP/CPI stay data-blocked). FOMC is testable: announcement at 14:00 ET
(2012+; 14:15 ET pre-2012), and we already have the audited FOMC list (0052) + ES
1-min. We measure both the FADE (mean-revert the first move) and the CONTINUATION.

Sample is tiny (~8/yr) -> exploratory only. CFD_INDEX cost charged.
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

import _common as C
from quantlab.costs import CFD_INDEX

# reuse the audited FOMC list from strategy 0052
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "0052_pre_fomc_drift"))
from run import FOMC  # noqa: E402

COST_RT = 2 * (CFD_INDEX.slippage_bps + CFD_INDEX.regulatory_bps)


def post_fomc(symbol="ES", spike_min=5, hold_min=45, mode="fade"):
    df = C.to_eastern(C.load(symbol))
    fomc = pd.to_datetime(FOMC).tz_localize("US/Eastern")
    rets = []
    for d in fomc:
        if d.year < 2012 or d > df.index.max():
            continue
        ann_h, ann_m = 14, 0
        day = df[df.index.normalize() == d.normalize()]
        if day.empty:
            continue
        base = d + pd.Timedelta(hours=ann_h, minutes=ann_m)
        spike_end = base + pd.Timedelta(minutes=spike_min)
        exit_t = base + pd.Timedelta(minutes=spike_min + hold_min)
        seg = day[(day.index >= base) & (day.index <= exit_t)]
        if len(seg) < spike_min + 5:
            continue
        p0 = seg["Open"].iloc[0]
        p_spike = seg.loc[seg.index <= spike_end, "Close"].iloc[-1]
        spike = (p_spike - p0) / p0
        if abs(spike) < 1e-4:
            continue
        entry = seg.loc[seg.index > spike_end, "Open"].iloc[0]
        exit_px = seg["Close"].iloc[-1]
        direction = -np.sign(spike) if mode == "fade" else np.sign(spike)
        rets.append(direction * (exit_px - entry) / entry)
    s = C.summarize(f"FOMC {mode}", np.array(rets), COST_RT)
    print(f"  {symbol} FOMC {mode:12s} spike={spike_min}m hold={hold_min}m: "
          f"n={s['n']:3d} gross={s['gross_bps']:8.2f}bps gS={s['gross_sharpe']:.3f} "
          f"net={s['net_bps']:8.2f}bps win={s['win']:.3f}")
    return s


if __name__ == "__main__":
    print("=== I0074 post-FOMC fade/continuation (ES 1-min, 2012+) ===")
    for mode in ("fade", "continuation"):
        for hold in (30, 60, 120):
            post_fomc("ES", spike_min=5, hold_min=hold, mode=mode)
