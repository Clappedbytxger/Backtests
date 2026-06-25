"""Quant-OS Attribution API — the Attribution Desk backend.

Mounted under ``/api/attribution`` by :mod:`apps.api.main`. Decomposes the live book's
returns (:mod:`quantlab.risk_book`) into skill vs. market with the attribution engine
(:mod:`quantlab.attribution`):

* ``/book``    — selectable sleeves (with a derived asset-class sector), benchmark
                 options and the window presets
* ``/factors`` — per-strategy α/β factor regression + the portfolio point (scatter)
* ``/rolling`` — rolling α/β time series for one sleeve or the portfolio, with the
                 benchmark drawdown overlaid (line chart)
* ``/brinson`` — Brinson-Fachler allocation/selection/interaction across sectors,
                 benchmarked to passive asset-class ETFs (waterfall)

Benchmark series come from yfinance (cached). Every endpoint degrades to
``{"ok": false, "error": ...}`` and floats are NaN/Inf-sanitised.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from quantlab import attribution as at
from quantlab import risk_book
from quantlab.data import get_prices

router = APIRouter(prefix="/api/attribution", tags=["attribution"])

_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 1800.0
_BOOK_CACHE: dict = {"ts": 0.0, "panel": None, "meta": None}
_BOOK_TTL = 300.0

# Regression benchmark options offered in the UI.
BENCHMARKS = [
    {"key": "SPY", "label": "S&P 500 (SPY)"},
    {"key": "QQQ", "label": "Nasdaq-100 (QQQ)"},
    {"key": "BTC-USD", "label": "Bitcoin (BTC)"},
    {"key": "TLT", "label": "20Y Treasuries (TLT)"},
]

WINDOWS = [
    {"key": "252", "days": 252, "label": "1 Jahr"},
    {"key": "756", "days": 756, "label": "3 Jahre"},
    {"key": "1260", "days": 1260, "label": "5 Jahre"},
    {"key": "full", "days": None, "label": "Gesamt"},
]

# Asset-class sector inference (keyword → sector) and each sector's passive benchmark.
_SECTOR_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("energy", ("benzin", "gas", "öl", "oel", "oil", "crude", "heizöl", "rbob", "wti", "brent", "charter")),
    ("metal", ("platin", "gold", "silber", "silver", "zink", "zinc", "kupfer", "copper", "palladium", "platinum", "metal")),
    ("agriculture", ("mais", "corn", "weizen", "wheat", "soy", "soja", "getreide", "grain", "rind", "cattle", "vieh", "hog", "lean", "mastrind", "feeder")),
    ("rates", ("treasury", "bond", "t-note", "auction", "fomc", "eom", "duration", "zins", "rate")),
    ("crypto", ("btc", "eth", "crypto", "bitcoin", "krypto")),
    ("equity", ("aktien", "s&p", "equity", "stock", "index", "nasdaq")),
]
_SECTOR_BENCHMARK = {
    "energy": "USO", "metal": "GLD", "agriculture": "DBA",
    "rates": "TLT", "crypto": "BTC-USD", "equity": "SPY", "other": None,
}
_SECTOR_LABEL = {
    "energy": "Energie", "metal": "Metalle", "agriculture": "Agrar",
    "rates": "Zinsen", "crypto": "Krypto", "equity": "Aktien", "other": "Sonstige",
}


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _infer_sector(name: str, category: str | None) -> str:
    hay = f"{name} {category or ''}".lower()
    for sector, kws in _SECTOR_RULES:
        if any(k in hay for k in kws):
            return sector
    return "other"


def _load_book() -> tuple[pd.DataFrame, list[dict]]:
    now = time.time()
    if _BOOK_CACHE["panel"] is not None and now - _BOOK_CACHE["ts"] < _BOOK_TTL:
        return _BOOK_CACHE["panel"], _BOOK_CACHE["meta"]
    panel, meta = risk_book.load_strategy_returns()
    for m in meta:
        m["sector"] = _infer_sector(m.get("name") or m["label"], m.get("category"))
    _BOOK_CACHE.update(ts=now, panel=panel, meta=meta)
    return panel, meta


def _benchmark_returns(ticker: str) -> pd.Series:
    """Daily simple returns of a benchmark ticker (cached)."""
    key = f"bench:{ticker}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    px = get_prices(ticker, start="1993-01-01")
    ret = px["Close"].astype(float).pct_change().dropna()
    ret.index = ret.index.normalize()
    _CACHE[key] = (now, ret)
    return ret


def _window_days(window: str) -> int | None:
    if window in (None, "", "full", "0"):
        return None
    try:
        return int(window)
    except ValueError:
        return None


def _slice(s: pd.DataFrame | pd.Series, days: int | None):
    return s if days is None else s.iloc[-days:]


def _portfolio_returns(panel: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Equal-weight daily return of the selected sleeves (skip pre/post-life NaNs)."""
    sub = panel[cols]
    return sub.mean(axis=1, skipna=True).dropna()


