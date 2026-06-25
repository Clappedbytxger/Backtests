"""Quant-OS Statistical-Arbitrage API — cointegration / pairs explorer.

Mounted under ``/api/pairs`` by :mod:`apps.api.main`. Wraps :mod:`quantlab.pairs`
over the cached yfinance daily data. Endpoints:

* ``/universe`` — curated asset groups the scanner can run over
* ``/scan``     — two-stage scan of a group → the "opportunity list" (sorted |z|)
* ``/pair``     — one pair's spread + rolling z-score history + entry/exit markers
* ``/heatmap``  — full cointegration matrix (1 − ADF p) for a group → clusters

Heavy work (downloads + ADF scans) is TTL-cached in-process. Every endpoint
degrades to ``{"ok": false, "error": ...}`` — the dashboard convention.
"""

from __future__ import annotations

import time
from dataclasses import asdict

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from quantlab import pairs as pr
from quantlab.data import get_multiple_closes

router = APIRouter(prefix="/api/pairs", tags=["pairs"])

# Curated asset groups (same-driver clusters where cointegration is plausible).
GROUPS: dict[str, dict] = {
    "famous": {"label": "Klassische Paare (Validierung)",
               "tickers": ["CVX", "XOM", "GLD", "SLV", "KO", "PEP", "HD", "LOW", "MA", "V", "EWA", "EWC"]},
    "energy": {"label": "Energie / Öl",
               "tickers": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY", "PSX", "VLO", "MPC"]},
    "commodities": {"label": "Rohstoffe (ETFs)",
                    "tickers": ["GLD", "SLV", "GDX", "GDXJ", "USO", "UNG", "DBA", "CPER", "PPLT", "PALL", "WEAT", "CORN"]},
    "tech": {"label": "Technologie",
             "tickers": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "ORCL", "CRM", "ADBE", "INTC"]},
    "banks": {"label": "Banken / Financials",
              "tickers": ["JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "SCHW"]},
    "etf_index": {"label": "Index- & Sektor-ETFs",
                  "tickers": ["SPY", "QQQ", "DIA", "IWM", "VTI", "XLK", "XLF", "XLE", "XLV", "XLI"]},
    "crypto": {"label": "Krypto",
               "tickers": ["BTC-USD", "ETH-USD", "LTC-USD", "BCH-USD", "XRP-USD", "ADA-USD", "SOL-USD", "DOGE-USD"]},
}

# --- in-process caches ------------------------------------------------------
_PANEL_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}
_PANEL_TTL = 6 * 3600.0
_SCAN_CACHE: dict[str, tuple[float, list]] = {}
_SCAN_TTL = 3 * 3600.0


def _panel(group: str, years: int) -> pd.DataFrame:
    """Cached wide price panel for a group (6h TTL)."""
    key = f"{group}:{years}"
    now = time.time()
    hit = _PANEL_CACHE.get(key)
    if hit and now - hit[0] < _PANEL_TTL:
        return hit[1]
    tickers = GROUPS[group]["tickers"]
    start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")
    px = get_multiple_closes(tickers, start=start).dropna(how="all")
    _PANEL_CACHE[key] = (now, px)
    return px


def _stats_dict(st: pr.PairStats) -> dict:
    d = asdict(st)
    d["cointegrated"] = st.cointegrated
    d["signal"] = st.signal()
    # JSON-safe (inf half-life → null)
    if not np.isfinite(d["half_life"]):
        d["half_life"] = None
    for k in ("correlation", "hedge_ratio", "intercept", "adf_stat", "adf_pvalue", "z_score"):
        v = d.get(k)
        d[k] = (None if v is None or not np.isfinite(v) else round(float(v), 4))
    return d


# --------------------------------------------------------------- endpoints
@router.get("/universe")
def universe() -> dict:
    """The curated asset groups the scanner can run over."""
    return {"ok": True, "groups": [
        {"id": g, "label": v["label"], "n_assets": len(v["tickers"]),
         "n_pairs": len(v["tickers"]) * (len(v["tickers"]) - 1) // 2,
         "tickers": v["tickers"]}
        for g, v in GROUPS.items()]}


@router.get("/scan")
def scan(group: str = Query("famous"), corr: float = Query(0.70, ge=0.0, le=1.0),
         years: int = Query(6, ge=2, le=25), z_window: int = Query(60, ge=15, le=250)) -> dict:
    """Two-stage scan of a group → the opportunity list (sorted by |z| desc)."""
    if group not in GROUPS:
        return {"ok": False, "error": f"unknown group '{group}'"}
    key = f"{group}:{corr}:{years}:{z_window}"
    now = time.time()
    hit = _SCAN_CACHE.get(key)
    if hit and now - hit[0] < _SCAN_TTL:
        n_cands, payload = hit[1]
        return {"ok": True, **_scan_payload(group, corr, years, n_cands, payload)}
    try:
        px = _panel(group, years)
        if px.shape[1] < 2:
            return {"ok": False, "error": "not enough assets with data"}
        cands = pr.correlation_prefilter(px, threshold=corr)
        res = pr.scan_pairs(px, corr_threshold=corr, z_window=z_window)
        # enrich every cointegrated pair with the net-of-cost spread backtest
        rows = []
        for st in res:
            d = _stats_dict(st)
            bt = pr.backtest_pair(px[st.a], px[st.b], z_window=z_window)
            d["backtest"] = _bt_dict(bt)
            rows.append(d)
        _SCAN_CACHE[key] = (now, (len(cands), rows))
        return {"ok": True, **_scan_payload(group, corr, years, len(cands), rows)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _scan_payload(group: str, corr: float, years: int, n_cands: int, rows: list[dict]) -> dict:
    n = len(GROUPS[group]["tickers"])
    n_edges = sum(1 for r in rows if (r.get("backtest") or {}).get("is_edge"))
    return {
        "group": group, "label": GROUPS[group]["label"],
        "n_assets": n, "n_possible_pairs": n * (n - 1) // 2,
        "corr_threshold": corr, "years": years,
        "stage1_survivors": n_cands, "n_cointegrated": len(rows),
        "n_edges": n_edges,
        "pairs": rows,
    }


def _bt_dict(bt: dict | None) -> dict | None:
    """Round a backtest dict for JSON (drop NaN/inf → null)."""
    if not bt:
        return None
    out = {}
    for k, v in bt.items():
        if k == "curve" or isinstance(v, bool) or v is None:  # bool is a subclass of int!
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = (None if not np.isfinite(v) else round(float(v), 4))
        else:
            out[k] = v
    return out


@router.get("/pair")
def pair(a: str = Query(...), b: str = Query(...), years: int = Query(6, ge=2, le=25),
         z_window: int = Query(60, ge=15, le=250), max_points: int = Query(900, ge=200, le=4000),
         use_log: bool = Query(True)) -> dict:
    """One pair's spread + rolling z-score history with entry/exit markers."""
    try:
        start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")
        px = get_multiple_closes([a, b], start=start).dropna()
        if px.shape[1] < 2 or len(px) < z_window + 10:
            return {"ok": False, "error": "insufficient overlapping data for this pair"}
        st = pr.engle_granger(px[a], px[b], use_log=use_log, z_window=z_window)
        if st is None:
            return {"ok": False, "error": "could not fit the pair"}
        spread = pr.spread_series(px[a], px[b], st.hedge_ratio, st.intercept, use_log=use_log)
        z = pr.zscore(spread, window=z_window)
        pos = pr.signal_series(z, entry=2.0)

        # entry/exit markers = state transitions of the position series
        markers = []
        prev = 0.0
        for ix, p in pos.items():
            if p != prev:
                if prev == 0 and p != 0:
                    markers.append({"t": str(ix.date()), "z": _r(z.get(ix)),
                                    "kind": "long" if p > 0 else "short"})
                elif p == 0 and prev != 0:
                    markers.append({"t": str(ix.date()), "z": _r(z.get(ix)), "kind": "exit"})
                prev = p

        step = max(1, len(spread) // max_points)
        idx = spread.index[::step]
        series = [{"t": str(ix.date()), "spread": _r(spread.get(ix)), "z": _r(z.get(ix))}
                  for ix in idx]
        bt = pr.backtest_pair(px[a], px[b], z_window=z_window, use_log=use_log, with_curve=True)
        return {"ok": True, "a": a, "b": b, "stats": _stats_dict(st),
                "z_window": z_window, "use_log": use_log,
                "series": series, "markers": markers, "backtest": _bt_dict(bt)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/heatmap")
def heatmap(group: str = Query("famous"), years: int = Query(6, ge=2, le=25)) -> dict:
    """Full cointegration matrix for a group: strength = 1 − ADF p-value.

    Runs Engle-Granger on EVERY pair (ignoring the correlation pre-filter) so the
    matrix is complete; the cell colour encodes how strongly the pair cointegrates.
    """
    if group not in GROUPS:
        return {"ok": False, "error": f"unknown group '{group}'"}
    try:
        px = _panel(group, years)
        cols = [c for c in GROUPS[group]["tickers"] if c in px.columns]
        n = len(cols)
        strength = [[None] * n for _ in range(n)]
        pmat = [[None] * n for _ in range(n)]
        for i in range(n):
            strength[i][i] = 1.0
            pmat[i][i] = 0.0
            for j in range(i + 1, n):
                st = pr.engle_granger(px[cols[i]], px[cols[j]])
                p = st.adf_pvalue if st is not None else None
                val = (None if p is None or not np.isfinite(p) else round(1.0 - float(p), 4))
                pv = (None if p is None or not np.isfinite(p) else round(float(p), 4))
                strength[i][j] = strength[j][i] = val
                pmat[i][j] = pmat[j][i] = pv
        return {"ok": True, "group": group, "label": GROUPS[group]["label"],
                "tickers": cols, "strength": strength, "pvalue": pmat}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------- helpers
def _r(x, d: int = 4):
    try:
        v = float(x)
        return None if not np.isfinite(v) else round(v, d)
    except (TypeError, ValueError):
        return None
