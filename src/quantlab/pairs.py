"""Statistical-arbitrage / cointegration explorer — pairs-trading engine.

Finds cointegrated pairs in a price panel via a two-stage scan (cheap correlation
pre-filter → Engle-Granger ADF), measures the spread's mean-reversion speed, and
turns the rolling spread z-score into long/short/exit signals.

Pipeline
--------
1. **Stage 1 — Pearson pre-filter** (:func:`correlation_prefilter`): the
   N·(N−1)/2 full ADF scan is expensive, so first rank pairs by the Pearson
   correlation of their LOG returns and keep only those above a threshold
   (default 0.70). This is a vectorized matrix op — milliseconds for hundreds
   of names.
2. **Stage 2 — Engle-Granger** (:func:`engle_granger`): for each surviving pair,
   OLS-regress ``log(A)`` on ``log(B)`` (+ intercept) to get the **hedge ratio**
   β, form the spread ``s = log(A) − β·log(B) − c``, and run the **Augmented
   Dickey-Fuller** test on ``s``. A pair is cointegrated when the ADF p-value
   < 0.05 (the spread is stationary ⇒ mean-reverting).
3. **Half-life** (:func:`half_life`): fit the discrete Ornstein-Uhlenbeck
   relation ``Δs_t = λ·s_{t-1} + ε`` by OLS; the mean-reversion half-life is
   ``−ln 2 / λ`` (in bars). Small half-life ⇒ the spread snaps back quickly.
4. **Signals** (:func:`zscore`, :func:`signal_from_z`): the rolling z-score of
   the spread; ``z > +2`` ⇒ short the spread (sell A / buy B), ``z < −2`` ⇒ long
   the spread (buy A / sell B), exit as ``|z|`` falls back through ~0.

Look-ahead note: the *research* statistics (hedge ratio, ADF, half-life) are
full-sample by design — they answer "is this pair cointegrated over the sample?".
The *tradable* z-score uses a trailing rolling window only (no future data), so
the signal series is decision-time honest; ``tests/test_pairs.py`` pins that.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller


@dataclass(frozen=True)
class PairStats:
    """Result of an Engle-Granger test on one ordered pair (A regressed on B)."""

    a: str
    b: str
    correlation: float
    hedge_ratio: float       # β: units of B shorted per unit A
    intercept: float
    adf_stat: float
    adf_pvalue: float
    half_life: float         # bars; NaN/inf if non-mean-reverting
    z_score: float           # latest rolling z-score of the spread
    n_obs: int

    @property
    def cointegrated(self) -> bool:
        return self.adf_pvalue < 0.05

    def signal(self, entry: float = 2.0) -> str:
        return signal_from_z(self.z_score, entry=entry)


# ── stage 1: correlation pre-filter ──────────────────────────────────────────


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Log returns of a wide price panel (columns = tickers)."""
    return np.log(prices / prices.shift(1)).dropna(how="all")


def correlation_prefilter(
    prices: pd.DataFrame, threshold: float = 0.70, min_overlap: int = 250
) -> list[tuple[str, str, float]]:
    """Stage-1 cheap filter: pairs whose log-return Pearson corr ≥ threshold.

    Returns ``[(a, b, corr), ...]`` sorted by descending correlation. Only the
    upper triangle is returned (each unordered pair once). Pairs with fewer than
    ``min_overlap`` jointly-observed bars are skipped (unreliable correlation).
    """
    rets = log_returns(prices)
    cols = list(rets.columns)
    corr = rets.corr(min_periods=min_overlap)
    out: list[tuple[str, str, float]] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            c = corr.iat[i, j]
            if pd.notna(c) and c >= threshold:
                out.append((cols[i], cols[j], float(c)))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


# ── stage 2: Engle-Granger cointegration ─────────────────────────────────────


