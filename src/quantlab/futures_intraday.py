"""Intraday futures OHLCV from Databento (CME Globex), with on-disk caching.

Mirrors ``data.py`` (yfinance) and ``crypto_data.py`` (ccxt): page the data once,
cache it as Parquet, never re-download. The motivation is the prop-edge research
program (Prop-Edge-Framework.md): the priority hypotheses — opening-range fade,
time-of-day, ES<->NQ lead-lag — need real *intraday* index-futures bars with
years of depth, which the free yfinance feed does not provide (1h only ~2.4y).

Databento gives a $125 free credit on signup and *no* daily request cap. The
CME dataset ``GLBX.MDP3`` carries the real ES/NQ/MES/MNQ contracts. 1-minute
OHLCV is tiny, so a decade of ES costs only a few cents of credit — but the
credit is finite, so this module ALWAYS prints (and can gate on) the metered
cost before a download, and caches hard.

Symbology (continuous front month, calendar roll):
    ES.c.0  -> S&P 500 e-mini front month         (GLBX.MDP3 starts 2010-06-06)
    NQ.c.0  -> Nasdaq-100 e-mini front month
    MES.c.0 -> Micro S&P 500   (only from 2019-05, the micro launch)
    MNQ.c.0 -> Micro Nasdaq-100 (only from 2019-05)

ES/NQ are preferred for depth: intraday *returns* are identical to MES/MNQ (same
underlying, just a smaller multiplier), so backtest on ES.c.0 / NQ.c.0 and apply
the MES_INTRADAY / MNQ_INTRADAY cost model from ``quantlab.costs``.

Auth: set the environment variable ``DATABENTO_API_KEY`` (do NOT hardcode it).
    PowerShell:  $env:DATABENTO_API_KEY = "db-..."
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

# Cache lives next to the project root: D:/Backtests/data/cache/futures
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "futures"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_DATASET = "GLBX.MDP3"  # CME Globex MDP 3.0


def _cache_path(symbol: str, schema: str, start: str, end: str | None) -> Path:
    safe = symbol.replace(".", "_").replace("/", "_")
    return CACHE_DIR / f"{safe}_{schema}_{start}_{end}.parquet"


# Gitignored fallback keyfile (matches the ``*.key`` rule in .gitignore), so the
# key survives across shells without depending on env-var propagation.
_KEYFILE = Path(__file__).resolve().parents[2] / ".databento.key"


def _read_key() -> str | None:
    """API key from the env var, else the gitignored .databento.key file."""
    key = os.environ.get("DATABENTO_API_KEY")
    if key:
        return key.strip()
    if _KEYFILE.exists():
        return _KEYFILE.read_text(encoding="utf-8").strip() or None
    return None


def _client():
    """Build a Databento Historical client from the API key."""
    key = _read_key()
    if not key:
        raise RuntimeError(
            "No Databento API key found. Sign up at databento.com (free $125 "
            "credit), copy your key, then EITHER set the env var\n"
            '    $env:DATABENTO_API_KEY = "db-..."\n'
            f"OR write the key into {_KEYFILE} (gitignored)."
        )
    import databento as db  # imported lazily so the module loads without the SDK

    return db.Historical(key)


def estimate_cost(
    symbol: str = "ES.c.0",
    schema: str = "ohlcv-1m",
    start: str = "2010-06-06",
    end: str | None = None,
    dataset: str = _DATASET,
) -> dict:
    """Return Databento's metered cost (USD) + record count for a request.

    Call this BEFORE downloading to protect the finite free credit. Cheap
    metadata call; does not consume data credit.
    """
    # Continuous symbology fails to resolve when ``end`` is omitted, so always
    # pass an explicit end (default: today).
    end = end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    client = _client()
    kwargs = dict(dataset=dataset, symbols=[symbol], schema=schema,
                  start=start, end=end, stype_in="continuous")
    cost = client.metadata.get_cost(**kwargs)
    size = client.metadata.get_record_count(**kwargs)
    return {"usd": float(cost), "records": int(size), "symbol": symbol,
            "schema": schema, "start": start, "end": end}


def get_futures_intraday(
    symbol: str = "ES.c.0",
    schema: str = "ohlcv-1m",
    start: str = "2010-06-06",
    end: str | None = None,
    dataset: str = _DATASET,
    use_cache: bool = True,
    force_refresh: bool = False,
    max_usd: float = 5.0,
) -> pd.DataFrame:
    """Download (or load cached) intraday OHLCV bars for one futures symbol.

    Returns a DataFrame indexed by UTC timestamp with columns
    ``Open, High, Low, Close, Volume`` (capitalised to match ``data.py`` /
    ``crypto_data.py`` so the rest of quantlab is drop-in compatible).

    Args:
        symbol: continuous-front-month symbol, e.g. ``"ES.c.0"``.
        schema: ``"ohlcv-1m"``, ``"ohlcv-1h"`` or ``"ohlcv-1d"``.
        start / end: ISO dates. ``end=None`` means latest available.
        use_cache / force_refresh: Parquet cache controls.
        max_usd: hard guard — refuse to download if the metered cost exceeds this
            (protects the free credit). Raise it deliberately for big pulls.
    """
    end = end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    path = _cache_path(symbol, schema, start, end)
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    est = estimate_cost(symbol, schema, start, end, dataset)
    print(f"[databento] {symbol} {schema} {start}..{end or 'now'}: "
          f"{est['records']:,} records, metered cost ${est['usd']:.4f}")
    if est["usd"] > max_usd:
        raise RuntimeError(
            f"Refusing to download: metered cost ${est['usd']:.2f} exceeds "
            f"max_usd=${max_usd:.2f}. Raise max_usd to override."
        )

    client = _client()
    kwargs = dict(dataset=dataset, symbols=[symbol], schema=schema,
                  start=start, stype_in="continuous")
    if end:
        kwargs["end"] = end
    data = client.timeseries.get_range(**kwargs)
    df = data.to_df()  # float prices, UTC DatetimeIndex (ts_event)

    if df.empty:
        raise ValueError(f"No data returned for {symbol} {schema} ({start}..{end}).")

    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "Date"
    df = df[df["Close"] > 0]  # guard (lesson 0005: futures can print non-positive)

    if use_cache:
        df.to_parquet(path)
    return df


if __name__ == "__main__":
    # Dry run: estimate cost only, no download (safe without spending credit).
    try:
        for sym in ["ES.c.0", "NQ.c.0"]:
            e = estimate_cost(sym, "ohlcv-1m", "2010-06-06")
            print(f"{sym} ohlcv-1m full history: {e['records']:,} bars, ${e['usd']:.4f}")
    except RuntimeError as exc:
        print(exc)
