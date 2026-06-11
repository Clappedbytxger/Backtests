"""Information Coefficient (IC) and related signal quality metrics.

The IC is the rank correlation (Spearman) between a feature value at a release
date and the forward return of the asset over a specified horizon.  It measures
how predictive the feature is, independent of position sizing.

Workflow for a new fundamental hypothesis:
1. Build the feature series using ``features.py`` (PIT-correct, release-dated).
2. Call ``score_feature()`` to get IC by horizon, permutation p-values, and
   reliability.  This is the IC equivalent of ``significance.permutation_test()``.
3. Only if IC survives permutation at the 1W / 1M / 3M horizon does a full
   backtest (position sizing, cost model) make sense.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Core IC computation
# ---------------------------------------------------------------------------

def information_coefficient(
    feature: pd.Series,
    forward_returns: pd.Series,
    method: str = "spearman",
) -> float:
    """Rank-IC between a feature and forward returns on matched dates.

    Args:
        feature: feature values indexed by release date.  Only dates present
            in both ``feature`` and ``forward_returns`` are used.
        forward_returns: forward returns indexed by the *entry* date (= release
            date of the feature).  Compute these before calling, e.g.:
            ``fwd = prices["Close"].pct_change(horizon).shift(-horizon)``.
        method: ``"spearman"`` (rank IC, robust to outliers, default) or
            ``"pearson"`` (raw IC, sensitive to outliers).

    Returns:
        float: IC value in [-1, 1].  Returns NaN if fewer than 5 matched
        observations are available.
    """
    common = feature.index.intersection(forward_returns.index)
    f = feature.reindex(common).dropna()
    r = forward_returns.reindex(f.index).dropna()
    shared = f.index.intersection(r.index)
    if len(shared) < 5:
        return np.nan

    if method == "spearman":
        ic, _ = stats.spearmanr(f.reindex(shared), r.reindex(shared))
    else:
        ic, _ = stats.pearsonr(f.reindex(shared), r.reindex(shared))
    return float(ic)


def forward_returns(
    prices: pd.DataFrame | pd.Series,
    horizon_days: int,
    price_col: str = "Close",
) -> pd.Series:
    """Compute forward returns over ``horizon_days`` trading days.

    Args:
        prices: price DataFrame (must contain ``price_col``) or Series.
        horizon_days: number of trading days to look forward (e.g. 5 = 1W,
            22 = 1M, 66 = 3M).
        price_col: column to use if ``prices`` is a DataFrame.

    Returns:
        pd.Series: return from t to t+horizon, indexed by t.

    PIT note: this function is used to compute the *target*, not a signal.
    It looks forward by design — the IC measures how well the feature
    predicts this forward return.
    """
    close = prices[price_col] if isinstance(prices, pd.DataFrame) else prices
    return close.pct_change(horizon_days).shift(-horizon_days)


# ---------------------------------------------------------------------------
# IC at each release date
# ---------------------------------------------------------------------------

def ic_at_releases(
    feature_df: pd.DataFrame,
    prices: pd.DataFrame | pd.Series,
    feature_col: str,
    horizon_days: int,
    price_col: str = "Close",
) -> tuple[pd.Series, pd.Series]:
    """IC inputs: feature values and forward returns at each release date.

    For a monthly WASDE feature, this gives ~12 × n_years paired observations.
    For a weekly NASS feature, ~25 × n_years.

    Returns:
        (feature_at_release, fwd_return_at_release): two aligned pd.Series
        indexed by release date.  Use these directly in
        ``information_coefficient()`` or ``ic_permutation_test()``.
    """
    fwd = forward_returns(prices, horizon_days, price_col)
    releases = feature_df["release_date"].dropna().unique()
    releases = pd.DatetimeIndex(sorted(releases))

    feat_vals = []
    fwd_vals = []
    valid_dates = []

    price_start = fwd.index.min()  # don't process releases before price history
    seen_entries: set = set()      # guard against duplicate entry days

    for rd in releases:
        # Skip releases that fall before the price data — they all collapse
        # to the same first available trading day, creating duplicate indices.
        if rd < price_start:
            continue

        row = feature_df[feature_df["release_date"] == rd]
        if row.empty or feature_col not in row.columns:
            continue
        f_val = row[feature_col].iloc[-1]
        if pd.isna(f_val):
            continue
        # Forward return starting on the release date
        if rd not in fwd.index or pd.isna(fwd.loc[rd]):
            # Try to find the nearest trading day on or after release
            future = fwd.index[fwd.index >= rd]
            if future.empty or pd.isna(fwd.loc[future[0]]):
                continue
            rd_entry = future[0]
        else:
            rd_entry = rd

        # Guard: skip if this entry day already has an observation (safety net)
        if rd_entry in seen_entries:
            continue
        seen_entries.add(rd_entry)

        feat_vals.append(f_val)
        fwd_vals.append(fwd.loc[rd_entry])
        valid_dates.append(rd_entry)

    idx = pd.DatetimeIndex(valid_dates)
    return (
        pd.Series(feat_vals, index=idx, name=feature_col),
        pd.Series(fwd_vals,  index=idx, name=f"fwd_{horizon_days}d"),
    )


# ---------------------------------------------------------------------------
# IC decay over multiple horizons
# ---------------------------------------------------------------------------

def ic_decay(
    feature_df: pd.DataFrame,
    prices: pd.DataFrame | pd.Series,
    feature_col: str,
    horizons: tuple[int, ...] = (5, 22, 66),
    price_col: str = "Close",
) -> pd.DataFrame:
    """IC at multiple forward horizons (decay curve).

    Shows how far into the future the feature has predictive power.  A feature
    with IC(1W) > IC(3M) is a short-horizon signal; the reverse suggests slow
    information diffusion — the target regime for fundamental commodity signals.

    Returns:
        DataFrame with one row per horizon containing:
        ``horizon_days``, ``n_obs``, ``ic``, ``ic_t_stat``, ``ic_p_value``.
    """
    rows = []
    for h in horizons:
        f_vals, r_vals = ic_at_releases(
            feature_df, prices, feature_col, h, price_col
        )
        ic = information_coefficient(f_vals, r_vals)
        n = len(f_vals.dropna().index.intersection(r_vals.dropna().index))

        if n >= 5 and not np.isnan(ic):
            # t-statistic for IC under H0: IC=0, df = n-2
            t = ic * np.sqrt(n - 2) / np.sqrt(max(1 - ic**2, 1e-10))
            p = 2 * (1 - stats.t.cdf(abs(t), df=n - 2))
        else:
            t, p = np.nan, np.nan

        rows.append({
            "horizon_days": h,
            "n_obs":        n,
            "ic":           ic,
            "ic_t_stat":    t,
            "ic_p_value":   p,
        })

    return pd.DataFrame(rows).set_index("horizon_days")


# ---------------------------------------------------------------------------
# IC reliability
# ---------------------------------------------------------------------------

def ic_reliability(
    feature_df: pd.DataFrame,
    prices: pd.DataFrame | pd.Series,
    feature_col: str,
    horizon_days: int,
    price_col: str = "Close",
) -> dict:
    """Fraction of release periods where the feature correctly called direction.

    Unlike the overall IC, reliability counts: how often does a positive feature
    value (bullish signal) precede a positive forward return?  A 60 % hit rate
    is more tradeable than a high IC driven by a few outliers.

    Returns:
        dict with keys: ``n_obs``, ``ic``, ``hit_rate``, ``hit_rate_above_zero``
        (fraction of positive-feature dates with positive return),
        ``hit_rate_below_zero`` (fraction of negative-feature dates with
        negative return, i.e. the short side works too).
    """
    f_vals, r_vals = ic_at_releases(
        feature_df, prices, feature_col, horizon_days, price_col
    )
    common = f_vals.dropna().index.intersection(r_vals.dropna().index)
    f = f_vals.reindex(common)
    r = r_vals.reindex(common)

    ic = information_coefficient(f, r)
    n = len(common)

    positive_feature = f > 0
    negative_feature = f < 0

    above = (
        (r[positive_feature] > 0).sum() / positive_feature.sum()
        if positive_feature.sum() > 0 else np.nan
    )
    below = (
        (r[negative_feature] < 0).sum() / negative_feature.sum()
        if negative_feature.sum() > 0 else np.nan
    )
    overall = ((f > 0) == (r > 0)).mean()

    return {
        "n_obs":                n,
        "ic":                   ic,
        "hit_rate":             float(overall),
        "hit_rate_above_zero":  float(above) if not np.isnan(above) else np.nan,
        "hit_rate_below_zero":  float(below) if not np.isnan(below) else np.nan,
    }


# ---------------------------------------------------------------------------
# IC permutation test
# ---------------------------------------------------------------------------

def ic_permutation_test(
    feature_df: pd.DataFrame,
    prices: pd.DataFrame | pd.Series,
    feature_col: str,
    horizon_days: int,
    n_perm: int = 2000,
    price_col: str = "Close",
    seed: int | None = 42,
) -> dict:
    """Permutation test: is the observed IC significantly non-zero?

    Shuffles the feature values across release dates while keeping the
    forward returns fixed.  The p-value is the fraction of random permutations
    whose |IC| >= the observed |IC|.

    Args:
        n_perm: number of random permutations (2000 is sufficient for p < 0.05).

    Returns:
        dict with ``ic_observed``, ``p_value`` (two-sided), ``n_obs``,
        ``perm_mean_ic``, ``perm_std_ic``.

    This is the IC-analogue of ``significance.permutation_test()``.  A feature
    must clear p < 0.05 here before a full backtest is worth running.
    """
    rng = np.random.default_rng(seed)
    f_vals, r_vals = ic_at_releases(
        feature_df, prices, feature_col, horizon_days, price_col
    )
    common = f_vals.dropna().index.intersection(r_vals.dropna().index)
    f = f_vals.reindex(common).values
    r = r_vals.reindex(common).values
    n = len(f)

    if n < 5:
        return {"ic_observed": np.nan, "p_value": np.nan, "n_obs": n,
                "perm_mean_ic": np.nan, "perm_std_ic": np.nan}

    obs_ic, _ = stats.spearmanr(f, r)

    perm_ics = np.empty(n_perm)
    for i in range(n_perm):
        f_shuffled = rng.permutation(f)
        perm_ics[i], _ = stats.spearmanr(f_shuffled, r)

    p_value = float((np.abs(perm_ics) >= abs(obs_ic)).mean())

    return {
        "ic_observed":  float(obs_ic),
        "p_value":      p_value,
        "n_obs":        n,
        "perm_mean_ic": float(perm_ics.mean()),
        "perm_std_ic":  float(perm_ics.std()),
    }


# ---------------------------------------------------------------------------
# Full feature scorecard
# ---------------------------------------------------------------------------

def score_feature(
    feature_df: pd.DataFrame,
    prices: pd.DataFrame | pd.Series,
    feature_col: str,
    horizons: tuple[int, ...] = (5, 22, 66),
    n_perm: int = 500,
    price_col: str = "Close",
) -> dict:
    """Full IC scorecard for a single feature.

    Runs IC decay, reliability, and permutation test across all horizons.
    Use this as the first pass before running a full backtest.

    Args:
        n_perm: permutations per horizon (500 is sufficient for screening;
            use 2000 for final validation).

    Returns:
        dict with keys:
        ``ic_decay``     — DataFrame from ``ic_decay()``
        ``reliability``  — dict per horizon from ``ic_reliability()``
        ``permutation``  — dict per horizon from ``ic_permutation_test()``
        ``passes_screen``— True if ANY horizon has perm p < 0.10 (loose screen)
        ``best_horizon`` — horizon_days with lowest p_value

    This does NOT replace the full validation battery (DSR, OOS split,
    bootstrap CI, cost check).  It is the IC-level pre-screen that determines
    whether a backtest is worth running at all.
    """
    decay_df = ic_decay(feature_df, prices, feature_col, horizons, price_col)

    reliability = {}
    permutation = {}
    for h in horizons:
        reliability[h] = ic_reliability(
            feature_df, prices, feature_col, h, price_col
        )
        permutation[h] = ic_permutation_test(
            feature_df, prices, feature_col, h, n_perm, price_col
        )

    p_values = {h: permutation[h]["p_value"] for h in horizons
                if not np.isnan(permutation[h]["p_value"])}
    passes = any(p < 0.10 for p in p_values.values())
    best_h = min(p_values, key=p_values.get) if p_values else None

    return {
        "feature":       feature_col,
        "ic_decay":      decay_df,
        "reliability":   reliability,
        "permutation":   permutation,
        "passes_screen": passes,
        "best_horizon":  best_h,
    }


def print_scorecard(scorecard: dict) -> None:
    """Pretty-print the output of ``score_feature()``."""
    feature = scorecard["feature"]
    print(f"\n{'='*60}")
    print(f"IC Scorecard: {feature}")
    print(f"{'='*60}")

    decay = scorecard["ic_decay"]
    print("\nIC Decay:")
    print(f"  {'Horizon':>10}  {'N':>6}  {'IC':>8}  {'t-stat':>8}  {'p-value':>8}")
    for h, row in decay.iterrows():
        print(
            f"  {h:>10}  {int(row['n_obs']):>6}  "
            f"{row['ic']:>8.4f}  {row['ic_t_stat']:>8.3f}  "
            f"{row['ic_p_value']:>8.4f}"
        )

    print("\nReliability & Permutation:")
    print(f"  {'Horizon':>10}  {'HitRate':>8}  {'HitRate+':>9}  "
          f"{'HitRate-':>9}  {'Perm-p':>8}")
    for h in scorecard["reliability"]:
        rel = scorecard["reliability"][h]
        perm = scorecard["permutation"][h]
        print(
            f"  {h:>10}  {rel['hit_rate']:>8.3f}  "
            f"{rel['hit_rate_above_zero']:>9.3f}  "
            f"{rel['hit_rate_below_zero']:>9.3f}  "
            f"{perm['p_value']:>8.4f}"
        )

    passes = scorecard["passes_screen"]
    best_h = scorecard["best_horizon"]
    print(f"\nScreen result: {'PASS (run full backtest)' if passes else 'FAIL (no signal)'}")
    if best_h:
        print(f"Best horizon: {best_h} days")
    print("=" * 60)
