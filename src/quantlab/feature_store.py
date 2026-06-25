"""Machine-Learning Feature Store — centralised, look-ahead-safe factor computation.

A single place that turns raw OHLCV (via :mod:`quantlab.data`) into standardised
mathematical/statistical factors ("features") and **persists them to disk** so every
consumer (backtests, the agent, the dashboard) reads the same pre-computed values
instead of re-deriving them in RAM.

Design goals (from the spec):

1. **RAM-efficient caching.** Computed features are written to **Apache Parquet**
   (one file per ticker, columnar) and never held unbounded in memory. Reads use
   PyArrow column-projection (:func:`FeatureStore.load` ``factors=...``) so only the
   chunk an active loop needs is materialised. A small **SQLite** database
   (``_registry.db``) holds the metadata (last computed, compute-ms, missing-rate,
   on-disk bytes) that powers the Feature-Health dashboard.

2. **Factor registry ("feature buffet").** :data:`REGISTRY` declares the available
   factors grouped into *momentum*, *volatility* and *structure*. Adding a factor =
   adding one :class:`FactorDef`.

3. **Time-travel / no look-ahead.** Every factor is **causal**: the value at bar
   ``t`` depends only on data observable at the close of ``t`` (own OHLC + trailing
   windows + *previous* completed week/month). :func:`FeatureStore.as_of` returns the
   panel truncated at a date, and :func:`validate_no_lookahead` *proves* causality by
   a shift-invariance test (recompute on a truncated series; the value at the cutoff
   must be byte-identical to the full-series value).

Look-ahead rule of thumb baked into every factor here: **no centered windows, no
``shift(-k)``, no same-bar future** — weekly/monthly pivots use the *previous*
completed period, shifted and forward-filled onto the daily index.
"""

from __future__ import annotations

import io
import sqlite3
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import get_settings
from .data import get_prices

# ── factor primitives (all causal) ─────────────────────────────────────────────
# Each takes the OHLCV frame and returns a Series aligned to its index. They must
# only ever read past/current data — see validate_no_lookahead for the guarantee.


def _returns(df: pd.DataFrame) -> pd.Series:
    return df["Close"].pct_change()


