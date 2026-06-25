"""Market-regime detection — the "Weather Radar" engine.

Classifies each bar of an OHLC series into one of FOUR mutually-exclusive market
regimes by crossing two independent axes:

* **Volatility axis** (high / low) — is the market unusually agitated *for itself*?
  Driven by annualized realized volatility (std of log returns) and ATR-as-%-of-price,
  ranked against the asset's own trailing distribution. An optional external
  volatility index (e.g. ``^VIX`` for equities) is blended in when supplied.
* **Trend axis** (trending / sideways) — is price going somewhere, or chopping?
  Driven by Wilder's ADX (trend *strength*) plus the alignment of price to the
  EMA20 / SMA50 / SMA200 stack (trend *direction*).

The 2×2 cross yields the four canonical regimes:

==================  ====================  ============================================
code                label                 reading
==================  ====================  ============================================
``high_vol_trend``  High Vol · Trending   strong directional move, agitated (bull/bear)
``low_vol_trend``   Low Vol · Trending    stable, orderly trend ("the easy money")
``high_vol_range``  High Vol · Choppy     whipsaw / news-driven range, hard to trade
``low_vol_range``   Low Vol · Quiet       calm range / accumulation
==================  ====================  ============================================

Plus an orthogonal **direction** (``bull`` / ``bear`` / ``neutral``) from the MA
stack, so a trend regime can be reported as bullish or bearish without multiplying
the regime count.

Look-ahead safety: every column at bar ``t`` uses only bars ``<= t`` (rolling /
EWM / expanding windows, no centered windows, no ``shift(-k)``). The regime is a
*nowcast* knowable at the close of ``t`` — which is exactly what makes the per-regime
performance breakdown (used to validate Alpha-Factory hypotheses) honest. The
causality guarantee is pinned by ``tests/test_regime.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ── single source of truth for regime codes, labels, colors ──────────────────
# The API hands these to the frontend so the "weather" palette is defined once.

REGIMES: tuple[str, ...] = (
    "high_vol_trend",
    "low_vol_trend",
    "high_vol_range",
    "low_vol_range",
)

REGIME_LABELS: dict[str, str] = {
    "high_vol_trend": "High Vol · Trending",
    "low_vol_trend": "Low Vol · Trending",
    "high_vol_range": "High Vol · Choppy",
    "low_vol_range": "Low Vol · Quiet",
}

# Bloomberg-terminal "weather" palette: alarm red for the dangerous trend, neon
# green for the orderly trend, amber for choppy, muted slate for quiet.
REGIME_COLORS: dict[str, str] = {
    "high_vol_trend": "#ef4444",  # alarm red
    "low_vol_trend": "#22c55e",   # neon green
    "high_vol_range": "#f59e0b",  # amber
    "low_vol_range": "#64748b",   # muted slate-grey
}

REGIME_DESCRIPTIONS: dict[str, str] = {
    "high_vol_trend": "Starker Richtungsschub bei hoher Volatilität — Trend, aber ruppig (Breakouts/Crashes).",
    "low_vol_trend": "Stabiler, geordneter Trend bei niedriger Vola — das ruhige Trendregime.",
    "high_vol_range": "Unruhiger Seitwärtsmarkt — Whipsaws, news-getrieben, schwer handelbar.",
    "low_vol_range": "Ruhige Range / Akkumulation — niedrige Vola, kein Trend.",
}

DIRECTION_LABELS: dict[str, str] = {"bull": "Bullish", "bear": "Bearish", "neutral": "Neutral"}


@dataclass(frozen=True)
class RegimeConfig:
    """Tunable thresholds for the classifier (sane defaults baked in)."""

    vol_window: int = 21          # lookback for realized vol & ATR%
    vol_rank_window: int = 252    # trailing window the vol is ranked within
    vol_high_pct: float = 0.55    # vol-rank above this ⇒ "high vol" (slightly > median)
    atr_period: int = 14
    adx_period: int = 14
    adx_trend_min: float = 22.0   # ADX at/above ⇒ trending (Wilder's classic ~20-25)
    ema_fast: int = 20
    sma_mid: int = 50
    sma_slow: int = 200
    ann_factor: float = 252.0     # trading days/year for vol annualization
    vix_weight: float = 0.5       # blend weight when an external vol index is given
    min_history: int = 60         # bars required before a regime is emitted


# ── primitive indicators (causal) ────────────────────────────────────────────


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Wilder True Range; first bar = High-Low (no previous close)."""
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    tr.iloc[0] = (high.iloc[0] - low.iloc[0]) if len(high) else np.nan
    return tr


