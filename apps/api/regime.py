"""Quant-OS Market Weather Radar API — live market-regime detection.

Mounted under ``/api/regime`` by :mod:`apps.api.main`. Wraps
:mod:`quantlab.regime` over the cached yfinance daily data. Endpoints:

* ``/palette``     — the canonical regime codes, labels, colors + descriptions
                     (single source of truth for the frontend "weather" theme)
* ``/universe``    — the basket of assets the radar can classify
* ``/current``     — latest-bar snapshot for one ticker (the radar widget)
* ``/timeline``    — price series + per-regime shaded spans (the timeline chart)
* ``/performance`` — break one asset's returns down by regime (soll-vs-ist matrix)
* ``/overview``    — current regime for the whole universe (the radar grid)

Heavy work (price downloads + classification) is TTL-cached in-process. Every
endpoint degrades to ``{"ok": false, "error": ...}`` — the dashboard convention.
"""

from __future__ import annotations

import time

import pandas as pd
from fastapi import APIRouter, Query

from quantlab import regime as rg
from quantlab.data import get_prices, get_close

router = APIRouter(prefix="/api/regime", tags=["regime"])

# A liquid cross-asset basket — one representative per "weather system".
UNIVERSE: list[dict] = [
    {"ticker": "SPY", "name": "S&P 500", "asset_class": "index", "use_vix": True},
    {"ticker": "QQQ", "name": "Nasdaq 100", "asset_class": "index", "use_vix": True},
    {"ticker": "IWM", "name": "Russell 2000", "asset_class": "index", "use_vix": True},
    {"ticker": "GLD", "name": "Gold", "asset_class": "commodity", "use_vix": False},
    {"ticker": "USO", "name": "Crude Oil", "asset_class": "commodity", "use_vix": False},
    {"ticker": "TLT", "name": "20Y Treasuries", "asset_class": "bond", "use_vix": False},
    {"ticker": "HYG", "name": "High Yield Credit", "asset_class": "bond", "use_vix": False},
    {"ticker": "UUP", "name": "US Dollar", "asset_class": "fx", "use_vix": False},
    {"ticker": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto", "use_vix": False},
    {"ticker": "ETH-USD", "name": "Ethereum", "asset_class": "crypto", "use_vix": False},
]
_UNIVERSE_BY_TICKER = {u["ticker"]: u for u in UNIVERSE}

# --- in-process caches ------------------------------------------------------
_CLS_CACHE: dict[str, tuple[float, pd.DataFrame, pd.DataFrame]] = {}
_CLS_TTL = 3 * 3600.0
_VIX_CACHE: dict[str, tuple[float, pd.Series]] = {}
_VIX_TTL = 3 * 3600.0


def _get_vix(start: str) -> pd.Series | None:
    now = time.time()
    hit = _VIX_CACHE.get(start)
    if hit and now - hit[0] < _VIX_TTL:
        return hit[1]
    try:
        vix = get_close("^VIX", start=start)
    except Exception:  # noqa: BLE001 - VIX is optional
        vix = None
    if vix is not None:
        _VIX_CACHE[start] = (now, vix)
    return vix


def _classify(ticker: str, years: int = 8) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (ohlc, classified) for a ticker, TTL-cached. Raises on no data."""
    key = f"{ticker}:{years}"
    now = time.time()
    hit = _CLS_CACHE.get(key)
    if hit and now - hit[0] < _CLS_TTL:
        return hit[1], hit[2]
    start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")
    df = get_prices(ticker, start=start)
    meta = _UNIVERSE_BY_TICKER.get(ticker, {})
    vix = _get_vix(start) if meta.get("use_vix") else None
    cls = rg.classify(df, vix=vix)
    _CLS_CACHE[key] = (now, df, cls)
    return df, cls


def _meta(ticker: str) -> dict:
    return _UNIVERSE_BY_TICKER.get(ticker, {"ticker": ticker, "name": ticker,
                                            "asset_class": "other", "use_vix": False})


# --------------------------------------------------------------- endpoints
@router.get("/palette")
def palette() -> dict:
    """Canonical regime codes/labels/colors/descriptions — the weather legend."""
    return {
        "ok": True,
        "regimes": [
            {"code": c, "label": rg.REGIME_LABELS[c], "color": rg.REGIME_COLORS[c],
             "description": rg.REGIME_DESCRIPTIONS[c]}
            for c in rg.REGIMES
        ],
        "directions": rg.DIRECTION_LABELS,
    }


@router.get("/universe")
def universe() -> dict:
    """The basket of assets the radar classifies."""
    return {"ok": True, "count": len(UNIVERSE), "universe": UNIVERSE}


@router.get("/current")
def current(ticker: str = Query("SPY"), years: int = Query(8, ge=2, le=30)) -> dict:
    """Latest-bar regime snapshot for one ticker (the radar widget)."""
    try:
        _, cls = _classify(ticker, years)
        snap = rg.current_regime(cls)
        dist = rg.regime_distribution(cls)
        return {"ok": True, "ticker": ticker, "meta": _meta(ticker),
                "snapshot": snap, "distribution": dist}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/timeline")
def timeline(ticker: str = Query("SPY"), years: int = Query(3, ge=1, le=30),
             max_points: int = Query(750, ge=100, le=4000)) -> dict:
    """Price series + per-regime shaded spans for the timeline chart.

    Returns ``price`` as ``[{t, close, ema_fast, sma_mid, sma_slow}]`` and
    ``segments`` as regime spans. ``price`` is down-sampled to ``max_points`` for
    a snappy chart while ``segments`` stay exact.
    """
    try:
        df, cls = _classify(ticker, max(years, 4))
        joined = cls.join(df[["Close"]])
        cutoff = pd.Timestamp.today() - pd.DateOffset(years=years)
        view = joined[joined.index >= cutoff]
        if view.empty:
            view = joined
        step = max(1, len(view) // max_points)
        sl = view.iloc[::step]
        price = [{
            "t": rg._isodate(ix),
            "close": _r(row.get("Close")),
            "ema_fast": _r(row.get("ema_fast")),
            "sma_mid": _r(row.get("sma_mid")),
            "sma_slow": _r(row.get("sma_slow")),
            "regime": (None if pd.isna(row.get("regime")) else str(row.get("regime"))),
        } for ix, row in sl.iterrows()]
        spans = rg.segments(view)
        return {"ok": True, "ticker": ticker, "meta": _meta(ticker),
                "price": price, "segments": spans,
                "palette": {c: rg.REGIME_COLORS[c] for c in rg.REGIMES}}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/performance")
def performance(ticker: str = Query("SPY"), years: int = Query(8, ge=2, le=30),
                strategy: str = Query("buy_hold")) -> dict:
    """Break an asset's returns down by regime (the performance matrix).

    ``strategy`` selects the return stream to slice:
      * ``buy_hold``    — the asset's own daily returns (the baseline radar);
      * ``long_trend``  — long only while the regime is trending (a toy overlay
                          that demonstrates regime-gating);
      * ``long_quiet``  — long only in the low-vol-range regime.
    This proves *in which regimes* a rule actually earns — the exact check the
    Alpha-Factory needs for its ``allowed_market_regimes`` claim.
    """
    try:
        df, cls = _classify(ticker, years)
        ret = df["Close"].pct_change().fillna(0.0)
        regs = cls["regime"]
        if strategy == "long_trend":
            gate = regs.isin(["high_vol_trend", "low_vol_trend"]).astype(float)
            stream = ret * gate.shift(1).fillna(0.0)
        elif strategy == "long_quiet":
            gate = (regs == "low_vol_range").astype(float)
            stream = ret * gate.shift(1).fillna(0.0)
        else:
            strategy = "buy_hold"
            stream = ret
        perf = rg.regime_performance(stream, cls)
        # overall line for the soll/ist header
        eq = (1.0 + stream).cumprod()
        overall = {
            "total_return": float(eq.iloc[-1] - 1.0) if len(eq) else 0.0,
            "sharpe": float(stream.mean() / stream.std() * (252 ** 0.5)) if stream.std() else 0.0,
            "n": int((stream != 0).sum()),
        }
        return {"ok": True, "ticker": ticker, "meta": _meta(ticker),
                "strategy": strategy, "by_regime": perf, "overall": overall,
                "order": list(rg.REGIMES)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/overview")
def overview(years: int = Query(8, ge=2, le=30)) -> dict:
    """Current regime for every asset in the universe (the radar grid)."""
    items = []
    for u in UNIVERSE:
        try:
            _, cls = _classify(u["ticker"], years)
            snap = rg.current_regime(cls)
            items.append({"ticker": u["ticker"], "name": u["name"],
                          "asset_class": u["asset_class"], "snapshot": snap})
        except Exception as e:  # noqa: BLE001 - one bad feed must not kill the grid
            items.append({"ticker": u["ticker"], "name": u["name"],
                          "asset_class": u["asset_class"], "snapshot": None,
                          "error": f"{type(e).__name__}: {e}"})
    return {"ok": True, "count": len(items), "items": items,
            "palette": {c: {"label": rg.REGIME_LABELS[c], "color": rg.REGIME_COLORS[c]}
                        for c in rg.REGIMES}}


# --------------------------------------------------------------- helpers
def _r(x, d: int = 4):
    try:
        v = float(x)
        return None if pd.isna(v) else round(v, d)
    except (TypeError, ValueError):
        return None
