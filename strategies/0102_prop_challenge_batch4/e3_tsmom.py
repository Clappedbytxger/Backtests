"""I0077 - Cross-asset daily time-series momentum (CFD basket), dual-sleeve, vol-scaled.

Port of the century-evidence TSMOM family (#s04) onto a diversified CTI CFD basket.
The edge IS the diversification across ~11 decorrelated assets (the smoothing the
5% trailing needs); a single leg is weak.

  Signal (weekly, Friday close):
    S = 0.5*sign(C[t]-C[t-50]) + 0.5*sign(C[t]-C[t-200])  in {-1,-0.5,0,0.5,1}
  Vol scaling: w_i = S_i * (10% / sigma_i),  sigma_i = ann. 40d realized vol.
  Book scaled to 6% annual vol (scale-invariant for Sharpe; affects CAGR/MaxDD only).
  Exit = signal flip at next rebalance. Held positions pay overnight swap.

Cost: per-instrument spread on rebalance turnover + overnight swap on gross exposure.

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/e3_tsmom.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# instrument -> (yfinance ticker, asset class for cost)
UNIVERSE = {
    "US500": ("^GSPC", "index"), "NAS100": ("^NDX", "index"),
    "GER40": ("^GDAXI", "index"), "JP225": ("^N225", "index"),
    "Gold": ("GC=F", "gold"), "Silver": ("SI=F", "gold"), "Oil": ("CL=F", "gold"),
    "EURUSD": ("EURUSD=X", "fx"), "GBPUSD": ("GBPUSD=X", "fx"),
    "USDJPY": ("USDJPY=X", "fx"), "AUDUSD": ("AUDUSD=X", "fx"),
}
VOL_TARGET_LEG = 0.10
BOOK_VOL = 0.06
SPREAD_SIDE = {k: C.SPREAD_RT[v] / 2.0 / 1e4 for k, v in
               {"index": "index", "gold": "gold", "fx": "fx"}.items()}


def build_panel() -> tuple[pd.DataFrame, dict]:
    closes = {}
    klass = {}
    for name, (tk, cls) in UNIVERSE.items():
        try:
            closes[name] = get_prices(tk, start="2003-01-01")["Close"]
            klass[name] = cls
        except Exception as e:
            print(f"skip {name}: {e}")
    px = pd.DataFrame(closes).sort_index()
    px = px.ffill(limit=3)
    return px, klass


def signals(px: pd.DataFrame) -> pd.DataFrame:
    fast = np.sign(px - px.shift(50))
    slow = np.sign(px - px.shift(200))
    return 0.5 * fast + 0.5 * slow


def main() -> None:
    px, klass = build_panel()
    rets = px.pct_change()
    sig = signals(px)
    sigma = rets.rolling(40).std() * np.sqrt(252)
    raw_w = sig * (VOL_TARGET_LEG / sigma)
    raw_w = raw_w.replace([np.inf, -np.inf], np.nan)

    # weekly rebalance: take weights on Fridays, hold (shifted +1 day for execution)
    is_friday = px.index.weekday == 4
    w_weekly = raw_w.where(pd.Series(is_friday, index=px.index), other=np.nan).ffill()
    w_held = w_weekly.shift(1)  # decision Friday close -> applied next session

    valid = w_held.notna().any(axis=1)
    w_held = w_held[valid].fillna(0.0)
    r = rets.reindex(w_held.index).fillna(0.0)

    # gross portfolio return
    gross = (w_held * r).sum(axis=1)

    # costs: turnover spread at rebalance + nightly swap on gross exposure
    dw = w_held.diff().abs().fillna(w_held.abs())
    spread_cost = pd.Series(0.0, index=w_held.index)
    swap_cost = pd.Series(0.0, index=w_held.index)
    for name in w_held.columns:
        cls = klass[name]
        spread_cost += dw[name] * SPREAD_SIDE[cls]
        swap_cost += w_held[name].abs() * (C.SWAP_PER_NIGHT[cls] / 1e4)
    net = gross - spread_cost - swap_cost

    # scale to 6% annual vol (ex-post; scale-invariant for Sharpe)
    realized_vol = net.std() * np.sqrt(252)
    k = BOOK_VOL / realized_vol if realized_vol > 0 else 1.0
    net_scaled = net * k
    gross_scaled = gross * k

    out = {"idea": "I0077", "name": "Cross-asset daily TSMOM (dual-sleeve, vol-scaled)"}
    m_net = compute_metrics(net_scaled)
    m_gross = compute_metrics(gross_scaled)

    # per-leg standalone Sharpe (value is aggregation)
    leg_sharpes = {}
    for name in w_held.columns:
        leg = (w_held[name].shift(0) * r[name])
        leg_sharpes[name] = round(C.ann_sharpe(leg), 3)

    # crisis behavior: 2008, 2020, 2022 yearly net
    yearly = net_scaled.groupby(net_scaled.index.year).apply(lambda s: float((1 + s).prod() - 1))

    out["book"] = {
        "period": f"{net_scaled.index.min().date()}..{net_scaled.index.max().date()}",
        "net_sharpe": round(m_net["sharpe"], 3),
        "gross_sharpe": round(m_gross["sharpe"], 3),
        "net_cagr": round(m_net["cagr"], 4),
        "net_maxdd": round(m_net["max_drawdown"], 4),
        "net_calmar": round(m_net["calmar"], 3),
        "ann_turnover_cost_bps": round(float((spread_cost + swap_cost).mean() * 252 * 1e4), 1),
        "avg_leg_sharpe": round(float(np.mean(list(leg_sharpes.values()))), 3),
    }
    out["leg_sharpes"] = leg_sharpes
    out["crisis_years_net"] = {str(int(y)): round(float(v), 4)
                               for y, v in yearly.items() if int(y) in (2008, 2018, 2020, 2022)}
    # cost breakdown + realistic gross leverage at 6% book vol
    out["cost_breakdown"] = {
        "spread_ann_bps_unscaled": round(float(spread_cost.mean() * 252 * 1e4), 1),
        "swap_ann_bps_unscaled": round(float(swap_cost.mean() * 252 * 1e4), 1),
        "book_scale_k": round(float(k), 4),
        "swap_ann_bps_scaled_to_6pct": round(float(swap_cost.mean() * 252 * 1e4 * k), 1),
        "gross_leverage_scaled": round(float(w_held.abs().sum(axis=1).mean() * k), 2),
    }
    print("=== I0077 Cross-asset TSMOM (faithful: weekly, dual-sleeve) ===")
    print(json.dumps(out["book"], indent=2))
    print("leg sharpes:", out["leg_sharpes"])
    print("crisis years (net):", out["crisis_years_net"])
    print("cost breakdown:", json.dumps(out["cost_breakdown"], indent=2))

    # ── Stage-1 check (reject-not-final): does the trend edge exist at all? ──
    # Cleaner classic TSMOM: 12m (252d) sign, MONTHLY rebalance, gross.
    s12 = np.sign(px - px.shift(252))
    w12 = (s12 * (VOL_TARGET_LEG / sigma)).replace([np.inf, -np.inf], np.nan)
    is_meend = px.index.to_series().groupby([px.index.year, px.index.month]).transform("max") == px.index.to_series()
    w_m = w12.where(pd.Series(is_meend.values, index=px.index), other=np.nan).ffill().shift(1)
    vm = w_m.notna().any(axis=1)
    w_m = w_m[vm].fillna(0.0)
    rm = rets.reindex(w_m.index).fillna(0.0)
    gross_m = (w_m * rm).sum(axis=1)
    dwm = w_m.diff().abs().fillna(w_m.abs())
    spread_m = sum(dwm[n] * SPREAD_SIDE[klass[n]] for n in w_m.columns)
    swap_m = sum(w_m[n].abs() * (C.SWAP_PER_NIGHT[klass[n]] / 1e4) for n in w_m.columns)
    net_m = gross_m - spread_m - swap_m
    out["stage1_classic_monthly_12m"] = {
        "gross_sharpe": round(C.ann_sharpe(gross_m), 3),
        "net_sharpe": round(C.ann_sharpe(net_m), 3),
        "swap_ann_bps_unscaled": round(float(swap_m.mean() * 252 * 1e4), 1),
    }
    print("Stage-1 classic (12m, monthly):", out["stage1_classic_monthly_12m"])
    (RESULTS / "e3_tsmom.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