def engle_granger(
    a: pd.Series, b: pd.Series, *, use_log: bool = True, z_window: int = 60
) -> PairStats | None:
    """Run the Engle-Granger two-step test for ordered pair (A on B).

    OLS-regresses A on B (+ intercept), forms the residual spread, ADF-tests it,
    and computes the OU half-life and the latest rolling z-score. Returns ``None``
    if the two series cannot be aligned to enough common observations.
    """
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(df) < max(z_window + 5, 60):
        return None
    pa = np.log(df["a"]) if use_log else df["a"]
    pb = np.log(df["b"]) if use_log else df["b"]

    # OLS: pa = c + beta * pb + resid  → hedge ratio = beta
    X = sm.add_constant(pb.values)
    model = sm.OLS(pa.values, X).fit()
    intercept, beta = float(model.params[0]), float(model.params[1])
    spread = pd.Series(pa.values - beta * pb.values - intercept, index=df.index)

    try:
        adf_stat, adf_p, *_ = adfuller(spread.values, maxlag=1, autolag="AIC")
    except Exception:  # noqa: BLE001 - degenerate spread (constant) ⇒ not cointegrated
        return None

    corr = float(np.corrcoef(pa.values, pb.values)[0, 1])
    hl = half_life(spread)
    z = zscore(spread, window=z_window)
    z_last = float(z.iloc[-1]) if len(z.dropna()) else float("nan")
    return PairStats(
        a=str(a.name), b=str(b.name), correlation=corr,
        hedge_ratio=beta, intercept=intercept,
        adf_stat=float(adf_stat), adf_pvalue=float(adf_p),
        half_life=float(hl), z_score=z_last, n_obs=int(len(df)),
    )


def spread_series(a: pd.Series, b: pd.Series, hedge_ratio: float, intercept: float,
                  *, use_log: bool = True) -> pd.Series:
    """Reconstruct the spread ``A − β·B − c`` (log prices by default)."""
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    pa = np.log(df["a"]) if use_log else df["a"]
    pb = np.log(df["b"]) if use_log else df["b"]
    return pd.Series(pa.values - hedge_ratio * pb.values - intercept, index=df.index)


# ── half-life via Ornstein-Uhlenbeck ─────────────────────────────────────────


def half_life(spread: pd.Series) -> float:
    """Mean-reversion half-life (bars) from the discrete OU fit Δs = λ·s_{t-1}+ε.

    ``half_life = −ln 2 / λ``. Returns ``+inf`` when λ ≥ 0 (no mean reversion).
    """
    s = spread.dropna()
    if len(s) < 10:
        return float("inf")
    s_lag = s.shift(1).dropna()
    ds = (s - s.shift(1)).dropna()
    s_lag = s_lag.loc[ds.index]
    X = sm.add_constant(s_lag.values)
    lam = float(sm.OLS(ds.values, X).fit().params[1])
    if lam >= 0:
        return float("inf")
    return float(-np.log(2) / lam)


# ── z-score + signals ─────────────────────────────────────────────────────────