def return_zscore(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling z-score of daily returns over ``window`` (trailing mean/std)."""
    r = _returns(df)
    mu = r.rolling(window).mean()
    sd = r.rolling(window).std()
    return (r - mu) / sd.replace(0.0, np.nan)


def rsi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Wilder's RSI over ``window`` bars, in [0, 100]."""
    delta = df["Close"].diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def macd_histogram(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD divergence = MACD line − signal line (the classic histogram).

    MACD = EMA(fast) − EMA(slow); signal = EMA(signal) of MACD. All EMAs are causal.
    """
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd - sig


def garman_klass(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling annualised Garman-Klass volatility estimator over ``window`` days.

    Per-day variance contribution uses that day's own O/H/L/C (known at close):
    ``0.5·ln(H/L)² − (2·ln2 − 1)·ln(C/O)²``; the rolling mean is annualised by √252.
    """
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    hl = np.log(h / l) ** 2
    co = np.log(c / o) ** 2
    daily_var = 0.5 * hl - (2.0 * np.log(2.0) - 1.0) * co
    return np.sqrt(daily_var.rolling(window).mean().clip(lower=0.0) * 252.0)


def _atr(df: pd.DataFrame, window: int) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [df["High"] - df["Low"],
         (df["High"] - prev_close).abs(),
         (df["Low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window).mean()


def atr_ratio(df: pd.DataFrame, fast: int = 14, slow: int = 50) -> pd.Series:
    """Short/long ATR ratio — a volatility-regime gauge (>1 = expanding range)."""
    return _atr(df, fast) / _atr(df, slow).replace(0.0, np.nan)


def _period_pivot(df: pd.DataFrame, rule: str) -> pd.Series:
    """Distance (%) of close to the *previous* completed period's floor pivot.

    Floor-trader pivot ``P = (H + L + C) / 3`` of the prior week/month, shifted one
    period and forward-filled onto the daily index → strictly look-ahead-safe.
    """
    grp = df.resample(rule).agg(H=("High", "max"), L=("Low", "min"), C=("Close", "last"))
    pivot = (grp["H"] + grp["L"] + grp["C"]) / 3.0
    pivot = pivot.shift(1)  # use the PREVIOUS completed period only
    daily = pivot.reindex(df.index, method="ffill")
    return (df["Close"] - daily) / daily


def dist_weekly_pivot(df: pd.DataFrame) -> pd.Series:
    return _period_pivot(df, "W-FRI")


def dist_monthly_pivot(df: pd.DataFrame) -> pd.Series:
    return _period_pivot(df, "ME")


def dist_sma(df: pd.DataFrame, window: int = 50) -> pd.Series:
    """Relative distance of close to its ``window``-day simple moving average."""
    sma = df["Close"].rolling(window).mean()
    return (df["Close"] - sma) / sma


# ── factor registry ("the buffet") ─────────────────────────────────────────────


@dataclass(frozen=True)
class FactorDef:
    name: str
    group: str  # momentum | volatility | structure
    func: Callable[[pd.DataFrame], pd.Series]
    description: str


REGISTRY: list[FactorDef] = [
    # Momentum
    FactorDef("ret_zscore_20", "momentum", lambda d: return_zscore(d, 20),
              "20-Tage rollierender Z-Score der Tagesrenditen"),
    FactorDef("rsi_14", "momentum", lambda d: rsi(d, 14),
              "Wilder RSI(14), Überkauft/Überverkauft-Oszillator"),
    FactorDef("macd_div", "momentum", lambda d: macd_histogram(d),
              "MACD-Divergenz (MACD-Linie − Signallinie, 12/26/9)"),
    # Volatility
    FactorDef("garman_klass_20", "volatility", lambda d: garman_klass(d, 20),
              "Garman-Klass-Volatilität (20T, annualisiert) aus OHLC"),
    FactorDef("atr_ratio_14_50", "volatility", lambda d: atr_ratio(d, 14, 50),
              "ATR(14)/ATR(50) — Volatilitäts-Regime (>1 = Ausweitung)"),
    # Structure
    FactorDef("dist_weekly_pivot", "structure", dist_weekly_pivot,
              "Abstand (%) des Close zum Floor-Pivot der Vorwoche"),
    FactorDef("dist_monthly_pivot", "structure", dist_monthly_pivot,
              "Abstand (%) des Close zum Floor-Pivot des Vormonats"),
    FactorDef("dist_sma_50", "structure", lambda d: dist_sma(d, 50),
              "Relativer Abstand des Close zum SMA(50)"),
    FactorDef("dist_sma_200", "structure", lambda d: dist_sma(d, 200),
              "Relativer Abstand des Close zum SMA(200)"),
]

FACTOR_BY_NAME: dict[str, FactorDef] = {f.name: f for f in REGISTRY}
GROUPS = ("momentum", "volatility", "structure")

# Default tickers the dashboard offers (liquid, cheap to pull via yfinance/cache).
DEFAULT_UNIVERSE: list[tuple[str, str]] = [
    ("SPY", "S&P 500 ETF"), ("QQQ", "Nasdaq-100 ETF"), ("IWM", "Russell 2000 ETF"),
    ("GC=F", "Gold"), ("CL=F", "Crude Oil (WTI)"), ("NG=F", "Natural Gas"),
    ("BTC-USD", "Bitcoin"), ("TLT", "20Y Treasury ETF"),
]

STALE_AFTER_DAYS = 2.0  # a feature file older than this many days is "stale"


# ── feature store ──────────────────────────────────────────────────────────────


def compute_features(
    df: pd.DataFrame, factors: Sequence[FactorDef] | None = None
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Compute the registry factors on an OHLCV frame, timing each one.

    Returns ``(feature_frame, timings_ms)`` where ``feature_frame`` is indexed like
    ``df`` and ``timings_ms`` maps factor name → wall-clock compute time (ms).
    """
    factors = list(factors or REGISTRY)
    out: dict[str, pd.Series] = {}
    timings: dict[str, float] = {}
    for fd in factors:
        t0 = time.perf_counter()
        out[fd.name] = fd.func(df).astype("float64")
        timings[fd.name] = (time.perf_counter() - t0) * 1000.0
    frame = pd.DataFrame(out, index=df.index)
    frame.index.name = "Date"
    return frame, timings


def _column_disk_bytes(series: pd.Series) -> int:
    """On-disk (parquet-encoded) byte size of a single feature column."""
    buf = io.BytesIO()
    series.to_frame().to_parquet(buf)
    return buf.tell()


class FeatureStore:
    """Persisted, look-ahead-safe feature store backed by Parquet + SQLite.

    Parquet files live under ``<store_dir>/<safe_ticker>.parquet`` (one columnar
    file per ticker). Metadata lives in ``<store_dir>/_registry.db``.
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        self.store_dir = Path(store_dir) if store_dir else get_settings().cache_dir / "features"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.store_dir / "_registry.db"
        self._init_db()

    # -- persistence helpers --
    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as cx:
            cx.execute(
                """CREATE TABLE IF NOT EXISTS feature_meta (
                    ticker TEXT NOT NULL,
                    factor TEXT NOT NULL,
                    grp TEXT NOT NULL,
                    last_computed REAL NOT NULL,
                    compute_ms REAL NOT NULL,
                    n_rows INTEGER NOT NULL,
                    n_missing INTEGER NOT NULL,
                    disk_bytes INTEGER NOT NULL,
                    PRIMARY KEY (ticker, factor)
                )"""
            )

    def _path(self, ticker: str) -> Path:
        safe = ticker.replace("^", "idx_").replace("=", "_").replace("/", "_")
        return self.store_dir / f"{safe}.parquet"

    # -- compute / write --
    def compute(
        self,
        ticker: str,
        start: str = "2010-01-01",
        end: str | None = None,
        factors: Sequence[str] | None = None,
    ) -> dict:
        """Compute + persist features for ``ticker``; update SQLite metadata.

        Returns a summary dict (rows, factors, per-factor timing/missing/bytes).
        """
        defs = ([FACTOR_BY_NAME[f] for f in factors] if factors else REGISTRY)
        prices = get_prices(ticker, start=start, end=end)
        frame, timings = compute_features(prices, defs)

        path = self._path(ticker)
        frame.to_parquet(path)  # whole panel; reads project columns on demand

        now = time.time()
        n_rows = len(frame)
        rows_meta = []
        with sqlite3.connect(self.db_path) as cx:
            for fd in defs:
                col = frame[fd.name]
                n_missing = int(col.isna().sum())
                disk_bytes = _column_disk_bytes(col)
                cx.execute(
                    """INSERT INTO feature_meta
                       (ticker, factor, grp, last_computed, compute_ms, n_rows, n_missing, disk_bytes)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(ticker, factor) DO UPDATE SET
                         grp=excluded.grp, last_computed=excluded.last_computed,
                         compute_ms=excluded.compute_ms, n_rows=excluded.n_rows,
                         n_missing=excluded.n_missing, disk_bytes=excluded.disk_bytes""",
                    (ticker, fd.name, fd.group, now, timings[fd.name],
                     n_rows, n_missing, disk_bytes),
                )
                rows_meta.append({
                    "factor": fd.name, "group": fd.group,
                    "compute_ms": round(timings[fd.name], 3),
                    "n_missing": n_missing,
                    "missing_rate": round(n_missing / n_rows, 4) if n_rows else 0.0,
                    "disk_bytes": disk_bytes,
                })
        return {
            "ticker": ticker, "n_rows": n_rows,
            "n_factors": len(defs), "file": path.name,
            "start": str(frame.index[0].date()) if n_rows else None,
            "end": str(frame.index[-1].date()) if n_rows else None,
            "factors": rows_meta,
        }

    # -- read (RAM-efficient: project only requested columns) --
    def load(
        self,
        ticker: str,
        factors: Iterable[str] | None = None,
        as_of: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Load persisted features. Only ``factors`` columns are read into RAM.

        ``as_of`` truncates to ``index <= as_of`` (the time-travel guarantee — see
        :func:`as_of`). Raises ``FileNotFoundError`` if the ticker is not built.
        """
        path = self._path(ticker)
        if not path.exists():
            raise FileNotFoundError(f"features not built for '{ticker}' — call compute() first")
        cols = list(factors) if factors else None
        frame = pd.read_parquet(path, columns=cols)  # PyArrow column projection
        if as_of is not None:
            frame = as_of_slice(frame, as_of)
        return frame

    def is_built(self, ticker: str) -> bool:
        return self._path(ticker).exists()

    # -- dashboard payloads --
    def status(self, ticker: str | None = None) -> list[dict]:
        """Per-(ticker, factor) registry rows with freshness/size/missing metadata."""
        now = time.time()
        q = "SELECT ticker, factor, grp, last_computed, compute_ms, n_rows, n_missing, disk_bytes FROM feature_meta"
        params: tuple = ()
        if ticker:
            q += " WHERE ticker = ?"
            params = (ticker,)
        q += " ORDER BY ticker, grp, factor"
        with sqlite3.connect(self.db_path) as cx:
            rows = cx.execute(q, params).fetchall()
        out = []
        for tk, factor, grp, last, ms, n_rows, n_miss, dbytes in rows:
            age_days = (now - last) / 86400.0
            out.append({
                "ticker": tk, "factor": factor, "group": grp,
                "status": "stale" if age_days > STALE_AFTER_DAYS else "up-to-date",
                "last_computed": last, "age_days": round(age_days, 2),
                "compute_ms": round(ms, 3),
                "n_rows": n_rows, "n_missing": n_miss,
                "missing_rate": round(n_miss / n_rows, 4) if n_rows else 0.0,
                "disk_bytes": dbytes,
            })
        return out

    def correlation(self, ticker: str, factors: Iterable[str] | None = None) -> dict:
        """Pearson correlation matrix of the ticker's factors (redundancy heatmap)."""
        frame = self.load(ticker, factors=factors).dropna(how="all")
        corr = frame.corr()
        labels = list(corr.columns)
        matrix = [[None if pd.isna(v) else round(float(v), 3) for v in corr.loc[r]] for r in labels]
        return {"labels": labels, "matrix": matrix, "n_rows": int(len(frame))}


# ── time-travel + look-ahead validation ────────────────────────────────────────


def as_of_slice(frame: pd.DataFrame, date: str | pd.Timestamp) -> pd.DataFrame:
    """Return only the rows observable at ``date`` (``index <= date``).

    The store-time guarantee (every factor is causal) makes this a true "time
    machine": the values returned here are byte-identical to what they were on
    ``date`` itself — see :func:`validate_no_lookahead`.
    """
    ts = pd.Timestamp(date)
    return frame.loc[frame.index <= ts]


def as_of(store: FeatureStore, ticker: str, date: str | pd.Timestamp,
          factors: Iterable[str] | None = None) -> pd.DataFrame:
    """Convenience: load ``ticker`` features as they stood at ``date``."""
    return store.load(ticker, factors=factors, as_of=date)


def validate_no_lookahead(
    ticker: str,
    factors: Sequence[str] | None = None,
    n_checks: int = 6,
    start: str = "2015-01-01",
    end: str | None = None,
    tol: float = 1e-9,
) -> dict:
    """Prove each factor is causal via a shift-invariance test.

    For several cutoff dates we recompute every factor using **only** the data up to
    the cutoff and compare it to the full-series value at that same date. A causal
    factor is unaffected by future bars, so the two must match within ``tol``; any
    mismatch is data leakage.

    Returns a per-factor report ``{factor: {ok, max_abs_diff, checks}}`` plus an
    overall ``ok`` flag — exactly what the dashboard surfaces as a leakage badge.
    """
    defs = ([FACTOR_BY_NAME[f] for f in factors] if factors else REGISTRY)
    prices = get_prices(ticker, start=start, end=end)
    full, _ = compute_features(prices, defs)

    n = len(prices)
    if n < 250:
        return {"ok": False, "error": "not enough data for a leakage check", "factors": {}}
    # spread cutoffs across the back half of the sample (need warm-up before them)
    idxs = np.linspace(int(n * 0.5), n - 2, num=min(n_checks, n // 50 + 1)).astype(int)
    cutoffs = [prices.index[i] for i in dict.fromkeys(idxs)]

    report: dict[str, dict] = {fd.name: {"max_abs_diff": 0.0, "checks": 0, "ok": True} for fd in defs}
    for cut in cutoffs:
        truncated = prices.loc[prices.index <= cut]
        trunc_feat, _ = compute_features(truncated, defs)
        for fd in defs:
            full_val = full[fd.name].loc[cut]
            trunc_val = trunc_feat[fd.name].iloc[-1]
            # both NaN (warm-up) counts as a match
            if pd.isna(full_val) and pd.isna(trunc_val):
                report[fd.name]["checks"] += 1
                continue
            diff = abs(float(full_val) - float(trunc_val))
            report[fd.name]["max_abs_diff"] = max(report[fd.name]["max_abs_diff"], diff)
            report[fd.name]["checks"] += 1
            if diff > tol or pd.isna(full_val) != pd.isna(trunc_val):
                report[fd.name]["ok"] = False

    for fd in defs:
        report[fd.name]["max_abs_diff"] = float(report[fd.name]["max_abs_diff"])
    overall = all(r["ok"] for r in report.values())
    return {"ok": overall, "n_cutoffs": len(cutoffs),
            "cutoffs": [str(c.date()) for c in cutoffs], "factors": report}