def _wilder_rma(s: pd.Series, period: int) -> pd.Series:
    """Wilder's running moving average (RMA) — EWM with alpha = 1/period."""
    return s.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Causal Wilder ATR over ``period`` bars (known at the close of each bar)."""
    return _wilder_rma(_true_range(df["High"], df["Low"], df["Close"]), period)


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Wilder's ADX with +DI / -DI. Returns a frame ``{adx, plus_di, minus_di}``.

    Standard construction: directional movement (+DM/-DM) is Wilder-smoothed and
    normalized by smoothed True Range to get +DI/-DI; DX = 100·|+DI−−DI|/(+DI+−DI);
    ADX is the Wilder-smoothed DX. All windows trail, so it is causal.
    """
    high, low, close = df["High"], df["Low"], df["Close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)

    tr = _true_range(high, low, close)
    atr_ = _wilder_rma(tr, period)
    plus_di = 100.0 * _wilder_rma(plus_dm, period) / atr_.replace(0.0, np.nan)
    minus_di = 100.0 * _wilder_rma(minus_dm, period) / atr_.replace(0.0, np.nan)
    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx_ = _wilder_rma(dx, period)
    return pd.DataFrame({"adx": adx_, "plus_di": plus_di, "minus_di": minus_di})


def realized_vol(close: pd.Series, window: int, ann_factor: float = 252.0) -> pd.Series:
    """Annualized rolling std of daily log returns (causal)."""
    logret = np.log(close / close.shift(1))
    return logret.rolling(window, min_periods=max(2, window // 2)).std() * np.sqrt(ann_factor)


def _trailing_pct_rank(s: pd.Series, window: int) -> pd.Series:
    """Percentile (0..1) of each value within its own trailing ``window`` (incl. self).

    Look-ahead-safe: only past + current observations enter the rank. Implemented
    as ``rolling.rank(pct=True)`` which ranks the last point against the window.
    """
    return s.rolling(window, min_periods=max(20, window // 5)).rank(pct=True)


# ── the classifier ───────────────────────────────────────────────────────────


def classify(
    df: pd.DataFrame,
    config: RegimeConfig | None = None,
    vix: pd.Series | None = None,
) -> pd.DataFrame:
    """Classify every bar of an OHLC frame into a market regime.

    Args:
        df: OHLC(V) frame indexed by date with ``High, Low, Close`` (``Open``/
            ``Volume`` optional). Adjusted prices recommended.
        config: thresholds; defaults are sensible for daily data.
        vix: optional external volatility index aligned to ``df.index`` (e.g.
            ``^VIX`` for US equities). When given, the high-vol decision blends
            the asset's own vol-rank with the index's vol-rank.

    Returns:
        A DataFrame aligned to ``df.index`` with the raw metrics and the labels:
        ``atr_pct, hist_vol, vol_rank, adx, plus_di, minus_di, ema_fast, sma_mid,
        sma_slow, vol_state, trend_state, direction, regime``. Rows before
        ``config.min_history`` get ``regime = None`` (insufficient history).
    """
    cfg = config or RegimeConfig()
    if not {"High", "Low", "Close"}.issubset(df.columns):
        raise ValueError("classify() needs High, Low, Close columns")

    close = df["Close"].astype(float)
    out = pd.DataFrame(index=df.index)

    # ── volatility axis ──────────────────────────────────────────────────────
    out["atr"] = atr(df, cfg.atr_period)
    out["atr_pct"] = out["atr"] / close
    out["hist_vol"] = realized_vol(close, cfg.vol_window, cfg.ann_factor)
    # rank realized vol within its own trailing window → adaptive, per-asset
    vol_rank = _trailing_pct_rank(out["hist_vol"], cfg.vol_rank_window)
    if vix is not None:
        vix_aligned = vix.reindex(df.index).ffill()
        vix_rank = _trailing_pct_rank(vix_aligned, cfg.vol_rank_window)
        # blend: a calm asset inside a stressed tape (or vice-versa) leans high
        vol_rank = (1.0 - cfg.vix_weight) * vol_rank + cfg.vix_weight * vix_rank
        out["vix"] = vix_aligned
        out["vix_rank"] = vix_rank
    out["vol_rank"] = vol_rank
    out["vol_state"] = np.where(vol_rank >= cfg.vol_high_pct, "high", "low")

    # ── trend axis ───────────────────────────────────────────────────────────
    adx_df = adx(df, cfg.adx_period)
    out["adx"] = adx_df["adx"]
    out["plus_di"] = adx_df["plus_di"]
    out["minus_di"] = adx_df["minus_di"]
    out["ema_fast"] = close.ewm(span=cfg.ema_fast, adjust=False, min_periods=cfg.ema_fast).mean()
    out["sma_mid"] = close.rolling(cfg.sma_mid, min_periods=cfg.sma_mid).mean()
    out["sma_slow"] = close.rolling(cfg.sma_slow, min_periods=cfg.sma_slow).mean()

    # MA-stack alignment → direction. Bullish = price above a rising stack.
    above_mid = close > out["sma_mid"]
    above_slow = close > out["sma_slow"]
    fast_above_mid = out["ema_fast"] > out["sma_mid"]
    bull = above_mid & above_slow & fast_above_mid
    bear = (~above_mid) & (~above_slow) & (~fast_above_mid)
    direction = np.where(bull, "bull", np.where(bear, "bear", "neutral"))
    out["direction"] = direction

    # Trending requires BOTH momentum (ADX) AND a coherent MA stack. ADX alone can
    # read high in a violent range; demanding stack alignment filters that out.
    adx_trending = out["adx"] >= cfg.adx_trend_min
    stack_aligned = bull | bear
    out["trend_state"] = np.where(adx_trending & stack_aligned, "trending", "sideways")

    # ── 2×2 cross → canonical regime ─────────────────────────────────────────
    vt = out["vol_state"].astype(str) + "|" + out["trend_state"].astype(str)
    regime_map = {
        "high|trending": "high_vol_trend",
        "low|trending": "low_vol_trend",
        "high|sideways": "high_vol_range",
        "low|sideways": "low_vol_range",
    }
    regime = vt.map(regime_map)

    # null out the warm-up where any core input is undefined
    warm = (
        out["sma_slow"].notna()
        & out["adx"].notna()
        & out["vol_rank"].notna()
        & (np.arange(len(out)) >= cfg.min_history)
    )
    regime = regime.where(warm)
    out["regime"] = regime
    out["regime_label"] = regime.map(REGIME_LABELS)
    out["regime_color"] = regime.map(REGIME_COLORS)
    return out


# ── snapshots, segments, performance ─────────────────────────────────────────


def current_regime(classified: pd.DataFrame) -> dict:
    """Latest-bar snapshot as a JSON-friendly dict (for the radar widget)."""
    valid = classified.dropna(subset=["regime"])
    if valid.empty:
        return {"regime": None, "label": "Unbekannt", "color": "#475569"}
    row = valid.iloc[-1]
    reg = str(row["regime"])
    direction = str(row["direction"])
    return {
        "asof": str(valid.index[-1].date()) if hasattr(valid.index[-1], "date") else str(valid.index[-1]),
        "regime": reg,
        "label": REGIME_LABELS.get(reg, reg),
        "color": REGIME_COLORS.get(reg, "#475569"),
        "description": REGIME_DESCRIPTIONS.get(reg, ""),
        "direction": direction,
        "direction_label": DIRECTION_LABELS.get(direction, direction),
        "vol_state": str(row["vol_state"]),
        "trend_state": str(row["trend_state"]),
        "metrics": {
            "adx": _f(row.get("adx")),
            "plus_di": _f(row.get("plus_di")),
            "minus_di": _f(row.get("minus_di")),
            "atr_pct": _f(row.get("atr_pct")),
            "hist_vol": _f(row.get("hist_vol")),
            "vol_rank": _f(row.get("vol_rank")),
        },
    }


def segments(classified: pd.DataFrame) -> list[dict]:
    """Compress consecutive equal-regime bars into spans for the timeline overlay.

    Returns ``[{regime, label, color, start, end, bars}]`` with ISO date strings,
    so the frontend can shade the price chart background per regime span.
    """
    valid = classified.dropna(subset=["regime"])
    if valid.empty:
        return []
    reg = valid["regime"].astype(str)
    # a new segment starts whenever the regime changes
    grp = (reg != reg.shift()).cumsum()
    spans: list[dict] = []
    for _, block in valid.groupby(grp):
        code = str(block["regime"].iloc[0])
        spans.append({
            "regime": code,
            "label": REGIME_LABELS.get(code, code),
            "color": REGIME_COLORS.get(code, "#475569"),
            "start": _isodate(block.index[0]),
            "end": _isodate(block.index[-1]),
            "bars": int(len(block)),
        })
    return spans


def regime_distribution(classified: pd.DataFrame) -> dict[str, dict]:
    """Share of time spent in each regime (for the radar summary)."""
    valid = classified.dropna(subset=["regime"])
    n = len(valid)
    counts = valid["regime"].value_counts().to_dict() if n else {}
    return {
        code: {
            "label": REGIME_LABELS[code],
            "color": REGIME_COLORS[code],
            "bars": int(counts.get(code, 0)),
            "pct": (float(counts.get(code, 0)) / n) if n else 0.0,
        }
        for code in REGIMES
    }


def regime_performance(
    returns: pd.Series,
    classified: pd.DataFrame,
    ann_factor: float = 252.0,
) -> dict[str, dict]:
    """Break a strategy's (or asset's) per-bar returns down by regime.

    This is the heart of the Alpha-Factory synergy: it proves *in which regimes*
    a strategy actually made or lost money, so the agent's claimed
    ``allowed_market_regimes`` can be checked against reality.

    Args:
        returns: per-bar returns (fractional), indexed like ``classified``.
        classified: output of :func:`classify` (must contain ``regime``).
        ann_factor: periods/year for annualizing mean/Sharpe.

    Returns:
        ``{regime_code: {label, color, n, total_return, mean_bps, ann_return,
        sharpe, win_rate, max_drawdown, pct_of_time}}`` for each of the 4 regimes.
    """
    reg = classified["regime"].reindex(returns.index)
    df = pd.DataFrame({"ret": returns.astype(float), "regime": reg}).dropna(subset=["regime"])
    n_total = len(df)
    perf: dict[str, dict] = {}
    for code in REGIMES:
        r = df.loc[df["regime"] == code, "ret"].dropna()
        perf[code] = _perf_block(r, code, n_total, ann_factor)
    return perf


def _perf_block(r: pd.Series, code: str, n_total: int, ann_factor: float) -> dict:
    n = int(len(r))
    if n == 0:
        return {"label": REGIME_LABELS[code], "color": REGIME_COLORS[code], "n": 0,
                "total_return": 0.0, "mean_bps": 0.0, "ann_return": 0.0, "sharpe": 0.0,
                "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown": 0.0, "pct_of_time": 0.0}
    equity = (1.0 + r).cumprod()
    dd = (equity / equity.cummax() - 1.0).min()
    sd = r.std()
    sharpe = (r.mean() / sd * np.sqrt(ann_factor)) if sd and not np.isnan(sd) else 0.0
    return {
        "label": REGIME_LABELS[code],
        "color": REGIME_COLORS[code],
        "n": n,
        "total_return": float(equity.iloc[-1] - 1.0),
        "mean_bps": float(r.mean() * 1e4),
        "ann_return": float(r.mean() * ann_factor),
        "sharpe": float(sharpe),
        "profit_factor": profit_factor(r),
        "win_rate": float((r > 0).mean()),
        "max_drawdown": float(dd),
        "pct_of_time": (n / n_total) if n_total else 0.0,
    }


# Profit-factor cap: a window with only winners has an undefined (infinite) profit
# factor; we report a large finite sentinel so the value stays JSON-safe and the
# routing comparison (``> threshold``) behaves sanely instead of hitting ``inf``.
PROFIT_FACTOR_CAP: float = 99.0


def profit_factor(r: pd.Series) -> float:
    """Gross profit / gross loss for a return stream (capped, look-ahead-free).

    Sum of positive returns divided by the absolute sum of negative returns. A stream
    with no losing bars returns :data:`PROFIT_FACTOR_CAP` (when it has wins) or ``0``
    (when it is empty/flat) so the result is always a finite float.
    """
    r = pd.Series(r, dtype="float64").dropna()
    if r.empty:
        return 0.0
    gross_win = float(r[r > 0].sum())
    gross_loss = float(-r[r < 0].sum())
    if gross_loss <= 0.0:
        return PROFIT_FACTOR_CAP if gross_win > 0.0 else 0.0
    return min(gross_win / gross_loss, PROFIT_FACTOR_CAP)


# ── small helpers ─────────────────────────────────────────────────────────────


def _f(x) -> float | None:
    try:
        v = float(x)
        return None if np.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return None


def _isodate(ts) -> str:
    return str(ts.date()) if hasattr(ts, "date") else str(ts)
