"""Data loading with on-disk caching for reproducible backtests.

Wraps yfinance and caches results as Parquet so repeated runs do not re-download
and remain deterministic. Always uses auto-adjusted prices (splits + dividends)
to avoid spurious return jumps.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from .config import get_settings

# Cache root from central config (default: <repo>/data/cache, unchanged).
CACHE_DIR = get_settings().cache_dir
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(ticker: str, start: str | None, end: str | None, interval: str) -> Path:
    """Build a stable cache filename from the request parameters."""
    key = f"{ticker}_{start}_{end}_{interval}"
    digest = hashlib.md5(key.encode()).hexdigest()[:10]
    safe_ticker = ticker.replace("^", "idx_").replace("=", "_").replace("/", "_")
    return CACHE_DIR / f"{safe_ticker}_{interval}_{digest}.parquet"


def get_prices(
    ticker: str,
    start: str | None = "1990-01-01",
    end: str | None = None,
    interval: str = "1d",
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Download (or load cached) OHLCV data for a single ticker.

    Returns a DataFrame indexed by date with columns:
    ``Open, High, Low, Close, Volume``. ``Close`` is split/dividend adjusted.

    Args:
        ticker: yfinance symbol, e.g. ``"SPY"``, ``"^GSPC"``, ``"NG=F"``.
        start: ISO start date (inclusive). ``None`` means earliest available.
        end: ISO end date (exclusive). ``None`` means today.
        interval: yfinance interval, e.g. ``"1d"``, ``"1wk"``.
        use_cache: read/write the Parquet cache.
        force_refresh: ignore an existing cache file and re-download.
    """
    path = _cache_path(ticker, start, end, interval)
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    raw = yf.download(
        ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
        actions=False,
    )
    if raw.empty:
        raise ValueError(f"No data returned for ticker '{ticker}' ({start}..{end}).")

    # yfinance may return a MultiIndex column header for a single ticker; flatten it.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index.name = "Date"
    df = df.dropna(subset=["Close"])

    if use_cache:
        df.to_parquet(path)
    return df


_SPLITS_DIR = CACHE_DIR / "splits"


def get_splits(
    ticker: str,
    use_cache: bool = True,
    force_refresh: bool = False,
    max_age_days: float = 7.0,
) -> pd.Series:
    """Stock split history: ``{ex_date -> ratio}`` (e.g. ``4.0`` for a 4:1 split).

    Used to split-adjust the RAW intraday equities cache so charts line up with
    TradingView (which is split-adjusted by default). Cached to Parquet with a TTL
    since splits change rarely. Returns an empty Series when there are none or the
    lookup fails (callers then leave prices raw).
    """
    _SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace("^", "idx_").replace("=", "_").replace("/", "_")
    path = _SPLITS_DIR / f"{safe}.parquet"

    if use_cache and not force_refresh and path.exists():
        if time.time() - path.stat().st_mtime < max_age_days * 86400:
            try:
                s = pd.read_parquet(path)["ratio"]
                s.index = pd.to_datetime(s.index, utc=True)
                return s
            except Exception:  # noqa: BLE001 - a corrupt cache should just re-fetch
                pass

    try:
        raw = yf.Ticker(ticker).splits  # tz-aware DatetimeIndex -> float ratios
    except Exception:  # noqa: BLE001 - offline / bad symbol -> no adjustment
        raw = None
    if raw is None or len(raw) == 0:
        s = pd.Series(dtype="float64", name="ratio")
        s.index = pd.to_datetime(s.index, utc=True)
    else:
        s = raw[raw != 0].astype("float64")
        s.index = pd.to_datetime(s.index, utc=True)
        s.name = "ratio"

    if use_cache:
        try:
            s.to_frame().to_parquet(path)
        except Exception:  # noqa: BLE001
            pass
    return s


def get_close(ticker: str, **kwargs) -> pd.Series:
    """Convenience wrapper returning only the adjusted Close series."""
    return get_prices(ticker, **kwargs)["Close"].rename(ticker)


def get_multiple_closes(tickers: list[str], **kwargs) -> pd.DataFrame:
    """Load adjusted Close for several tickers, aligned on a common date index."""
    series = {}
    for t in tickers:
        try:
            series[t] = get_close(t, **kwargs)
        except ValueError:
            # Skip tickers with no data rather than failing the whole batch.
            continue
    return pd.DataFrame(series)
