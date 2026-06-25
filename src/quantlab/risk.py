"""Institutional risk engine — VaR, Expected Shortfall, correlation & allocation.

The math core behind the Quant-OS *Risk Desk* (``/api/risk`` → ``/risk`` dashboard).
Everything operates on a **panel of daily strategy returns** (a ``pandas.DataFrame``
indexed by date, one column per strategy, values = simple daily returns) so a book
of heterogeneous sleeves can be aggregated, stress-measured and capital-weighted on
one common footing.

Conventions
-----------
* **VaR / ES are reported as POSITIVE loss magnitudes** (a 1-day 95% VaR of 0.021
  means "we expect to lose more than 2.1% on ~1 trading day in 20"). Internally a
  return ``r`` is a loss of ``-r``.
* **Confidence** ``c`` ∈ (0,1): 0.95 / 0.99. **Horizon** ``h`` in trading days:
  results are scaled by √h (square-root-of-time), the standard desk convention.
* **Parametric** = variance-covariance (Gaussian) method; **historical** = empirical
  quantile of the realised return distribution.
* All optimisers are **long-only** (wᵢ ≥ 0, Σw = 1) — no shorting, matching the
  brief and how a prop book actually allocates capital.

Pure functions, no I/O. The trade-log → returns-panel adapter lives in
:mod:`quantlab.risk_book`; the FastAPI layer in :mod:`apps.api.risk`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform
from scipy.stats import norm

TRADING_DAYS = 252
_Z = norm.ppf  # standard-normal quantile (inverse CDF)


# ── single-stream measures ───────────────────────────────────────────────────


def historical_var(returns: pd.Series | np.ndarray, confidence: float = 0.95,
                   horizon: int = 1) -> float:
    """Historical (empirical) Value-at-Risk as a positive loss fraction.

    The ``(1-confidence)`` empirical quantile of the return distribution, negated
    to a loss and scaled to ``horizon`` days by √h.
    """
    r = _clean(returns)
    if r.size == 0:
        return float("nan")
    q = np.quantile(r, 1.0 - confidence)  # left-tail return (typically < 0)
    return float(max(-q, 0.0) * np.sqrt(horizon))


def parametric_var(returns: pd.Series | np.ndarray, confidence: float = 0.95,
                   horizon: int = 1, *, include_mean: bool = True) -> float:
    """Variance-covariance (Gaussian) VaR as a positive loss fraction.

    ``VaR = z·σ·√h − μ·h`` with ``z = Φ⁻¹(confidence)``. The drift term is tiny at
    short horizons but kept for correctness; pass ``include_mean=False`` to drop it.
    """
    r = _clean(returns)
    if r.size < 2:
        return float("nan")
    mu = float(r.mean()) if include_mean else 0.0
    sigma = float(r.std(ddof=1))
    var = _Z(confidence) * sigma * np.sqrt(horizon) - mu * horizon
    return float(max(var, 0.0))


def historical_es(returns: pd.Series | np.ndarray, confidence: float = 0.95,
                  horizon: int = 1) -> float:
    """Historical Expected Shortfall (Conditional VaR): mean loss in the tail.

    The average return *at or beyond* the VaR threshold, negated and √h-scaled —
    "when it breaches VaR, how bad is it on average".
    """
    r = _clean(returns)
    if r.size == 0:
        return float("nan")
    thr = np.quantile(r, 1.0 - confidence)
    tail = r[r <= thr]
    if tail.size == 0:
        tail = r[r <= np.quantile(r, max(1.0 - confidence, 1.0 / r.size))]
    if tail.size == 0:
        return float("nan")
    return float(max(-tail.mean(), 0.0) * np.sqrt(horizon))


def parametric_es(returns: pd.Series | np.ndarray, confidence: float = 0.95,
                  horizon: int = 1, *, include_mean: bool = True) -> float:
    """Gaussian Expected Shortfall: ``σ·φ(z)/(1−c)·√h − μ·h``."""
    r = _clean(returns)
    if r.size < 2:
        return float("nan")
    mu = float(r.mean()) if include_mean else 0.0
    sigma = float(r.std(ddof=1))
    z = _Z(confidence)
    es = sigma * norm.pdf(z) / (1.0 - confidence) * np.sqrt(horizon) - mu * horizon
    return float(max(es, 0.0))


def var_es(returns: pd.Series | np.ndarray, confidence: float = 0.95,
           horizon: int = 1) -> dict:
    """Both methods × VaR & ES for one stream — the per-cell payload for the UI."""
    return {
        "confidence": confidence,
        "horizon": horizon,
        "var_historical": historical_var(returns, confidence, horizon),
        "var_parametric": parametric_var(returns, confidence, horizon),
        "es_historical": historical_es(returns, confidence, horizon),
        "es_parametric": parametric_es(returns, confidence, horizon),
    }


# ── covariance / correlation ─────────────────────────────────────────────────


def correlation_matrix(panel: pd.DataFrame, *, min_overlap: int = 20) -> pd.DataFrame:
    """Pairwise Pearson correlation of daily returns (pairwise-complete).

    NaNs (a sleeve flat / not yet live) are dropped per pair. Pairs with fewer than
    ``min_overlap`` shared observations are set to NaN — a correlation off 3 common
    days is noise and must not drive an allocation.
    """
    corr = panel.corr(min_periods=min_overlap)
    return corr


def covariance_matrix(panel: pd.DataFrame, *, annualize: bool = False) -> pd.DataFrame:
    """Covariance of daily returns; ``annualize`` multiplies by 252."""
    cov = panel.cov()
    if annualize:
        cov = cov * TRADING_DAYS
    return cov


def rolling_correlation(panel: pd.DataFrame, a: str, b: str,
                        window: int = 90) -> pd.Series:
    """Rolling Pearson correlation between two sleeves — the 'is the diversification
    still there?' time series."""
    return panel[a].rolling(window, min_periods=max(10, window // 3)).corr(panel[b])


# ── portfolio aggregation ────────────────────────────────────────────────────


def portfolio_returns(panel: pd.DataFrame, weights: dict[str, float] | pd.Series) -> pd.Series:
    """Weighted daily return stream of the book (NaNs treated as 0 = sleeve flat)."""
    w = _weights_series(weights, panel.columns)
    return panel.reindex(columns=w.index).fillna(0.0).mul(w, axis=1).sum(axis=1)


def portfolio_vol(weights: dict[str, float] | pd.Series, cov: pd.DataFrame,
                  *, annualize: bool = False) -> float:
    """Portfolio standard deviation ``√(wᵀΣw)``."""
    w = _weights_series(weights, cov.columns).values
    sig = float(np.sqrt(max(w @ cov.values @ w, 0.0)))
    return sig * np.sqrt(TRADING_DAYS) if annualize else sig


def risk_contributions(weights: dict[str, float] | pd.Series,
                       cov: pd.DataFrame) -> pd.DataFrame:
    """Euler risk decomposition: marginal & component contribution to portfolio vol.

    Returns a frame with columns ``weight``, ``mcr`` (∂σ/∂wᵢ), ``contribution``
    (wᵢ·mcrᵢ, sums to σ_p) and ``pct`` (share of total risk). This is the table that
    exposes a sleeve eating most of the risk on a small allocation.
    """
    w = _weights_series(weights, cov.columns)
    cov_a = cov.loc[w.index, w.index].values
    wv = w.values
    sigma = float(np.sqrt(max(wv @ cov_a @ wv, 0.0)))
    if sigma <= 0:
        mcr = np.zeros_like(wv)
        contrib = np.zeros_like(wv)
        pct = np.zeros_like(wv)
    else:
        mcr = (cov_a @ wv) / sigma            # marginal contribution to risk
        contrib = wv * mcr                    # component contribution (Σ = sigma)
        pct = contrib / sigma
    return pd.DataFrame(
        {"weight": wv, "mcr": mcr, "contribution": contrib, "pct": pct},
        index=w.index,
    )


def diversification_ratio(weights: dict[str, float] | pd.Series,
                          cov: pd.DataFrame) -> dict:
    """Choueifaty diversification ratio and the implied benefit.

    ``DR = (w·σ) / σ_p`` (≥ 1). The weighted-average standalone vol over the realised
    portfolio vol; **benefit = 1 − σ_p/(w·σ)** is the fraction of risk netted away by
    diversification (0 = perfectly correlated book, → 1 = highly diversified).
    """
    w = _weights_series(weights, cov.columns)
    vols = np.sqrt(np.diag(cov.loc[w.index, w.index].values))
    wavg = float(w.values @ vols)
    sig = portfolio_vol(w, cov)
    dr = wavg / sig if sig > 0 else float("nan")
    return {
        "diversification_ratio": dr,
        "benefit": (1.0 - sig / wavg) if wavg > 0 else float("nan"),
        "weighted_avg_vol": wavg,
        "portfolio_vol": sig,
    }


# ── allocation models ────────────────────────────────────────────────────────


@dataclass
class Allocation:
    """One optimiser's output."""
    method: str
    weights: dict[str, float]
    exp_return: float = float("nan")   # annualised
    vol: float = float("nan")          # annualised
    sharpe: float = float("nan")
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "weights": self.weights,
            "exp_return": self.exp_return,
            "vol": self.vol,
            "sharpe": self.sharpe,
            "notes": self.notes,
        }


def mean_variance_optimization(panel: pd.DataFrame, *, objective: str = "max_sharpe",
                               rf: float = 0.0, w_max: float = 1.0) -> Allocation:
    """Long-only Markowitz optimiser (SLSQP) on annualised moments.

    ``objective``: ``"max_sharpe"`` (tangency portfolio) or ``"min_variance"``.
    Constraints: ``wᵢ ≥ 0``, ``Σw = 1``, optional per-sleeve cap ``w_max``. Falls back
    to an inverse-variance seed if the solver fails to converge.
    """
    cols = list(panel.columns)
    n = len(cols)
    mu = panel.mean().values * TRADING_DAYS
    cov = panel.cov().values * TRADING_DAYS
    cov = _ridge(cov)

    def vol(w):
        return float(np.sqrt(max(w @ cov @ w, 1e-18)))

    def neg_sharpe(w):
        return -(w @ mu - rf) / vol(w)

    from scipy.optimize import minimize

    obj = neg_sharpe if objective == "max_sharpe" else (lambda w: w @ cov @ w)
    bounds = [(0.0, w_max)] * n
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    x0 = _inverse_variance(cov)
    notes: list[str] = []
    try:
        res = minimize(obj, x0, method="SLSQP", bounds=bounds, constraints=cons,
                       options={"maxiter": 500, "ftol": 1e-10})
        w = res.x if res.success else x0
        if not res.success:
            notes.append(f"SLSQP not converged ({res.message}); inverse-variance seed used")
    except Exception as e:  # noqa: BLE001 - any solver issue degrades to the seed
        w = x0
        notes.append(f"optimiser error: {type(e).__name__}; inverse-variance seed used")
    w = _project_simplex(np.clip(w, 0, w_max))
    v = vol(w)
    er = float(w @ mu)
    return Allocation("mvo_" + objective, _wdict(cols, w), er, v,
                      (er - rf) / v if v > 0 else float("nan"), notes)


def hierarchical_risk_parity(panel: pd.DataFrame, *,
                             linkage_method: str = "single") -> Allocation:
    """Hierarchical Risk Parity (López de Prado 2016).

    No matrix inversion — therefore robust to the near-singular covariances that wreck
    MVO out-of-sample. Three stages: (1) tree-cluster the correlation distance matrix,
    (2) quasi-diagonalise to put similar sleeves adjacent, (3) recursively bisect,
    splitting capital between clusters by inverse cluster-variance.
    """
    cols = list(panel.columns)
    n = len(cols)
    cov = pd.DataFrame(_ridge(panel.cov().values), index=cols, columns=cols)
    if n == 1:
        return Allocation("hrp", {cols[0]: 1.0}, notes=["single asset"])

    corr = panel.corr().fillna(0.0).values.copy()
    np.fill_diagonal(corr, 1.0)
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))   # correlation distance
    np.fill_diagonal(dist, 0.0)
    link = linkage(squareform(dist, checks=False), method=linkage_method)
    order = _quasi_diag(link, n)
    ordered = [cols[i] for i in order]

    weights = pd.Series(1.0, index=ordered)
    clusters = [ordered]
    while clusters:
        clusters = [c[j:k] for c in clusters
                    for j, k in ((0, len(c) // 2), (len(c) // 2, len(c)))
                    if len(c) > 1]
        for i in range(0, len(clusters), 2):
            left, right = clusters[i], clusters[i + 1]
            v_left = _cluster_var(cov, left)
            v_right = _cluster_var(cov, right)
            alpha = 1.0 - v_left / (v_left + v_right)
            weights[left] *= alpha
            weights[right] *= 1.0 - alpha

    w = weights.reindex(cols).values
    w = w / w.sum()
    mu = panel.mean().values * TRADING_DAYS
    cov_a = cov.values * TRADING_DAYS
    v = float(np.sqrt(max(w @ cov_a @ w, 1e-18)))
    er = float(w @ mu)
    return Allocation("hrp", _wdict(cols, w), er, v,
                      er / v if v > 0 else float("nan"))


def equal_weight(panel: pd.DataFrame) -> Allocation:
    """1/N baseline — the honest benchmark every optimiser must beat."""
    cols = list(panel.columns)
    w = np.full(len(cols), 1.0 / len(cols))
    mu = panel.mean().values * TRADING_DAYS
    cov_a = _ridge(panel.cov().values) * TRADING_DAYS
    v = float(np.sqrt(max(w @ cov_a @ w, 1e-18)))
    er = float(w @ mu)
    return Allocation("equal_weight", _wdict(cols, w), er, v,
                      er / v if v > 0 else float("nan"))


# ── high-level summary ───────────────────────────────────────────────────────


def book_risk_summary(panel: pd.DataFrame, weights: dict[str, float] | pd.Series,
                      *, confidences=(0.95, 0.99), horizons=(1, 10),
                      capital: float | None = None) -> dict:
    """Full portfolio + per-strategy risk payload for the dashboard.

    Computes, on the supplied (already windowed) panel: portfolio VaR/ES across every
    confidence×horizon cell, the diversification benefit, annualised vol/return/Sharpe,
    and the same VaR/ES per sleeve. ``capital`` (book size) turns the headline VaR into
    a currency figure.
    """
    w = _weights_series(weights, panel.columns)
    port = portfolio_returns(panel, w)
    cov = covariance_matrix(panel)

    cells = {f"{int(c * 100)}_{h}d": var_es(port, c, h)
             for c in confidences for h in horizons}
    div = diversification_ratio(w, cov)
    vol_ann = float(port.std(ddof=1) * np.sqrt(TRADING_DAYS)) if port.size > 1 else float("nan")
    ret_ann = float(port.mean() * TRADING_DAYS)

    per_strategy = []
    rc = risk_contributions(w, cov)
    for col in panel.columns:
        s = panel[col].dropna()
        row = {
            "strategy": col,
            "weight": float(w.get(col, 0.0)),
            "n_obs": int(s.size),
            "vol_annual": float(s.std(ddof=1) * np.sqrt(TRADING_DAYS)) if s.size > 1 else float("nan"),
            "return_annual": float(s.mean() * TRADING_DAYS) if s.size else float("nan"),
            "sharpe": float(s.mean() / s.std(ddof=1) * np.sqrt(TRADING_DAYS))
            if s.size > 1 and s.std(ddof=1) > 0 else float("nan"),
            "risk_pct": float(rc.loc[col, "pct"]) if col in rc.index else float("nan"),
            "var_95_1d": historical_var(s, 0.95, 1),
            "es_95_1d": historical_es(s, 0.95, 1),
        }
        per_strategy.append(row)

    headline = cells["95_1d"]
    out = {
        "n_strategies": panel.shape[1],
        "n_obs": int(port.size),
        "span": {"start": _isodate(panel.index.min()), "end": _isodate(panel.index.max())},
        "portfolio": {
            "return_annual": ret_ann,
            "vol_annual": vol_ann,
            "sharpe": ret_ann / vol_ann if vol_ann and vol_ann == vol_ann and vol_ann > 0 else float("nan"),
            "var_es": cells,
            "diversification": div,
        },
        "per_strategy": per_strategy,
    }
    if capital:
        out["capital"] = capital
        out["portfolio"]["var_currency"] = {k: v["var_historical"] * capital for k, v in cells.items()}
        out["portfolio"]["es_currency"] = {k: v["es_historical"] * capital for k, v in cells.items()}
    return out


# ── internals ────────────────────────────────────────────────────────────────


def _clean(returns) -> np.ndarray:
    a = np.asarray(returns, dtype=float)
    return a[np.isfinite(a)]


def _weights_series(weights, columns) -> pd.Series:
    if isinstance(weights, pd.Series):
        w = weights.reindex(columns).fillna(0.0)
    else:
        w = pd.Series({c: float(weights.get(c, 0.0)) for c in columns})
    total = w.sum()
    return w / total if total > 0 else w


def _wdict(cols, w) -> dict[str, float]:
    return {c: float(x) for c, x in zip(cols, w)}


def _ridge(cov: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    """Add a tiny diagonal so a near-singular covariance stays invertible/PSD."""
    cov = np.asarray(cov, dtype=float)
    if cov.size == 0:
        return cov
    return cov + np.eye(cov.shape[0]) * (eps * max(np.trace(cov), 1e-8) / max(cov.shape[0], 1))


def _inverse_variance(cov: np.ndarray) -> np.ndarray:
    iv = 1.0 / np.clip(np.diag(cov), 1e-12, None)
    return iv / iv.sum()


def _project_simplex(w: np.ndarray) -> np.ndarray:
    s = w.sum()
    return w / s if s > 0 else np.full_like(w, 1.0 / len(w))


def _cluster_var(cov: pd.DataFrame, items: list[str]) -> float:
    """Inverse-variance-weighted variance of a sub-cluster (HRP step 3)."""
    sub = cov.loc[items, items].values
    iv = 1.0 / np.clip(np.diag(sub), 1e-12, None)
    w = iv / iv.sum()
    return float(w @ sub @ w)


def _quasi_diag(link: np.ndarray, n: int) -> list[int]:
    """Leaf order of the HRP dendrogram (similar sleeves end up adjacent)."""
    tree = to_tree(link, rd=False)
    return tree.pre_order(lambda x: x.id)


def _isodate(ts) -> str | None:
    try:
        return pd.Timestamp(ts).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None
