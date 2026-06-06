"""Intraday crypto OHLCV loading with on-disk caching, mirroring ``data.py``.

Uses ccxt to page through an exchange's public REST klines (no API key needed)
and caches the full series as Parquet so repeated runs do not re-download. The
exchange feed is the consolidated venue tape (e.g. Binance spot), so unlike the
IEX equity feed the volume column is real and usable.

Binance spot BTC/USDT history begins ~2017-08-17. Lower timeframes (1m) produce
far larger files but are fetched the same way — just pass ``timeframe="1m"``.
"""

from __future__ import annotations

import time
from pathlib import Path

import ccxt
import pandas as pd

# Cache lives next to the project root: D:/Backtests/data/cache/crypto
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "crypto"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Most exchanges cap one kline request at ~1000 candles.
_PAGE_LIMIT = 1000


def _cache_path(exchange: str, symbol: str, timeframe: str) -> Path:
    safe_symbol = symbol.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{exchange}_{safe_symbol}_{timeframe}.parquet"


def get_crypto_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since: str = "2017-01-01",
    exchange: str = "binance",
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Download (or load cached) OHLCV candles for one crypto pair.

    Returns a DataFrame indexed by UTC timestamp with columns
    ``Open, High, Low, Close, Volume``.

    Args:
        symbol: ccxt unified symbol, e.g. ``"BTC/USDT"``.
        timeframe: ccxt timeframe, e.g. ``"1h"``, ``"15m"``, ``"1m"``, ``"1d"``.
        since: ISO start date; the loader fetches forward from here to now.
        exchange: ccxt exchange id, e.g. ``"binance"``, ``"bybit"``, ``"kraken"``.
        use_cache: read/write the Parquet cache.
        force_refresh: ignore an existing cache file and re-download.
    """
    path = _cache_path(exchange, symbol, timeframe)
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    client = getattr(ccxt, exchange)({"enableRateLimit": True})
    tf_ms = client.parse_timeframe(timeframe) * 1000
    cursor = client.parse8601(f"{since}T00:00:00Z")
    now = client.milliseconds()

    rows: list[list[float]] = []
    while cursor < now:
        batch = client.fetch_ohlcv(symbol, timeframe, since=cursor, limit=_PAGE_LIMIT)
        if not batch:
            break
        rows.extend(batch)
        next_cursor = batch[-1][0] + tf_ms
        if next_cursor <= cursor:  # no forward progress -> stop
            break
        cursor = next_cursor
        time.sleep(client.rateLimit / 1000)  # be polite to the public endpoint

    if not rows:
        raise ValueError(f"No data returned for {symbol} {timeframe} on {exchange}.")

    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    df = df.drop_duplicates(subset="ts").sort_values("ts")
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.index.name = "Date"
    df = df[["Open", "High", "Low", "Close", "Volume"]]

    if use_cache:
        df.to_parquet(path)
    return df


if __name__ == "__main__":
    df = get_crypto_ohlcv("BTC/USDT", timeframe="1h", since="2017-01-01")
    print(f"BTC/USDT 1h on binance: {len(df):,} candles")
    print(f"  range: {df.index[0]}  ->  {df.index[-1]}")
    print(df.head(3))
    print(df.tail(3))