def zscore(spread: pd.Series, window: int = 60) -> pd.Series:
    """Trailing rolling z-score of the spread (look-ahead-safe).

    Uses a rolling mean/std over ``window`` trailing bars only, so ``z[t]`` is
    knowable at the close of ``t``. ``window<=0`` uses an expanding window.
    """
    if window and window > 0:
        mu = spread.rolling(window, min_periods=max(10, window // 2)).mean()
        sd = spread.rolling(window, min_periods=max(10, window // 2)).std()
    else:
        mu = spread.expanding(min_periods=20).mean()
        sd = spread.expanding(min_periods=20).std()
    return (spread - mu) / sd.replace(0.0, np.nan)


def signal_from_z(z: float, entry: float = 2.0, exit_band: float = 0.5) -> str:
    """Map a z-score to a discrete signal.

    ``short_spread`` (sell A / buy B) when z ≥ +entry; ``long_spread`` (buy A /
    sell B) when z ≤ −entry; ``neutral`` otherwise (inside the band).
    """
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return "neutral"
    if z >= entry:
        return "short_spread"
    if z <= -entry:
        return "long_spread"
    return "neutral"


def signal_series(z: pd.Series, entry: float = 2.0, exit_band: float = 0.5) -> pd.Series:
    """Stateful position series from a z-score path: +1 long spread, -1 short, 0 flat.

    Enters at ``|z| ≥ entry``, holds until the spread reverts inside ``exit_band``
    (z crosses ~0), so it captures the full reversion rather than flipping each bar.
    Causal: only uses ``z`` up to each bar.
    """
    pos = np.zeros(len(z))
    state = 0
    vals = z.values
    for i, zi in enumerate(vals):
        if np.isnan(zi):
            pos[i] = state
            continue
        if state == 0:
            if zi >= entry:
                state = -1   # short the spread
            elif zi <= -entry:
                state = +1   # long the spread
        elif state == +1 and zi >= -exit_band:
            state = 0
        elif state == -1 and zi <= exit_band:
            state = 0
        pos[i] = state
    return pd.Series(pos, index=z.index)


# ── spread-reversion backtest (turns "cointegrated" into "tradable edge") ─────

# An edge must clear all three: profitable net of cost, a positive OUT-of-sample
# Sharpe, and enough trades to mean something. Tunable, but deliberately modest.
EDGE_MIN_OOS_SHARPE = 0.5
EDGE_MIN_TRADES = 8


def backtest_pair(
    a: pd.Series,
    b: pd.Series,
    *,
    z_window: int = 60,
    entry: float = 2.0,
    exit_band: float = 0.5,
    cost_bps: float = 5.0,
    is_frac: float = 0.7,
    use_log: bool = True,
    with_curve: bool = False,
) -> dict | None:
    """Backtest the z-score mean-reversion rule on ONE pair, net of costs.

    This is what separates "cointegrated in-sample" from a *tradable edge*: it
    trades the spread (long-spread = long A / short β·B, and the mirror), charges
    a round-trip cost on BOTH legs, and reports an honest IS/OOS split.

    Honesty guardrails:
      * the hedge ratio β is fitted on the IN-SAMPLE slice ONLY and applied to the
        whole series — so the OOS Sharpe is not inflated by full-sample β fit;
      * the z-score uses a trailing rolling window (no future data);
      * the position is shifted +1 bar (decide at close ``t``, hold from ``t+1``);
      * cost = turnover · (1+|β|) · ``cost_bps`` (both legs traded each entry/exit).

    Returns a metrics dict (``None`` if the pair can't be aligned). ``is_edge`` is
    True only if OOS Sharpe ≥ :data:`EDGE_MIN_OOS_SHARPE`, trades ≥
    :data:`EDGE_MIN_TRADES` and the net total return is positive. ``with_curve``
    adds the net equity curve (for the detail chart).
    """
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    n = len(df)
    if n < max(z_window + 30, 120):
        return None
    pa = np.log(df["a"]) if use_log else df["a"]
    pb = np.log(df["b"]) if use_log else df["b"]

    split = int(n * is_frac)
    # β on IS only → honest OOS
    X_is = sm.add_constant(pb.iloc[:split].values)
    fit = sm.OLS(pa.iloc[:split].values, X_is).fit()
    intercept, beta = float(fit.params[0]), float(fit.params[1])

    spread = pd.Series(pa.values - beta * pb.values - intercept, index=df.index)
    z = zscore(spread, window=z_window)
    pos = signal_series(z, entry=entry, exit_band=exit_band)

    held = pos.shift(1).fillna(0.0)             # execution lag
    dspread = spread.diff().fillna(0.0)          # ≈ combined per-bar leg return
    gross = held * dspread
    turnover = held.diff().abs().fillna(held.abs())
    cost = turnover * (1.0 + abs(beta)) * (cost_bps / 1e4)
    net = gross - cost

    years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-9)
    ppy = n / years
    ann = np.sqrt(ppy)

    def _sh(r: pd.Series) -> float:
        r = r.dropna()
        sd = r.std(ddof=1)
        return float(r.mean() / sd * ann) if len(r) > 5 and sd > 0 else 0.0

    # Additive equity: the spread PnL is a difference of (log-)prices, so per-bar
    # net is a return-scale increment — sum it (compounding a price-unit spread
    # would blow up and is not how a market-neutral spread book accrues).
    cum = net.cumsum()
    level = 1.0 + cum
    dd = float((level / level.cummax() - 1.0).min())
    equity = level
    is_net, oos_net = net.iloc[:split], net.iloc[split:]

    # per-trade stats from the executed (shifted) position
    trades = _trade_pnls(held, dspread, turnover, beta, cost_bps)
    n_trades = len(trades)
    win_rate = float(np.mean([t > 0 for t in trades])) if trades else 0.0

    oos_sharpe = _sh(oos_net)
    total_net = float(net.sum())               # cumulative spread return (additive)
    is_edge = bool(oos_sharpe >= EDGE_MIN_OOS_SHARPE and n_trades >= EDGE_MIN_TRADES and total_net > 0)

    out = {
        "beta_is": beta,
        "split_date": str(df.index[split].date()) if 0 < split < n else None,
        "sharpe_full": _sh(net),
        "sharpe_is": _sh(is_net),
        "sharpe_oos": oos_sharpe,
        "total_return": total_net,
        "oos_return": float(oos_net.sum()),
        "max_drawdown": dd,
        "n_trades": int(n_trades),
        "win_rate": win_rate,
        "cost_bps": cost_bps,
        "is_edge": is_edge,
    }
    if with_curve:
        step = max(1, n // 900)
        out["curve"] = [{"t": str(ix.date()), "equity": round(float(v), 5)}
                        for ix, v in equity.iloc[::step].items()]
        out["split_index_frac"] = is_frac
    return out


def _trade_pnls(held: pd.Series, dspread: pd.Series, turnover: pd.Series,
                beta: float, cost_bps: float) -> list[float]:
    """Net PnL of each closed trade (entry→exit episode of constant position)."""
    leg_cost = (1.0 + abs(beta)) * (cost_bps / 1e4)
    trades: list[float] = []
    cur = 0.0
    state = 0.0
    hv, dv, tv = held.values, dspread.values, turnover.values
    for i in range(len(hv)):
        if hv[i] != state:
            if state != 0.0:                 # closing a position
                cur -= tv[i] * leg_cost      # exit cost
                trades.append(cur)
            cur = 0.0
            if hv[i] != 0.0:                 # opening a new one
                cur -= tv[i] * leg_cost      # entry cost
            state = hv[i]
        if state != 0.0:
            cur += state * dv[i]
    if state != 0.0:                          # mark open trade to last bar
        trades.append(cur)
    return trades


# ── the orchestrating scan ────────────────────────────────────────────────────


def scan_pairs(
    prices: pd.DataFrame,
    *,
    corr_threshold: float = 0.70,
    adf_threshold: float = 0.05,
    z_window: int = 60,
    max_pairs: int | None = None,
    use_log: bool = True,
) -> list[PairStats]:
    """Full two-stage scan over a price panel → cointegrated pairs by |z|.

    Stage 1 ranks candidate pairs by correlation; stage 2 runs Engle-Granger on
    each candidate (orienting A/B so the regression is stable). Returns the
    cointegrated pairs (ADF p < ``adf_threshold``) sorted by absolute current
    z-score descending — the biggest live dislocations on top.
    """
    candidates = correlation_prefilter(prices, threshold=corr_threshold)
    if max_pairs:
        candidates = candidates[:max_pairs]
    results: list[PairStats] = []
    for a, b, _corr in candidates:
        st = engle_granger(prices[a], prices[b], use_log=use_log, z_window=z_window)
        if st is None:
            continue
        # orient by the more stationary direction (lower ADF p)
        st_rev = engle_granger(prices[b], prices[a], use_log=use_log, z_window=z_window)
        if st_rev is not None and st_rev.adf_pvalue < st.adf_pvalue:
            st = st_rev
        if st.adf_pvalue < adf_threshold:
            results.append(st)
    results.sort(key=lambda s: abs(s.z_score) if not np.isnan(s.z_score) else -1, reverse=True)
    return results
