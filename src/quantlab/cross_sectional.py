"""Cross-sectional ranking engine — the relative-value paradigm.

Single-market timing (``backtest.py``) has two failure modes this project kept
hitting: low-frequency seasonals have too few trades for statistical power, and
high-frequency intraday direction is gross ≈ cost. The cross-sectional paradigm
sidesteps both: instead of asking *"when should I be long instrument X"* it asks
*"which of N instruments is most attractive right now — long the top, short the
bottom"*. Observations scale with the universe size, and the bet is relative
(market-neutral), so beta-masquerade (0015) and single-name fat tails shrink.

Look-ahead protection (same contract as the single-asset engine):
    A signal is computed from information up to and including the **close of the
    rebalance day** ``t``. The engine forward-fills the resulting target weights
    to daily frequency and then ``.shift(1)`` them, so a weight is only *held*
    from day ``t+1`` onward and earns that day's close-to-close return. Future
    leakage is structurally impossible.

Costs are turnover-based: every rebalance changes the weight vector, and the
summed absolute weight change across instruments (one side) is charged at
``cost_bps_per_side``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Signals (higher = more attractive = long). NaN = exclude (insufficient data). #
# --------------------------------------------------------------------------- #

def momentum_signal(
    prices: pd.DataFrame, lookback: int = 252, skip: int = 21
) -> pd.DataFrame:
    """Cross-sectional ``lookback``-minus-``skip`` momentum (default 12-1 month).

    The classic momentum signal: total return over the formation window, skipping
    the most recent ``skip`` days to avoid the short-term reversal. Computed daily
    so any rebalance schedule can sample it.

    ``signal_t = price_{t-skip} / price_{t-lookback} - 1``.
    """
    return prices.shift(skip) / prices.shift(lookback) - 1.0


# --------------------------------------------------------------------------- #
# Engine                                                                      #
# --------------------------------------------------------------------------- #

def _rebalance_dates(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Last actual trading day within each calendar period (``freq`` = M/Q/W)."""
    period = index.to_period(freq[0])
    last = pd.Series(index, index=index).groupby(period).last()
    return pd.DatetimeIndex(last.values)


def _target_weights(
    sig_row: pd.Series, quantile: float, long_short: bool, leg_weight: float, min_names: int
) -> pd.Series:
    """Map one cross-section of signal values to target weights.

    Long the top ``quantile`` fraction, short the bottom (if ``long_short``),
    equal-weight within each leg. Each leg sums to ``leg_weight`` in magnitude,
    so a long/short book is dollar-neutral (net 0, gross ``2*leg_weight``) and
    its return is exactly the top-minus-bottom spread.
    """
    out = pd.Series(0.0, index=sig_row.index)
    s = sig_row.dropna()
    n = s.shape[0]
    if n < min_names:
        return out
    k = max(1, int(round(quantile * n)))
    ranked = s.sort_values()
    longs = ranked.index[-k:]
    out[longs] = leg_weight / k
    if long_short:
        shorts = ranked.index[:k]
        out[shorts] = -leg_weight / k
    return out


