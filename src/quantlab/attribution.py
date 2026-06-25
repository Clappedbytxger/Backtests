"""Performance Attribution Engine — decompose returns into skill vs. market.

Answers the only question that matters: *are the profits real skill (alpha / market
timing) or just market tailwind (beta / sector drift)?* Two independent models:

1. **Factor regression (CAPM-style OLS)** — :func:`factor_regression` regresses a
   strategy's daily excess return on a benchmark's excess return to split it into
   **beta** (market sensitivity) and **risk-adjusted alpha** (the intercept, the part
   the benchmark does not explain), with t-stats / p-value / R². :func:`rolling_factor`
   tracks both through time so you can see beta drop in a crash (good risk management)
   or alpha erode (a decaying edge).

2. **Brinson-Fachler attribution** — :func:`brinson_fachler` splits a multi-asset
   portfolio's excess return over its benchmark into **allocation** (right sectors?),
   **selection** (right assets within a sector?) and **interaction** (the cross term).
   The identity ``Σ(allocation + selection + interaction) = R_portfolio − R_benchmark``
   holds *exactly* and is asserted by the tests.

All return inputs are simple daily returns. Annualisation uses 252 trading days.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252


def _rf_per_period(risk_free_annual: float) -> float:
    return (1.0 + risk_free_annual) ** (1.0 / TRADING_DAYS) - 1.0


# ── factor regression (OLS) ─────────────────────────────────────────────────────


@dataclass
class FactorResult:
    """CAPM-style factor-regression result for one strategy vs. one benchmark."""

    beta: float
    alpha_daily: float
    alpha_annual: float
    t_alpha: float
    p_alpha: float
    t_beta: float
    r_squared: float
    n: int
    corr: float
    mean_excess_annual: float

    def as_dict(self) -> dict:
        return {
            "beta": self.beta, "alpha_daily": self.alpha_daily,
            "alpha_annual": self.alpha_annual, "t_alpha": self.t_alpha,
            "p_alpha": self.p_alpha, "t_beta": self.t_beta,
            "r_squared": self.r_squared, "n": self.n, "corr": self.corr,
            "mean_excess_annual": self.mean_excess_annual,
        }


def factor_regression(
    strategy_ret: pd.Series,
    benchmark_ret: pd.Series,
    risk_free_annual: float = 0.02,
) -> FactorResult:
    """OLS of strategy excess return on benchmark excess return (CAPM).

    Model: ``(r_s − rf) = α + β·(r_b − rf) + ε``. Returns the slope ``β``, the
    intercept ``α`` (daily and annualised = ``α·252``), their t-statistics, the
    two-sided p-value of ``α`` and the regression R². Aligns the two series on their
    common dates and drops NaNs.
    """
    df = pd.concat([strategy_ret.rename("s"), benchmark_ret.rename("b")], axis=1).dropna()
    if len(df) < 3:
        raise ValueError("need at least 3 overlapping observations for a regression")
    rf = _rf_per_period(risk_free_annual)
    y = (df["s"] - rf).to_numpy()
    x = (df["b"] - rf).to_numpy()

    n = len(y)
    X = np.column_stack([np.ones(n), x])
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    alpha, beta = float(coef[0]), float(coef[1])

    resid = y - X @ coef
    dof = n - 2
    sigma2 = float(resid @ resid) / dof if dof > 0 else np.nan
    xtx_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(sigma2 * xtx_inv))
    t_alpha = alpha / se[0] if se[0] > 0 else np.nan
    t_beta = beta / se[1] if se[1] > 0 else np.nan
    p_alpha = float(2.0 * stats.t.sf(abs(t_alpha), dof)) if dof > 0 and np.isfinite(t_alpha) else np.nan

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    corr = float(np.corrcoef(x, y)[0, 1]) if n > 1 else np.nan

    return FactorResult(
        beta=beta, alpha_daily=alpha, alpha_annual=alpha * TRADING_DAYS,
        t_alpha=float(t_alpha), p_alpha=p_alpha, t_beta=float(t_beta),
        r_squared=float(r2), n=n, corr=corr,
        mean_excess_annual=float(y.mean() * TRADING_DAYS),
    )


def rolling_factor(
    strategy_ret: pd.Series,
    benchmark_ret: pd.Series,
    window: int = 63,
    risk_free_annual: float = 0.02,
) -> pd.DataFrame:
    """Rolling beta and (annualised) alpha over a trailing ``window`` (default ~1 quarter).

    ``β_t = Cov(s, b)/Var(b)`` and ``α_t = mean(s_excess) − β_t·mean(b_excess)`` over
    each window, computed vectorised and exactly. Returns a DataFrame indexed like the
    aligned inputs with columns ``beta`` and ``alpha_annual`` (NaN until the window
    fills).
    """
    df = pd.concat([strategy_ret.rename("s"), benchmark_ret.rename("b")], axis=1).dropna()
    rf = _rf_per_period(risk_free_annual)
    s = df["s"] - rf
    b = df["b"] - rf
    cov = s.rolling(window).cov(b)
    var = b.rolling(window).var()
    beta = cov / var
    alpha_daily = s.rolling(window).mean() - beta * b.rolling(window).mean()
    return pd.DataFrame({"beta": beta, "alpha_annual": alpha_daily * TRADING_DAYS})


# ── Brinson-Fachler attribution ─────────────────────────────────────────────────


@dataclass
class BrinsonEffect:
    sector: str
    w_p: float
    r_p: float
    w_b: float
    r_b: float
    allocation: float
    selection: float
    interaction: float
    total: float


@dataclass
class BrinsonResult:
    sectors: list[BrinsonEffect]
    portfolio_return: float
    benchmark_return: float
    active_return: float           # R_p − R_b
    allocation_total: float
    selection_total: float
    interaction_total: float
    residual: float = field(default=0.0)  # (sum of effects) − active_return, must be ~0

    def waterfall(self) -> list[dict]:
        """Cascade steps: benchmark → +allocation → +selection → +interaction → portfolio."""
        steps = [
            {"label": "Benchmark", "kind": "start", "value": self.benchmark_return,
             "cumulative": self.benchmark_return},
            {"label": "Allocation", "kind": "effect", "value": self.allocation_total},
            {"label": "Selection", "kind": "effect", "value": self.selection_total},
            {"label": "Interaction", "kind": "effect", "value": self.interaction_total},
            {"label": "Portfolio", "kind": "end", "value": self.portfolio_return,
             "cumulative": self.portfolio_return},
        ]
        cum = self.benchmark_return
        for st in steps[1:-1]:
            st["base"] = cum
            cum += st["value"]
            st["cumulative"] = cum
        return steps

    def as_dict(self) -> dict:
        return {
            "portfolio_return": self.portfolio_return,
            "benchmark_return": self.benchmark_return,
            "active_return": self.active_return,
            "allocation_total": self.allocation_total,
            "selection_total": self.selection_total,
            "interaction_total": self.interaction_total,
            "residual": self.residual,
            "sectors": [vars(s) for s in self.sectors],
            "waterfall": self.waterfall(),
        }


def brinson_fachler(
    weights_p: dict[str, float] | pd.Series,
    returns_p: dict[str, float] | pd.Series,
    weights_b: dict[str, float] | pd.Series,
    returns_b: dict[str, float] | pd.Series,
) -> BrinsonResult:
    """Brinson-Fachler single-period attribution across sectors.

    Per sector ``i`` (with ``R_b = Σ w_b,i·r_b,i`` the total benchmark return):

    * **allocation** = ``(w_p,i − w_b,i)·(r_b,i − R_b)`` — did over/under-weighting
      sectors with above/below-average benchmark returns pay off?
    * **selection**  = ``w_b,i·(r_p,i − r_b,i)`` — did our assets beat the sector?
    * **interaction**= ``(w_p,i − w_b,i)·(r_p,i − r_b,i)`` — the cross term.

    The three totals sum **exactly** to ``R_p − R_b`` (asserted in the tests via the
    ``residual`` field). Weights need not be pre-normalised — they are normalised to
    sum to 1 within each book first.
    """
    wp = pd.Series(weights_p, dtype=float)
    rp = pd.Series(returns_p, dtype=float)
    wb = pd.Series(weights_b, dtype=float)
    rb = pd.Series(returns_b, dtype=float)

    sectors = sorted(set(wp.index) | set(wb.index) | set(rp.index) | set(rb.index))
    wp = wp.reindex(sectors).fillna(0.0)
    wb = wb.reindex(sectors).fillna(0.0)
    rp = rp.reindex(sectors).fillna(0.0)
    rb = rb.reindex(sectors).fillna(0.0)

    if wp.sum() > 0:
        wp = wp / wp.sum()
    if wb.sum() > 0:
        wb = wb / wb.sum()

    R_p = float((wp * rp).sum())
    R_b = float((wb * rb).sum())

    effects = []
    for sec in sectors:
        alloc = float((wp[sec] - wb[sec]) * (rb[sec] - R_b))
        sel = float(wb[sec] * (rp[sec] - rb[sec]))
        inter = float((wp[sec] - wb[sec]) * (rp[sec] - rb[sec]))
        effects.append(BrinsonEffect(
            sector=sec, w_p=float(wp[sec]), r_p=float(rp[sec]),
            w_b=float(wb[sec]), r_b=float(rb[sec]),
            allocation=alloc, selection=sel, interaction=inter,
            total=alloc + sel + inter,
        ))

    alloc_t = sum(e.allocation for e in effects)
    sel_t = sum(e.selection for e in effects)
    inter_t = sum(e.interaction for e in effects)
    active = R_p - R_b
    residual = (alloc_t + sel_t + inter_t) - active

    return BrinsonResult(
        sectors=effects, portfolio_return=R_p, benchmark_return=R_b,
        active_return=active, allocation_total=alloc_t, selection_total=sel_t,
        interaction_total=inter_t, residual=residual,
    )


def classify_quadrant(alpha_annual: float, beta: float) -> str:
    """Four-quadrant label for the alpha-vs-beta scatter.

    ``premium`` = high alpha / low beta (top-left, the goal); ``leveraged`` = high
    alpha / high beta; ``defensive`` = low alpha / low beta; ``closet_beta`` = low
    alpha / high beta (paying for market exposure dressed as skill).
    """
    hi_alpha = alpha_annual > 0
    hi_beta = beta > 0.5
    if hi_alpha and not hi_beta:
        return "premium"
    if hi_alpha and hi_beta:
        return "leveraged"
    if not hi_alpha and not hi_beta:
        return "defensive"
    return "closet_beta"
