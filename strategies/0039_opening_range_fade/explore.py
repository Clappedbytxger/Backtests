"""Exploration: opening-range fade vs continuation on ES 1-minute (go/no-go).

Framework hypothesis #1 (highest priority). Before writing the full report we
need the cost gate: does fading (or following) the first opening-range breakout
have a gross edge that clears the MES round-trip (~3 bps)?

RTH = 09:30-16:00 ET. Opening range (OR) = high/low of the first N minutes.
After the OR window, find the FIRST bar whose High >= OR_high (up-break) or
Low <= OR_low (down-break). Enter at the NEXT bar's open (look-ahead safe), exit
at the session close. Fade: short an up-break / long a down-break. Continuation:
the opposite. Flat overnight.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "futures" / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"

RT_COST = 0.0003  # MES intraday round-trip, conservative (3 bps)


def load_rth() -> pd.DataFrame:
    df = pd.read_parquet(CACHE).tz_convert("US/Eastern")
    t = df.index.time
    rth = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    df = df[rth].copy()
    df["date"] = df.index.normalize()
    df["minute"] = (df.index.hour - 9) * 60 + (df.index.minute - 30)  # 0 at 09:30
    return df


def opening_range_trades(df: pd.DataFrame, or_min: int, hold: int | None) -> pd.DataFrame:
    """One row per day: first OR breakout, fade return at a fixed holding horizon.

    ``hold`` = minutes held after entry; ``None`` = hold to session close.
    Return is signed as a FADE (short up-break / long down-break).
    """
    recs = []
    for day, g in df.groupby("date", sort=True):
        g = g.sort_index().reset_index(drop=False)
        orng = g[g["minute"] < or_min]
        post = g[g["minute"] >= or_min]
        if len(orng) < or_min * 0.5 or len(post) < 5:
            continue
        or_hi, or_lo = orng["High"].max(), orng["Low"].min()
        up = post["High"] >= or_hi
        dn = post["Low"] <= or_lo
        i_up = post.index[up.values][0] if up.any() else None
        i_dn = post.index[dn.values][0] if dn.any() else None
        if i_up is None and i_dn is None:
            continue
        if i_dn is None or (i_up is not None and i_up <= i_dn):
            brk_dir, brk_i = +1, i_up
        else:
            brk_dir, brk_i = -1, i_dn
        if brk_i + 1 >= len(g):  # need a next bar to enter on
            continue
        entry = g.loc[brk_i + 1, "Open"]
        if hold is None:
            exit_px = g["Close"].iloc[-1]
        else:
            exit_i = min(brk_i + 1 + hold, len(g) - 1)
            exit_px = g.loc[exit_i, "Close"]
        fade_dir = -brk_dir
        gross = fade_dir * (exit_px / entry - 1.0)
        recs.append({"date": day, "brk_dir": brk_dir, "gross": gross})
    return pd.DataFrame(recs).set_index("date")


def main() -> None:
    df = load_rth()
    print(f"RTH 1m bars: {len(df):,}  days: {df['date'].nunique():,}  "
          f"{df.index[0].date()} .. {df.index[-1].date()}\n")
    print("FADE = short up-break / long down-break. net = gross - 3 bps RT.\n")
    for or_min in [5, 15, 30]:
        for hold in [5, 15, 30, 60, None]:
            tr = opening_range_trades(df, or_min, hold)
            fade = tr["gross"]
            label = f"{hold}m" if hold else "close"
            print(f"OR={or_min:2d}min hold={label:5}  n={len(fade):4d}  "
                  f"FADE gross={fade.mean()*1e4:6.2f}bps net={ (fade.mean()-RT_COST)*1e4:6.2f}bps "
                  f"win={(fade>0).mean()*100:3.0f}%  | CONT net={(-fade.mean()-RT_COST)*1e4:6.2f}bps")
        print()


if __name__ == "__main__":
    main()
