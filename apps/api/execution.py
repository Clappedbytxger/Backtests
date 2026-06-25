"""Quant-OS Execution API — the Execution Desk backend.

Mounted under ``/api/execution`` by :mod:`apps.api.main`. Drives the adaptive
slippage simulator (:mod:`quantlab.execution`) over a small demo universe of
strategy×asset pairs and exposes the post-trade Slippage Radar (Implementation
Shortfall ledger).

Endpoints:
* ``/universe``  — the demo strategy×asset pairs
* ``/simulate``  — theoretical vs. realised equity, cost breakdown, liquidity gauge
* ``/breakdown`` — slippage cost breakdown across the whole demo universe (bars)
* ``/radar``     — aggregated Implementation Shortfall from the live/paper ledger
* ``/seed``      — (POST) seed the ledger with realistic sample fills (demo)

Convention shared with the other desks: every endpoint degrades to
``{"ok": false, "error": ...}`` and floats are NaN/Inf-sanitised.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from quantlab import execution as ex
from quantlab.data import get_prices

router = APIRouter(prefix="/api/execution", tags=["execution"])

_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 1800.0
_LEDGER = ex.SlippageLedger()


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


# ── demo universe ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Demo:
    strategy: str
    ticker: str
    name: str
    kind: str       # "trend" | "meanrev"
    capital: float  # representative account size for this sleeve


DEMO_UNIVERSE: list[Demo] = [
    Demo("Trend Following", "SPY", "S&P 500 ETF", "trend", 5_000_000),
    Demo("Trend Following", "QQQ", "Nasdaq-100 ETF", "trend", 5_000_000),
    Demo("Trend Following", "EEM", "Emerging Markets", "trend", 4_000_000),
    Demo("Trend Following", "GLD", "Gold ETF", "trend", 4_000_000),
    Demo("Mean Reversion", "IWM", "Russell 2000 (Small Caps)", "meanrev", 3_000_000),
    Demo("Mean Reversion", "TLT", "20Y Treasury ETF", "meanrev", 3_000_000),
    Demo("Trend Following", "PPLT", "Platinum ETF (thin)", "trend", 6_000_000),
]
DEMO_BY_KEY = {f"{d.strategy}|{d.ticker}": d for d in DEMO_UNIVERSE}


def _signal(prices: pd.DataFrame, kind: str) -> pd.Series:
    """Build a simple long/flat demo signal (decision-time, look-ahead-safe)."""
    close = prices["Close"].astype(float)
    if kind == "meanrev":
        # RSI(2) mean reversion: long when deeply oversold, exit above midline.
        delta = close.diff()
        up = delta.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
        dn = (-delta).clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
        rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        sig = pd.Series(np.nan, index=close.index)
        sig[rsi < 10] = 1.0
        sig[rsi > 50] = 0.0
        return sig.ffill().fillna(0.0)
    # trend: SMA(50/200) crossover, long/flat
    return (close.rolling(50).mean() > close.rolling(200).mean()).astype(float)


def _load(ticker: str) -> pd.DataFrame:
    return get_prices(ticker, start="2012-01-01")


def _simulate(d: Demo, capital: float | None, impact_y: float) -> dict:
    prices = _load(d.ticker)
    signal = _signal(prices, d.kind)
    model = ex.SlippageModel(impact_y=impact_y)
    cap = capital or d.capital
    res = ex.run_adaptive_backtest(prices, signal, capital=cap, model=model)

    # liquidity gauge: a full position entry (one side) vs. latest dollar ADV
    adv = ex.dollar_adv(prices, model.adv_window)
    last_adv = float(adv.dropna().iloc[-1]) if adv.notna().any() else 0.0
    gauge = ex.liquidity_gauge(order_notional=cap, dollar_adv_value=last_adv)

    return {"prices": prices, "res": res, "gauge": gauge, "capital": cap}


def _downsample(s: pd.Series, n: int = 320) -> list[dict]:
    if len(s) <= n:
        idx = range(len(s))
    else:
        idx = np.linspace(0, len(s) - 1, n).astype(int)
    return [{"t": str(s.index[i].date()), "v": round(float(s.iloc[i]), 6)} for i in idx]


# ── endpoints ────────────────────────────────────────────────────────────────


@router.get("/universe")
def universe() -> dict:
    return {"ok": True, "count": len(DEMO_UNIVERSE),
            "items": [{"key": f"{d.strategy}|{d.ticker}", "strategy": d.strategy,
                       "ticker": d.ticker, "name": d.name, "kind": d.kind,
                       "capital": d.capital} for d in DEMO_UNIVERSE]}


@router.get("/simulate")
def simulate(
    strategy: str = Query("Trend Following"),
    ticker: str = Query("SPY"),
    capital: float | None = Query(None, ge=0),
    impact_y: float = Query(0.5, ge=0.0, le=3.0),
) -> dict:
    key = f"{strategy}|{ticker}"
    d = DEMO_BY_KEY.get(key)
    if d is None:
        return {"ok": False, "error": f"unknown strategy/asset '{key}'"}
    cache_key = f"sim:{key}:{capital}:{impact_y}"
    now = time.time()
    hit = _CACHE.get(cache_key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        sim = _simulate(d, capital, impact_y)
        res, b = sim["res"], sim["res"]["breakdown"]
        # latency drag (from the live/paper ledger) folded in for this strategy
        agg = _LEDGER.aggregate()
        lat_bps = next((r["latency_bps"] for r in agg["by_strategy"]
                        if r["strategy"] == strategy), 0.0)

        out = _sanitize({
            "ok": True, "strategy": strategy, "ticker": ticker, "name": d.name,
            "kind": d.kind, "capital": sim["capital"], "impact_y": impact_y,
            "equity_theoretical": _downsample(res["equity_theoretical"]),
            "equity_realized": _downsample(res["equity_realized"]),
            "breakdown": {
                "gross_total_return": b["gross_total_return"],
                "net_total_return": b["net_total_return"],
                "spread": b["spread"], "impact": b["impact"], "commission": b["commission"],
                "latency_bps": lat_bps,
                "total_cost_return": b["total_cost_return"],
                "n_trades": b["n_trades"],
                "avg_participation": b["avg_participation"],
                "max_participation": b["max_participation"],
            },
            "gauge": sim["gauge"],
        })
        _CACHE[cache_key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/breakdown")
def breakdown(impact_y: float = Query(0.5, ge=0.0, le=3.0)) -> dict:
    """Slippage cost breakdown across the demo universe (one bar per sleeve)."""
    cache_key = f"breakdown:{impact_y}"
    now = time.time()
    hit = _CACHE.get(cache_key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    agg = _LEDGER.aggregate()
    lat_by_strat = {r["strategy"]: r["latency_bps"] for r in agg["by_strategy"]}
    rows = []
    for d in DEMO_UNIVERSE:
        try:
            sim = _simulate(d, d.capital, impact_y)
            b = sim["res"]["breakdown"]
            n = max(b["n_trades"], 1)
            # express each component as bps-per-trade (return_drag / n_trades)
            rows.append({
                "key": f"{d.strategy}|{d.ticker}", "strategy": d.strategy,
                "ticker": d.ticker, "name": d.name,
                "spread_bps": b["spread"]["return_drag"] / n * 1e4,
                "impact_bps": b["impact"]["return_drag"] / n * 1e4,
                "commission_bps": b["commission"]["return_drag"] / n * 1e4,
                "latency_bps": lat_by_strat.get(d.strategy, 0.0),
                "spread_pct": b["spread"]["pct_of_gross"],
                "impact_pct": b["impact"]["pct_of_gross"],
                "commission_pct": b["commission"]["pct_of_gross"],
                "gross_return": b["gross_total_return"],
                "net_return": b["net_total_return"],
                "n_trades": b["n_trades"],
                "max_participation": b["max_participation"],
                "gauge_zone": sim["gauge"]["zone"],
            })
        except Exception as e:  # noqa: BLE001
            rows.append({"key": f"{d.strategy}|{d.ticker}", "strategy": d.strategy,
                         "ticker": d.ticker, "name": d.name, "error": str(e)})
    out = _sanitize({"ok": True, "impact_y": impact_y, "rows": rows})
    _CACHE[cache_key] = (now, out)
    return out


@router.get("/radar")
def radar() -> dict:
    """Aggregated post-trade Implementation Shortfall from the ledger."""
    try:
        agg = _LEDGER.aggregate()
        return _sanitize({"ok": True, **agg, "ledger_path": str(_LEDGER.path)})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.post("/seed")
def seed(n_per_strategy: int = Query(60, ge=1, le=500)) -> dict:
    """Seed the ledger with realistic synthetic fills (demo data for the radar).

    Models small, side-correct slippage: a few bps of latency drift + execution
    slippage + a fixed commission, per fill, varying by strategy "speed".
    """
    try:
        rng = np.random.default_rng(42)
        # wipe any previous demo ledger so re-seeding is idempotent
        if _LEDGER.path.exists():
            _LEDGER.path.unlink()
        # mean-reversion fires fast/urgent (more latency+slippage); trend is patient
        profiles = {
            "Trend Following": {"lat": 1.0, "slip": 1.5, "lat_s": 1.2},
            "Mean Reversion": {"lat": 2.5, "slip": 3.0, "lat_s": 0.4},
        }
        total = 0
        for d in DEMO_UNIVERSE:
            p = profiles[d.strategy]
            for _ in range(n_per_strategy):
                side = int(rng.choice([1, -1]))
                px = float(rng.uniform(50, 400))
                # latency drift (bps) — usually adverse, occasionally favourable
                lat_bps = rng.normal(p["lat"], p["lat"] * 0.8)
                slip_bps = abs(rng.normal(p["slip"], p["slip"] * 0.5))
                arrival = px * (1 + side * lat_bps / 1e4)
                fill = arrival * (1 + side * slip_bps / 1e4)
                qty = rng.integers(200, 4000)
                t0 = pd.Timestamp("2026-06-01") + pd.Timedelta(minutes=int(rng.integers(0, 20000)))
                t1 = t0 + pd.Timedelta(seconds=float(abs(rng.normal(p["lat_s"], 0.3))))
                _LEDGER.log_fill(d.strategy, d.ticker, side, float(qty), px, arrival,
                                 fill, commission=float(qty) * 0.0035,
                                 signal_time=t0, fill_time=t1)
                total += 1
        _CACHE.clear()
        return _sanitize({"ok": True, "n_logged": total, **_LEDGER.aggregate()})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
