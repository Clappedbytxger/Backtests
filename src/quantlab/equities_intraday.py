"""Intraday US-equity OHLCV from Databento (XNAS.ITCH, Nasdaq-listed), cached.

Mirrors ``futures_intraday.py`` but for single-name equities via the Nasdaq ITCH
feed (``XNAS.ITCH``, ``stype_in="raw_symbol"``, 1-minute OHLCV from 2018-05).
Motivation: the faithful Stufe-1 reproduction of cross-sectional intraday-equity
edges (e.g. Zarattini "stocks-in-play" opening-range breakout, idea I0067) that the
single-instrument CTI adaptation cannot capture — the published Sharpe lives in the
cross-section, so it must be tested on a stock universe, not one index.

Cost discipline as in the futures loader: ALWAYS print/gate the metered cost before
a download, cache hard. The consolidated US datasets (DBEQ.BASIC / EQUS.MINI) only
start 2023-03, so XNAS.ITCH (Nasdaq-listed, 2018-05+) is the deep free-credit path.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from .futures_intraday import _client, CACHE_DIR  # reuse key/client + cache root

_DATASET = "XNAS.ITCH"
_EQ_CACHE = CACHE_DIR.parent / "equities"
_EQ_CACHE.mkdir(parents=True, exist_ok=True)


def _path(symbol: str, schema: str, start: str, end: str) -> Path:
    return _EQ_CACHE / f"{symbol}_{schema}_{start}_{end}.parquet"


def estimate_cost(symbols, schema="ohlcv-1m", start="2018-05-01", end=None) -> dict:
    end = end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    c = _client()
    kw = dict(dataset=_DATASET, symbols=list(symbols), schema=schema,
              start=start, end=end, stype_in="raw_symbol")
    return {"usd": float(c.metadata.get_cost(**kw)),
            "records": int(c.metadata.get_record_count(**kw)),
            "n_symbols": len(symbols), "start": start, "end": end}


def get_equities_intraday(symbols, schema="ohlcv-1m", start="2018-05-01",
                          end=None, max_usd=5.0, use_cache=True,
                          force_refresh=False) -> dict[str, pd.DataFrame]:
    """Download (or load cached) 1-min OHLCV for several Nasdaq tickers.

    Returns ``{symbol: DataFrame}`` with UTC index and O/H/L/C/V columns. Symbols
    already cached are loaded; only the missing ones are fetched (one metered
    request for the whole missing batch, guarded by ``max_usd``).
    """
    end = end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    out: dict[str, pd.DataFrame] = {}
    missing = []
    for s in symbols:
        p = _path(s, schema, start, end)
        if use_cache and not force_refresh and p.exists():
            out[s] = pd.read_parquet(p)
        else:
            missing.append(s)
    if not missing:
        return out

    est = estimate_cost(missing, schema, start, end)
    print(f"[databento] XNAS.ITCH {schema} {len(missing)} symbols {start}..{end}: "
          f"{est['records']:,} records, metered ${est['usd']:.2f}")
    if est["usd"] > max_usd:
        raise RuntimeError(f"Refusing download: ${est['usd']:.2f} > max_usd=${max_usd:.2f}.")

    # Fetch ONE symbol at a time and persist immediately. A single bulk request +
    # ``to_df()`` over tens of millions of rows OOMs on the pandas deep-copy; the
    # per-symbol loop bounds memory and means a crash loses at most one symbol's
    # progress (the metered data already paid for is not re-lost).
    c = _client()
    for i, s in enumerate(missing, 1):
        data = c.timeseries.get_range(dataset=_DATASET, symbols=[s], schema=schema,
                                      start=start, end=end, stype_in="raw_symbol")
        df = data.to_df()
        if df.empty:
            print(f"  ({i}/{len(missing)}) {s}: EMPTY"); out[s] = df; continue
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                "close": "Close", "volume": "Volume"})
        df.index = pd.to_datetime(df.index, utc=True)
        sub = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        sub = sub[sub["Close"] > 0].sort_index()
        if use_cache and not sub.empty:
            sub.to_parquet(_path(s, schema, start, end))
        out[s] = sub
        print(f"  ({i}/{len(missing)}) {s}: {len(sub):,} bars cached")
        del data, df, sub
    return out