# ── endpoints ────────────────────────────────────────────────────────────────


@router.get("/book")
def book() -> dict:
    try:
        panel, meta = _load_book()
        return _sanitize({
            "ok": True, "count": len(meta), "strategies": meta,
            "default_selection": [m["num"] for m in meta],
            "benchmarks": BENCHMARKS, "windows": WINDOWS,
            "sectors": {k: _SECTOR_LABEL[k] for k in _SECTOR_LABEL},
            "span": {"start": panel.index.min().strftime("%Y-%m-%d") if len(panel) else None,
                     "end": panel.index.max().strftime("%Y-%m-%d") if len(panel) else None},
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/factors")
def factors(
    benchmark: str = Query("SPY"),
    window: str = Query("full"),
    nums: str | None = Query(None),
) -> dict:
    """Per-strategy α/β regression + the equal-weight portfolio point (scatter data)."""
    key = f"factors:{benchmark}:{window}:{nums}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        panel, meta = _load_book()
        if panel.empty:
            return {"ok": False, "error": "no strategies with a parseable trade log"}
        bench = _benchmark_returns(benchmark)
        days = _window_days(window)
        wanted = {n.strip() for n in nums.split(",")} if nums else None
        meta_by_col = {m["label"]: m for m in meta}

        points = []
        for col in panel.columns:
            m = meta_by_col.get(col)
            if m is None or (wanted is not None and m["num"] not in wanted):
                continue
            sret = _slice(panel[col].dropna(), days)
            if len(sret) < 30:
                continue
            try:
                fr = at.factor_regression(sret, bench)
            except ValueError:
                continue
            points.append({
                "num": m["num"], "label": m["label"], "name": m["name"],
                "sector": m["sector"], "category": m.get("category"),
                "beta": fr.beta, "alpha_annual": fr.alpha_annual,
                "t_alpha": fr.t_alpha, "p_alpha": fr.p_alpha,
                "r_squared": fr.r_squared, "n": fr.n,
                "quadrant": at.classify_quadrant(fr.alpha_annual, fr.beta),
            })

        # equal-weight portfolio
        sel_cols = [c for c in panel.columns
                    if (wanted is None or meta_by_col.get(c, {}).get("num") in wanted)]
        port = _slice(_portfolio_returns(panel, sel_cols), days)
        portfolio = None
        if len(port) >= 30:
            pf = at.factor_regression(port, bench)
            portfolio = {
                "beta": pf.beta, "alpha_annual": pf.alpha_annual,
                "t_alpha": pf.t_alpha, "p_alpha": pf.p_alpha,
                "r_squared": pf.r_squared, "n": pf.n,
                "quadrant": at.classify_quadrant(pf.alpha_annual, pf.beta),
            }

        out = _sanitize({"ok": True, "benchmark": benchmark, "window": window,
                         "points": points, "portfolio": portfolio})
        _CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/rolling")
def rolling(
    num: str = Query("PORTFOLIO"),
    benchmark: str = Query("SPY"),
    roll_window: int = Query(63, ge=20, le=504),
) -> dict:
    """Rolling α/β for one sleeve (or PORTFOLIO) with the benchmark drawdown overlay."""
    key = f"rolling:{num}:{benchmark}:{roll_window}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        panel, meta = _load_book()
        if panel.empty:
            return {"ok": False, "error": "empty book"}
        bench = _benchmark_returns(benchmark)
        if num.upper() == "PORTFOLIO":
            sret = _portfolio_returns(panel, list(panel.columns))
            label = "Portfolio (Equal Weight)"
        else:
            col = next((m["label"] for m in meta if m["num"] == num), None)
            if col is None:
                return {"ok": False, "error": f"unknown strategy {num}"}
            sret = panel[col].dropna()
            label = col

        roll = at.rolling_factor(sret, bench, window=roll_window).dropna()
        if roll.empty:
            return {"ok": False, "error": "not enough overlap for a rolling window"}

        # benchmark drawdown over the same dates → shows where crashes are
        b = bench.reindex(roll.index).fillna(0.0)
        eq = (1.0 + b).cumprod()
        dd = (eq / eq.cummax() - 1.0)

        # downsample to ~400 points
        idx = (np.linspace(0, len(roll) - 1, 400).astype(int) if len(roll) > 400
               else range(len(roll)))
        series = [{"t": str(roll.index[i].date()),
                   "beta": round(float(roll["beta"].iloc[i]), 4),
                   "alpha": round(float(roll["alpha_annual"].iloc[i]), 5),
                   "bench_dd": round(float(dd.iloc[i]), 4)} for i in idx]

        out = _sanitize({"ok": True, "num": num, "label": label, "benchmark": benchmark,
                         "roll_window": roll_window, "series": series})
        _CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _total_return(returns: pd.Series) -> float:
    return float((1.0 + returns).prod() - 1.0)


@router.get("/brinson")
def brinson(window: str = Query("252")) -> dict:
    """Brinson-Fachler decomposition: our book by sector vs. passive asset-class ETFs.

    Sectors = inferred asset classes of the sleeves. Portfolio sector return = the
    equal-weight combo of our sleeves in that sector; benchmark sector return = the
    passive ETF; benchmark weights = equal across sectors (the naive policy). The
    waterfall builds Benchmark → +Allocation → +Selection → +Interaction → Portfolio.
    """
    key = f"brinson:{window}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        panel, meta = _load_book()
        if panel.empty:
            return {"ok": False, "error": "empty book"}
        days = _window_days(window) or 252
        meta_by_col = {m["label"]: m for m in meta}

        # group sleeves by sector
        sectors: dict[str, list[str]] = {}
        for col in panel.columns:
            m = meta_by_col.get(col)
            if m:
                sectors.setdefault(m["sector"], []).append(col)

        wp, rp, wb, rb = {}, {}, {}, {}
        diag = []
        n_sectors_with_bm = sum(1 for s in sectors if _SECTOR_BENCHMARK.get(s))
        for sector, cols in sectors.items():
            sret = _slice(_portfolio_returns(panel, cols), days)
            if sret.empty:
                continue
            r_p = _total_return(sret)
            # portfolio weight = capital share = sleeve count (equal-weight book)
            wp[sector] = len(cols)
            rp[sector] = r_p

            bm = _SECTOR_BENCHMARK.get(sector)
            if bm:
                bret = _slice(_benchmark_returns(bm).reindex(sret.index).dropna(), None)
                r_b = _total_return(bret) if not bret.empty else 0.0
            else:
                r_b = 0.0  # "other" → cash benchmark
            rb[sector] = r_b
            wb[sector] = 1.0  # equal policy weight across sectors
            diag.append({"sector": sector, "label": _SECTOR_LABEL.get(sector, sector),
                         "benchmark": bm or "cash", "n_sleeves": len(cols)})

        if not wp:
            return {"ok": False, "error": "no sectors to attribute"}

        res = at.brinson_fachler(wp, rp, wb, rb)
        d = res.as_dict()
        # attach labels + benchmark tickers to each sector row
        label_by_sec = {x["sector"]: x for x in diag}
        for srow in d["sectors"]:
            info = label_by_sec.get(srow["sector"], {})
            srow["label"] = info.get("label", srow["sector"])
            srow["benchmark"] = info.get("benchmark")
            srow["n_sleeves"] = info.get("n_sleeves")

        out = _sanitize({"ok": True, "window": window, "n_sectors": len(wp),
                         "n_sectors_with_benchmark": n_sectors_with_bm, **d})
        _CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
