"""Quick pre-test for 0049 Market Intraday Momentum (Gao/Han/Li/Zhou 2018).

Before writing the full report: is there ANY predictive relation between the
first half-hour return (and the overnight gap) and the LAST half-hour return on
ES 2010-2026? If beta ~0 (as our own 0040/0041 found autocorr ~0), the strategy
is dead on arrival and we stop. If beta > 0, build the full battery.

Decision-time check: the first-30m signal is known at 10:00 ET; the trade is the
last 30m (15:30-16:00). No look-ahead. The 12th-half-hour (15:00-15:30) signal is
known at 15:30, trade 15:30-16:00 — also clean.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
ES_1M = ROOT / "data" / "cache" / "futures" / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
ANN = np.sqrt(252)


def load_es_rth() -> pd.DataFrame:
    df = pd.read_parquet(ES_1M).tz_convert("US/Eastern")
    t = df.index.time
    rth = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    df = df[rth].copy()
    df["date"] = df.index.normalize()
    df["m"] = (df.index.hour - 9) * 60 + (df.index.minute - 30)  # 0..389
    return df


def win(g: pd.DataFrame, a: int, b: int) -> float:
    """Return open(minute a) -> close(minute b)."""
    sa = g.loc[g.m == a, "Open"]
    sb = g.loc[g.m == b, "Close"]
    if sa.empty or sb.empty:
        return np.nan
    return sb.iloc[0] / sa.iloc[0] - 1.0


def main() -> None:
    df = load_es_rth()
    g = df.groupby("date")
    first30 = g.apply(lambda x: win(x, 0, 29)).rename("first30")          # 09:30-10:00
    last30 = g.apply(lambda x: win(x, 360, 389)).rename("last30")          # 15:30-16:00
    h12 = g.apply(lambda x: win(x, 330, 359)).rename("h12")                # 15:00-15:30
    opens = g.apply(lambda x: x.loc[x.m == 0, "Open"].iloc[0] if (x.m == 0).any() else np.nan).rename("open0930")
    closes = g.apply(lambda x: x.loc[x.m == 389, "Close"].iloc[0] if (x.m == 389).any() else np.nan).rename("close1600")
    d = pd.concat([first30, last30, h12, opens, closes], axis=1).dropna(subset=["first30", "last30"])
    # overnight gap = today's 09:30 open / yesterday's 16:00 close - 1
    d["overnight"] = d["open0930"] / d["close1600"].shift(1) - 1.0
    d["gap_plus_first30"] = (1 + d["overnight"]) * (1 + d["first30"]) - 1.0

    print(f"sessions: {len(d)}   ({d.index.min().date()} .. {d.index.max().date()})")
    print(f"last30  std = {d['last30'].std()*1e4:6.1f} bps   mean = {d['last30'].mean()*1e4:+5.2f} bps")
    print()
    for sig in ["first30", "overnight", "gap_plus_first30", "h12"]:
        sub = d[[sig, "last30"]].dropna()
        beta = np.polyfit(sub[sig], sub["last30"], 1)[0]
        corr = sub[sig].corr(sub["last30"])
        # sign strategy: position = sign(signal), pnl = pos * last30 (gross)
        pos = np.sign(sub[sig])
        pnl = pos * sub["last30"]
        sharpe = pnl.mean() / pnl.std() * ANN if pnl.std() else float("nan")
        net = (pnl.mean() - 0.0003) * 1e4
        print(f"{sig:18} beta={beta:+6.3f} corr={corr:+.3f}  "
              f"signGrossSharpe={sharpe:+5.2f} grossBps={pnl.mean()*1e4:+5.2f} "
              f"netBps={net:+5.2f} win={(pnl>0).mean()*100:4.1f}%")


if __name__ == "__main__":
    main()
