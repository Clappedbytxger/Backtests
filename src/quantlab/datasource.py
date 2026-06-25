"""Unified market-data layer — pluggable providers behind one interface (Phase 3.2).

A single :func:`get_bars` dispatches to a chosen provider and always returns the same
shape (the project-standard OHLCV frame: ``Open/High/Low/Close/Volume`` on a ``Date``
index), so the rest of the app never special-cases a vendor:

* ``yfinance`` — the existing cached loader (:mod:`quantlab.data`); deep free history.
* ``alpaca``   — Alpaca Market Data v2 over REST (httpx), keyed from the BYOK vault
                 (``alpaca_key`` / ``alpaca_secret``); IEX feed (free on paper accounts).

Timeframes are given in a canonical vocabulary (``1Day``/``1Hour``/``1Min``/``1Week``)
and mapped per provider. Provider availability (does Alpaca have keys?) is reported by
:func:`provider_status` so the UI can show what is wired up.
"""

from __future__ import annotations

import httpx
import pandas as pd

# canonical timeframe -> (yfinance interval, alpaca timeframe)
_TF: dict[str, tuple[str, str]] = {
    "1Min": ("1m", "1Min"),
    "1Hour": ("1h", "1Hour"),
    "1Day": ("1d", "1Day"),
    "1Week": ("1wk", "1Week"),
}
PROVIDERS = ("yfinance", "alpaca")
_ALPACA_DATA_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"


def _alpaca_creds() -> tuple[str, str] | None:
    """``(key_id, secret)`` from the vault/env/keyfile, or ``None`` if not configured."""
    from quantlab.fundamental_data import read_api_key

    try:
        return read_api_key("alpaca_key"), read_api_key("alpaca_secret")
    except RuntimeError:
        return None


def get_bars(symbol: str, start: str | None = None, end: str | None = None,
             timeframe: str = "1Day", provider: str = "yfinance",
             limit: int = 10000) -> pd.DataFrame:
    """OHLCV bars for ``symbol`` from ``provider`` in a unified shape.

    Args:
        symbol: provider-native symbol (``"SPY"`` works for both; futures like
            ``"NG=F"`` are yfinance-only).
        start/end: ISO dates (``end`` exclusive). ``None`` → provider default.
        timeframe: one of ``1Min``/``1Hour``/``1Day``/``1Week``.
        provider: ``"yfinance"`` or ``"alpaca"``.
        limit: max bars (Alpaca pagination cap).

    Returns a DataFrame indexed by ``Date`` with ``Open/High/Low/Close/Volume``.
    """
    if timeframe not in _TF:
        raise ValueError(f"unknown timeframe {timeframe!r}; use one of {list(_TF)}")
    if provider == "yfinance":
        from quantlab.data import get_prices

        return get_prices(symbol, start=start or "1990-01-01", end=end,
                          interval=_TF[timeframe][0])
    if provider == "alpaca":
        return _alpaca_bars(symbol, start, end, _TF[timeframe][1], limit)
    raise ValueError(f"unknown provider {provider!r}; use one of {PROVIDERS}")


def _alpaca_bars(symbol: str, start: str | None, end: str | None,
                 tf: str, limit: int) -> pd.DataFrame:
    creds = _alpaca_creds()
    if creds is None:
        raise RuntimeError("Alpaca keys not set — add alpaca_key / alpaca_secret in Settings")
    key, secret = creds
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = {"timeframe": tf, "limit": min(limit, 10000), "adjustment": "all", "feed": "iex"}
    if start:
        params["start"] = start
    if end:
        params["end"] = end

    rows: list[dict] = []
    url = _ALPACA_DATA_URL.format(symbol=symbol.upper())
    for _ in range(20):  # pagination cap
        r = httpx.get(url, params=params, headers=headers, timeout=30.0)
        if r.status_code in (401, 403):
            raise RuntimeError("Alpaca auth failed — check alpaca_key / alpaca_secret")
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get("bars") or [])
        token = data.get("next_page_token")
        if not token or len(rows) >= limit:
            break
        params["page_token"] = token

    if not rows:
        raise ValueError(f"Alpaca returned no bars for '{symbol}'")
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["t"], utc=True).dt.tz_localize(None)
    df = (df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                             "c": "Close", "v": "Volume"})
            .set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]
            .sort_index())
    return df


def provider_status() -> list[dict]:
    """Per-provider availability for the Settings/Data UI (no network calls)."""
    alpaca_ok = _alpaca_creds() is not None
    return [
        {"provider": "yfinance", "label": "Yahoo Finance", "available": True,
         "needs_keys": False, "reason": "frei, tiefe Historie (Aktien/ETF/Futures/Indizes)"},
        {"provider": "alpaca", "label": "Alpaca Market Data", "available": alpaca_ok,
         "needs_keys": True,
         "reason": "bereit" if alpaca_ok else "alpaca_key/alpaca_secret im Vault setzen"},
    ]
