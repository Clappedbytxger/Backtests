"""Performance and risk metrics for backtests.

All functions operate on a *daily* return series (simple returns, not log)
unless noted. Annualization uses ``TRADING_DAYS`` per year. A standardized
``summary`` dict is produced via :func:`compute_metrics` so every strategy is
evaluated identically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def total_return(returns: pd.Series) -> float:
    """Cumulative simple return over the whole period (e.g. 0.5 = +50%)."""
    return float((1.0 + returns).prod() - 1.0)


def cagr(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Compound Annual Growth Rate.

    Geometric mean return annualized. Robust to the actual number of periods.
    """
    n = returns.shape[0]
    if n == 0:
        return float("nan")
    growth = (1.0 + returns).prod()
    if growth <= 0:
        return -1.0
    years = n / periods_per_year
    return float(growth ** (1.0 / years) - 1.0)


def annual_volatility(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Annualized standard deviation of returns."""
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series,
    risk_free_annual: float = 0.02,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Annualized Sharpe ratio.

    Excess return over a constant annual risk-free rate (converted to a per-period
    rate), divided by the standard deviation, scaled by ``sqrt(periods_per_year)``.
    """
    if returns.std(ddof=1) == 0 or returns.empty:
        return float("nan")
    rf_per_period = (1.0 + risk_free_annual) ** (1.0 / periods_per_year) - 1.0
    excess = returns - rf_per_period
    return float(excess.mean() / excess.std(ddof=1) * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series,
    risk_free_annual: float = 0.02,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Annualized Sortino ratio (penalizes only downside volatility)."""
    if returns.empty:
        return float("nan")
    rf_per_period = (1.0 + risk_free_annual) ** (1.0 / periods_per_year) - 1.0
    excess = returns - rf_per_period
    downside = excess[excess < 0]
    dd = downside.std(ddof=1)
    if dd == 0 or np.isnan(dd):
        return float("nan")
    return float(excess.mean() / dd * np.sqrt(periods_per_year))


def equity_curve(returns: pd.Series, start_value: float = 1.0) -> pd.Series:
    """Cumulative equity (compounded) from a return series."""
    return start_value * (1.0 + returns).cumprod()


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Drawdown at each point: equity / running peak - 1 (<= 0)."""
    eq = equity_curve(returns)
    peak = eq.cummax()
    return eq / peak - 1.0


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline (negative number, e.g. -0.35)."""
    if returns.empty:
        return float("nan")
    return float(drawdown_series(returns).min())


def max_drawdown_duration(returns: pd.Series) -> int:
    """Longest stretch (in periods) spent below a prior equity peak."""
    dd = drawdown_series(returns)
    underwater = dd < 0
    longest = current = 0
    for flag in underwater:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return int(longest)


def calmar_ratio(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """CAGR divided by the absolute max drawdown."""
    mdd = max_drawdown(returns)
    if mdd == 0 or np.isnan(mdd):
        return float("nan")
    return float(cagr(returns, periods_per_year) / abs(mdd))


def compute_metrics(
    returns: pd.Series,
    risk_free_annual: float = 0.02,
    periods_per_year: int = TRADING_DAYS,
) -> dict:
    """Bundle the headline portfolio metrics into one dict.

    ``returns`` is the per-period return of the strategy (0 on flat days).
    Trade-level stats (win rate, profit factor, holding period) come from
    :func:`trade_stats` instead, since they need the trade log.
    """
    returns = returns.dropna()
    return {
        "total_return": total_return(returns),
        "cagr": cagr(returns, periods_per_year),
        "annual_volatility": annual_volatility(returns, periods_per_year),
        "sharpe": sharpe_ratio(returns, risk_free_annual, periods_per_year),
        "sortino": sortino_ratio(returns, risk_free_annual, periods_per_year),
        "calmar": calmar_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(returns),
        "max_drawdown_duration_days": max_drawdown_duration(returns),
        "n_periods": int(returns.shape[0]),
    }


def trade_stats(trades: pd.DataFrame) -> dict:
    """Trade-level statistics from a trade log.

    Expects columns ``pnl`` (net profit per trade in currency or fraction) and
    ``holding_days`` (calendar/trading days held).

    Returns win rate, profit factor, payoff (profit) ratio, expectancy,
    average holding period and trade counts.
    """
    if trades.empty:
        return {
            "n_trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "payoff_ratio": float("nan"),
            "expectancy": float("nan"),
            "avg_holding_days": float("nan"),
            "avg_win": float("nan"),
            "avg_loss": float("nan"),
        }

    pnl = trades["pnl"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_profit = wins.sum()
    gross_loss = -losses.sum()  # positive number

    win_rate = len(wins) / len(pnl)
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = -losses.mean() if len(losses) else 0.0  # positive magnitude

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
    expectancy = pnl.mean()

    return {
        "n_trades": int(len(pnl)),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "payoff_ratio": float(payoff_ratio),
        "expectancy": float(expectancy),
        "avg_holding_days": float(trades["holding_days"].mean()),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
    }