def run_cross_sectional(
    prices: pd.DataFrame,
    signal: pd.DataFrame,
    rebalance: str = "ME",
    quantile: float = 0.25,
    long_short: bool = True,
    leg_weight: float = 1.0,
    cost_bps_per_side: float = 5.0,
    min_names: int = 4,
) -> dict:
    """Backtest a cross-sectional long/short (or long-only) ranking strategy.

    Args:
        prices: adjusted-close panel, columns = instruments, datetime index.
        signal: same-shaped panel; higher = long. NaN = exclude that name/day.
            Must be decision-time (no future data) — e.g. :func:`momentum_signal`.
        rebalance: pandas offset alias for the rebalance period (``"ME"`` month,
            ``"QE"`` quarter, ``"W"`` week). The last trading day of each period.
        quantile: top/bottom fraction selected per leg (0.25 = quartiles).
        long_short: if False, long-only top quantile (benchmark = equal-weight).
        leg_weight: gross capital per leg (1.0 => L/S gross 2.0, net 0.0; the
            return is the top-minus-bottom spread).
        cost_bps_per_side: transaction cost per unit turnover, basis points.
        min_names: minimum valid instruments required to take a position.

    Returns:
        dict with ``returns`` (net), ``gross_returns``, ``equity``, ``weights``
        (held, shifted), ``turnover`` (per-rebalance, two legs), ``benchmark``
        (equal-weight of the universe) and ``rebalance_dates``.
    """
    prices = prices.sort_index()
    rets = prices.pct_change()

    rb_dates = _rebalance_dates(prices.index, rebalance)
    sig_rb = signal.reindex(rb_dates)

    target = sig_rb.apply(
        lambda row: _target_weights(row, quantile, long_short, leg_weight, min_names),
        axis=1,
    )

    # Forward-fill targets to daily, then shift: decided at close t, held from t+1.
    w_daily = target.reindex(prices.index, method="ffill").fillna(0.0)
    held = w_daily.shift(1).fillna(0.0)

    gross_ret = (held * rets).reindex(columns=prices.columns).sum(axis=1)

    # Turnover = summed absolute daily weight change (nonzero only at rebalances).
    turnover_daily = held.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover_daily * (cost_bps_per_side / 1e4)
    net_ret = gross_ret - cost

    equity = (1.0 + net_ret).cumprod()
    benchmark = (1.0 + rets.mean(axis=1).fillna(0.0)).cumprod()

    return {
        "returns": net_ret,
        "gross_returns": gross_ret,
        "equity": equity,
        "weights": held,
        "turnover": turnover_daily[turnover_daily > 0],
        "benchmark": benchmark,
        "rebalance_dates": rb_dates,
    }


def cross_sectional_permutation_test(
    prices: pd.DataFrame,
    signal: pd.DataFrame,
    n_perm: int = 1000,
    seed: int | None = 42,
    metric: str = "sharpe",
    **engine_kwargs,
) -> dict:
    """Permutation test for cross-sectional rank skill.

    The right null here is *"the ranking carries no information"*: on each
    rebalance date we randomly **shuffle the signal across instruments**,
    destroying the rank-to-future-return link while preserving the marginal
    weight structure, the universe, the rebalance schedule and the realized
    returns. The p-value is the fraction of shuffles whose metric >= the real
    strategy's. Unlike the single-asset position-shuffle, this keeps the
    cross-sectional construction intact and only kills the signal's ordering.
    """
    from .metrics import sharpe_ratio

    def score(r: pd.Series) -> float:
        return sharpe_ratio(r) if metric == "sharpe" else float(r.mean())

    observed = score(run_cross_sectional(prices, signal, **engine_kwargs)["returns"])

    rng = np.random.default_rng(seed)
    rb_dates = _rebalance_dates(prices.index, engine_kwargs.get("rebalance", "ME"))
    sig_rb = signal.reindex(rb_dates)
    cols = signal.columns

    null = np.empty(n_perm)
    for i in range(n_perm):
        shuffled_rows = {}
        for dt, row in sig_rb.iterrows():
            vals = row.values.copy()
            shuffled_rows[dt] = pd.Series(rng.permutation(vals), index=cols)
        shuffled_rb = pd.DataFrame(shuffled_rows).T
        # Re-expand the shuffled rebalance signal to a daily panel for the engine.
        shuffled_daily = shuffled_rb.reindex(prices.index, method="ffill")
        null[i] = score(
            run_cross_sectional(prices, shuffled_daily, **engine_kwargs)["returns"]
        )

    p_value = float((np.sum(null >= observed) + 1) / (n_perm + 1))
    return {
        "observed": float(observed),
        "p_value": p_value,
        "null_mean": float(np.mean(null)),
        "null_std": float(np.std(null)),
        "n_perm": n_perm,
        "metric": metric,
    }
