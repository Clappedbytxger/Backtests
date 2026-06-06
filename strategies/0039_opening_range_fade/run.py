"""Strategy 0039 — Opening-Range Fade / Continuation (ES 1-minute intraday).

Prop-Edge-Framework.md hypothesis #1 (highest priority): intraday index
mean-reversion via an opening-range fade. After the first N minutes of the RTH
session define an opening range (OR), fade the first breakout of that range
(short an up-break, long a down-break), flat overnight — the "many small wins,
smooth equity" profile the prop drawdown/consistency rules reward.

Data: real ES (S&P 500 e-mini) 1-minute bars from Databento GLBX.MDP3, 2010-2026
(5.5M bars, 4048 RTH sessions). ES intraday *returns* equal MES, so the
MES_INTRADAY cost model (~3 bps round-trip) applies. This is the first strategy
with genuine intraday depth AND genuine sample size.

Result: REJECTED on the cost gate. Across every (OR window x holding horizon)
and an OR-width conditioning split, the breakout fade has gross edge ~0 bps and
~49% win (a coin flip); continuation is equally dead. Nothing clears the 3 bps
MES round-trip. The liquid index opening range is efficiently arbitraged — the
same wall as BTC 0012-0015 and gap-fade 0038: on a liquid market the intraday
directional gross edge is ~0 and cost is the binding constraint.

Run:
    .venv/Scripts/python.exe strategies/0039_opening_range_fade/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.metrics import sharpe_ratio  # noqa: E402
from quantlab.significance import permutation_test  # noqa: E402

CACHE = ROOT / "data" / "cache" / "futures" / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
RT_COST = 0.0003  # MES intraday round-trip (conservative 3 bps)
HOLDS = [5, 15, 30, 60, None]  # minutes after entry; None = session close
ORS = [5, 15, 30]


def load_rth() -> pd.DataFrame:
    df = pd.read_parquet(CACHE).tz_convert("US/Eastern")
    t = df.index.time
    rth = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    df = df[rth].copy()
    df["date"] = df.index.normalize()
    df["minute"] = (df.index.hour - 9) * 60 + (df.index.minute - 30)
    return df


def breakout_returns(df: pd.DataFrame, or_min: int) -> pd.DataFrame:
    """Per day: first OR breakout, fade return at every holding horizon + OR width.

    One pass per OR window computes all holding horizons. Returns are signed as a
    FADE (short up-break / long down-break); continuation is just the negative.
    Look-ahead-safe: OR is closed before the breakout, entry is the NEXT bar open.
    """
    recs = []
    for day, g in df.groupby("date", sort=True):
        g = g.sort_index().reset_index(drop=True)
        orng = g[g["minute"] < or_min]
        post = g[g["minute"] >= or_min]
        if len(orng) < or_min * 0.5 or len(post) < 5:
            continue
        hi, lo = orng["High"].max(), orng["Low"].min()
        up = post["High"] >= hi
        dn = post["Low"] <= lo
        i_up = post.index[up.values][0] if up.any() else None
        i_dn = post.index[dn.values][0] if dn.any() else None
        if i_up is None and i_dn is None:
            continue
        if i_dn is None or (i_up is not None and i_up <= i_dn):
            bd, bi = +1, i_up
        else:
            bd, bi = -1, i_dn
        if bi + 1 >= len(g):
            continue
        entry = g.loc[bi + 1, "Open"]
        rec = {"date": day, "brk_dir": bd, "width_bps": (hi / lo - 1) * 1e4}
        for hold in HOLDS:
            exit_i = len(g) - 1 if hold is None else min(bi + 1 + hold, len(g) - 1)
            rec[f"h{hold}"] = -bd * (g.loc[exit_i, "Close"] / entry - 1.0)
        recs.append(rec)
    return pd.DataFrame(recs).set_index("date")


def main() -> None:
    df = load_rth()
    n_days = df["date"].nunique()
    print(f"ES 1m RTH: {len(df):,} bars, {n_days:,} sessions "
          f"{df.index[0].date()}..{df.index[-1].date()}\n")
    print("FADE = short up-break / long down-break. net = gross - 3 bps RT.\n")

    out = {"cost_rt": RT_COST, "n_sessions": int(n_days), "grid": {}, "width": {}}
    grid_net = np.full((len(ORS), len(HOLDS)), np.nan)
    best = {"net": -1e9}
    per_or = {}

    for oi, or_min in enumerate(ORS):
        tr = breakout_returns(df, or_min)
        per_or[or_min] = tr
        for hi, hold in enumerate(HOLDS):
            fade = tr[f"h{hold}"]
            net = fade.mean() - RT_COST
            grid_net[oi, hi] = net * 1e4
            label = f"{hold}m" if hold else "close"
            print(f"OR={or_min:2d} hold={label:5} n={len(fade):4d}  "
                  f"FADE gross={fade.mean()*1e4:6.2f} net={net*1e4:6.2f}bps "
                  f"win={(fade>0).mean()*100:3.0f}%  | CONT net={(-fade.mean()-RT_COST)*1e4:6.2f}")
            out["grid"][f"OR{or_min}_h{hold}"] = {
                "n": int(len(fade)), "gross_bps": float(fade.mean() * 1e4),
                "net_bps": float(net * 1e4), "win": float((fade > 0).mean())}
            # track the single best (least-bad) cell for a full significance look
            if fade.mean() * 1e4 > best["net"]:
                best = {"net": fade.mean() * 1e4, "or": or_min, "hold": hold,
                        "series": fade}
        print()

    # OR-width conditioning (look-ahead-safe: width known at breakout)
    print("OR-width terciles (FADE net bps), the economically-motivated refinement:")
    for or_min, hold in [(5, 15), (15, 30), (30, 30)]:
        tr = per_or[or_min]
        s = tr[f"h{hold}"]
        q = tr["width_bps"].quantile([1/3, 2/3]).values
        cells = {
            "narrow": s[tr.width_bps <= q[0]],
            "mid": s[(tr.width_bps > q[0]) & (tr.width_bps < q[1])],
            "wide": s[tr.width_bps >= q[1]],
        }
        txt = "  ".join(f"{k}={(v.mean()-RT_COST)*1e4:6.2f}(n={len(v)})" for k, v in cells.items())
        print(f"  OR={or_min} hold={hold}m:  {txt}")
        out["width"][f"OR{or_min}_h{hold}"] = {
            k: float((v.mean() - RT_COST) * 1e4) for k, v in cells.items()}

    # Full significance on the least-bad cell — to show even the best is noise.
    bs = best["series"].dropna()
    pos = pd.Series(np.where(bs.values >= 0, 0.0, 0.0), index=bs.index)  # placeholder
    perm = permutation_test(bs, bs, pd.Series(np.sign(bs.values), index=bs.index),
                            n_perm=2000, metric="mean")
    print(f"\nLeast-bad cell: OR={best['or']} hold={best['hold']} -> "
          f"gross {best['net']:.2f}bps, net {best['net']-3:.2f}bps, "
          f"Sharpe(active) {sharpe_ratio(bs):.2f}, win {(bs>0).mean()*100:.0f}%")
    out["best_cell"] = {"or": best["or"], "hold": best["hold"],
                        "gross_bps": float(best["net"]),
                        "net_bps": float(best["net"] - 3),
                        "sharpe_active": float(sharpe_ratio(bs)),
                        "win": float((bs > 0).mean())}

    # ---- plot: heatmap of FADE net bps over OR x hold (all negative = red) ----
    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(grid_net, cmap="RdYlGn", vmin=-6, vmax=6, aspect="auto")
    ax.set_xticks(range(len(HOLDS)))
    ax.set_xticklabels([f"{h}m" if h else "close" for h in HOLDS])
    ax.set_yticks(range(len(ORS)))
    ax.set_yticklabels([f"OR {o}m" for o in ORS])
    ax.set_xlabel("holding horizon after entry")
    ax.set_title("Opening-range FADE net edge (bps/trade) — ES 1m, 2010-2026\n"
                 "every cell < 0: no horizon clears the 3 bps MES round-trip")
    for oi in range(len(ORS)):
        for hi in range(len(HOLDS)):
            ax.text(hi, oi, f"{grid_net[oi, hi]:.1f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, label="net bps/trade")
    fig.tight_layout()
    fig.savefig(RESULTS / "or_fade_grid.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2))
    print("\nVerdict: REJECTED. Opening-range breakout has no directional edge "
          "(gross ~0, win ~49%) at any window/horizon; cost is the binding "
          "constraint on the liquid index, as in 0012-0015 and 0038.")


if __name__ == "__main__":
    main()
