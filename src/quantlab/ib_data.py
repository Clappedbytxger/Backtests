"""Intraday price data — Interactive Brokers (deep history) + yfinance fallback.

`load_prices(instrument, timeframe)` is the unified entry point used by the agent
harness: ``timeframe="1d"`` returns the cached daily yfinance series; an intraday
timeframe (``"1h"``, ``"30m"``, ``"15m"``, ``"5m"``, ``"1m"``) returns bars with a
**tz-aware DatetimeIndex** (so ``.hour`` / ``.minute`` exist and time-of-day rules
work). Intraday prefers a cached IBKR pull (deep history) and falls back to
yfinance (rolling ~2y for 1h) when none exists.

IBKR pulls (:func:`get_intraday`) need a running TWS / IB Gateway and reuse the
0108 connection pattern. Pre-populate the cache with ``scripts/fetch_intraday.py``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import get_settings

_INTRADAY = {"1h", "60m", "30m", "15m", "5m", "1m"}
# timeframe -> (yfinance interval, yfinance max period, IBKR barSizeSetting)
_TF = {
    "1h": ("1h", "730d", "1 hour"),
    "60m": ("1h", "730d", "1 hour"),
    "30m": ("30m", "60d", "30 mins"),
    "15m": ("15m", "60d", "15 mins"),
    "5m": ("5m", "60d", "5 mins"),
    "1m": ("1m", "7d", "1 min"),
}
_IB_PORTS = (7497, 4002, 7496, 4001)  # TWS paper, Gateway paper, TWS live, Gateway live


def _cache_dir() -> Path:
    d = get_settings().cache_dir / "intraday"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(symbol: str, timeframe: str, source: str) -> Path:
    safe = symbol.replace("=", "_").replace("^", "idx_").replace("/", "_")
    return _cache_dir() / f"{safe}_{timeframe}_{source}.parquet"


def _normalize(df: pd.DataFrame, tz: str = "UTC") -> pd.DataFrame:
    """Standardize to Open/High/Low/Close/Volume with a tz-aware DatetimeIndex."""
    df = df.rename(columns=str.title)
    if "Date" in df.columns:
        df = df.set_index("Date")
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize(tz)
    df.index.name = "Date"
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    return df[cols].dropna(subset=["Close"]).sort_index()


# ---------------------------------------------------------------- yfinance path
def get_intraday_yf(symbol: str, timeframe: str = "1h", use_cache: bool = True,
                    force_refresh: bool = False) -> pd.DataFrame:
    """Intraday bars from yfinance (free, no gateway; rolling window per interval)."""
    if timeframe not in _TF:
        raise ValueError(f"unsupported intraday timeframe {timeframe!r} ({sorted(_TF)})")
    cache = _cache_path(symbol, timeframe, "yf")
    if use_cache and not force_refresh and cache.exists():
        return pd.read_parquet(cache)
    import yfinance as yf

    interval, period, _ = _TF[timeframe]
    raw = yf.download(symbol, interval=interval, period=period, auto_adjust=True,
                      progress=False, actions=False)
    if raw.empty:
        raise ValueError(f"no intraday data for {symbol!r} ({interval}, {period})")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = _normalize(raw)
    if use_cache:
        df.to_parquet(cache)
    return df


# -------------------------------------------------------------------- IBKR path
def _ib_contract(symbol: str):
    """Map a yfinance-style symbol to an IBKR contract + default whatToShow."""
    from ib_async import Crypto, Forex, Index, Stock

    proxies = {"^GSPC": "SPY", "^NDX": "QQQ", "^DJI": "DIA", "^RUT": "IWM"}
    if symbol.endswith("-USD"):  # crypto, e.g. BTC-USD
        return Crypto(symbol.split("-")[0], "PAXOS", "USD"), "MIDPOINT"
    if symbol.endswith("=X"):  # FX, e.g. EURUSD=X
        return Forex(symbol[:-2]), "MIDPOINT"
    if symbol in proxies:
        return Stock(proxies[symbol], "SMART", "USD"), "TRADES"
    if symbol.startswith("^"):
        return Index(symbol[1:], "CBOE", "USD"), "TRADES"
    return Stock(symbol, "SMART", "USD"), "TRADES"


def get_intraday(symbol: str, timeframe: str = "1h", duration: str = "2 Y",
                 what: str | None = None, use_rth: bool = False,
                 host: str = "127.0.0.1", port: int | None = None,
                 client_id: int = 131, force_refresh: bool = False) -> pd.DataFrame:
    """Intraday bars from Interactive Brokers (needs a running TWS / IB Gateway).

    Caches to ``data/cache/intraday/<sym>_<tf>_ib.parquet``. ``duration`` follows
    IBKR syntax (e.g. ``"2 Y"``, ``"6 M"``, ``"30 D"``); IBKR limits the span per
    bar size, so request finer bars over shorter windows.
    """
    if timeframe not in _TF:
        raise ValueError(f"unsupported intraday timeframe {timeframe!r}")
    cache = _cache_path(symbol, timeframe, "ib")
    if cache.exists() and not force_refresh:
        return pd.read_parquet(cache)

    from ib_async import IB, util
    util.logToConsole(level=50)
    contract, what_default = _ib_contract(symbol)
    bar_size = _TF[timeframe][2]
    ib = IB()
    ports = (port,) if port else _IB_PORTS
    last_err = None
    for p in ports:
        try:
            ib.connect(host, p, clientId=client_id, timeout=8, readonly=True)
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
    if not ib.isConnected():
        raise ConnectionError(
            f"no TWS/IB Gateway on {host}:{ports} — start it and enable API access "
            f"({type(last_err).__name__ if last_err else 'refused'})")
    try:
        ib.qualifyContracts(contract)
        bars = ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration, barSizeSetting=bar_size,
            whatToShow=what or what_default, useRTH=use_rth, formatDate=2)
        if not bars:
            raise ValueError(f"IBKR returned no bars for {symbol} ({bar_size}, {duration})")
        df = _normalize(util.df(bars))
    finally:
        ib.disconnect()
    df.to_parquet(cache)
    return df


# ---------------------------------------------------------------- unified entry
def load_prices(instrument: str, timeframe: str = "1d", start: str = "2005-01-01") -> pd.DataFrame:
    """Daily (yfinance) or intraday (cached IBKR -> yfinance fallback) OHLCV."""
    if timeframe in ("1d", "1day", "daily", "d"):
        from .data import get_prices
        return get_prices(instrument, start=start)
    ib_cache = _cache_path(instrument, timeframe, "ib")
    if ib_cache.exists():
        return pd.read_parquet(ib_cache)  # deep IBKR history if pre-fetched
    return get_intraday_yf(instrument, timeframe)
