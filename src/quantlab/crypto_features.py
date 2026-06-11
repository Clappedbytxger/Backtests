"""Theory-/evidence-driven crypto cross-section features (PIT-safe, Track A).

Every feature has a documented cause and a literature anchor (roadmap Teil 3;
Cakici et al. 2024, Liu & Tsyvinski 2021, Liu/Tsyvinski/Wu 2022); nothing is
mined. All panels are daily UTC (crypto trades 24/7 — windows are calendar
days, 1 week = 7 rows), columns = Binance pairs, and decision-time: a value
at date ``t`` uses bars up to and including the close of UTC day ``t``. The
portfolio engine additionally ``shift(1)``s holdings.

Feature inventory
-----------------
mom_7/14/28/56/84   1/2/4/8/12-week returns — momentum is the strongest,
                    most persistent crypto factor; the 1-week column doubles
                    as short-term reversal (the model decides the sign).
size                log PIT market cap (weekly CMC snapshot, applied with a
                    1-day lag) — small-cap premium.
amihud_21           Amihud illiquidity |ret|/dollar-volume, 21d mean —
                    dominant predictor per Cakici et al.
vol_30 / semivol_30 realized vol and downside semi-vol (annualized, 365d).
volume_trend        log(7d avg dollar-volume / 84d avg) — Babiak-style
                    volume dynamics.
max_ret_28          max daily return in 4 weeks — salience / lottery demand
                    (Cai & Zhao).
past_alpha_90       rolling 90d alpha vs the PIT cap-weighted market factor —
                    documented dominant (Cakici et al.).
beta_90             the matching market beta (risk conditioning).

Funding carry and on-chain features are deliberately deferred (roadmap
Phase 4) — they need separate sources (Coinglass/DefiLlama) and must prove
*incremental* value over this base panel.

Targets: ``fwd_{7,14,28}`` raw forward returns (portfolio PnL) and their
per-date cross-sectional rank transform ``y`` (regression target). Forward
returns are computed on the close panel and require the coin to still print
a bar at t+h; a coin that dies inside the window has a NaN target and simply
drops out of the training rows (its death still hits the *portfolio* through
the return panel — the honest split).

Cost model: per-side bps staged by 21d median dollar volume (Binance spot
taker 10 bps + spread/impact by liquidity class). Small caps are where the
edge lives AND where the cost wall stands — modeled conservatively.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MOM_WINDOWS = (7, 14, 28, 56, 84)
TARGET_HORIZONS = (7, 14, 28)
ANN_DAYS = 365  # 24/7 market


def rank_transform(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-date cross-sectional rank into (-0.5, 0.5); NaNs stay NaN."""
    n = panel.notna().sum(axis=1)
    r = panel.rank(axis=1)
    return r.sub(0.5).div(n, axis=0).sub(0.5)


def market_return(ret: pd.DataFrame, mcap: pd.DataFrame) -> pd.Series:
    """PIT cap-weighted market factor over the current members.

    Weights are the (already 1-day-lagged) PIT market caps, additionally
    ``shift(1)``-ed so day t's market return is weighted with day t-1
    information only.
    """
    w = mcap.shift(1)
    w = w.where(ret.notna())
    return (ret * w).sum(axis=1) / w.sum(axis=1)


def rolling_alpha_beta(
    ret: pd.DataFrame, mkt: pd.Series, window: int = 90, min_periods: int = 60
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling OLS alpha/beta of each coin vs the market factor, vectorized
    via rolling moments (no per-coin loop)."""
    m = mkt.reindex(ret.index)
    mm = pd.DataFrame({c: m for c in ret.columns}, index=ret.index).where(ret.notna())

    r_mean = ret.rolling(window, min_periods=min_periods).mean()
    m_mean = mm.rolling(window, min_periods=min_periods).mean()
    rm_mean = (ret * mm).rolling(window, min_periods=min_periods).mean()
    m2_mean = (mm**2).rolling(window, min_periods=min_periods).mean()

    cov = rm_mean - r_mean * m_mean
    var = m2_mean - m_mean**2
    beta = cov / var.replace(0.0, np.nan)
    alpha = (r_mean - beta * m_mean) * ANN_DAYS
    return alpha, beta


def build_feature_panels(panels: dict) -> dict:
    """All feature/target panels from :func:`crypto_xsection.get_price_panels`.

    Every feature is masked to ``membership_daily`` — a coin outside the PIT
    top-N at decision time contributes neither features nor targets.

    Returns dict with ``features`` ({name: panel}), ``targets_raw``,
    ``targets_rank``, ``returns``, ``vol30``, ``dvol_med21``, ``days``.
    """
    close, ret = panels["close"], panels["ret"]
    memb, mcap = panels["membership_daily"], panels["mcap_daily"]
    dvol = panels["dollar_volume"]
    days = close.index

    feats: dict[str, pd.DataFrame] = {}

    for k in MOM_WINDOWS:
        feats[f"mom_{k}"] = close.pct_change(k)

    feats["size"] = np.log(mcap)

    # Amihud on observed bars only; log-compress the heavy tail (rank
    # transform later removes scale anyway, the log just stabilizes means).
    daily_illiq = (ret.abs() / dvol.replace(0.0, np.nan)) * 1e9
    feats["amihud_21"] = np.log1p(daily_illiq.rolling(21, min_periods=14).mean())

    vol30 = ret.rolling(30, min_periods=20).std() * np.sqrt(ANN_DAYS)
    feats["vol_30"] = vol30
    feats["semivol_30"] = ret.where(ret < 0).rolling(30, min_periods=8).std() * np.sqrt(ANN_DAYS)

    feats["volume_trend"] = np.log(
        dvol.rolling(7, min_periods=5).mean()
        / dvol.rolling(84, min_periods=56).mean()
    )
    feats["max_ret_28"] = ret.rolling(28, min_periods=20).max()

    mkt = market_return(ret, mcap)
    alpha, beta = rolling_alpha_beta(ret, mkt)
    feats["past_alpha_90"] = alpha
    feats["beta_90"] = beta

    feats = {name: p.where(memb) for name, p in feats.items()}

    targets_raw = {h: close.pct_change(h).shift(-h).where(memb) for h in TARGET_HORIZONS}
    targets_rank = {h: rank_transform(t) for h, t in targets_raw.items()}

    return {
        "features": feats,
        "targets_raw": targets_raw,
        "targets_rank": targets_rank,
        "returns": ret,
        "market": mkt,
        "vol30": vol30,
        "dvol_med21": dvol.rolling(21, min_periods=14).median(),
        "days": days,
    }


def assemble_design_matrix(
    fp: dict,
    horizon: int = 7,
    rank_features: bool = True,
    sample_freq: str = "W",
    min_names: int = 20,
    require_target: bool = True,
    extra_features: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Long-format design matrix: rows = (date, pair), columns = features + y.

    Weekly sampling keeps the 7d target non-overlapping (CPCV purging still
    handles the longer horizons). Dates with fewer than ``min_names`` valid
    rows are dropped — a thin cross-section cannot be ranked meaningfully.

    ``require_target=False`` keeps rows whose forward label is not yet
    realized (the last ``horizon`` days) — needed for live scoring; training
    must keep the default ``True``.

    ``extra_features`` (e.g. :func:`phase4_features` output) are stacked and
    rank-transformed exactly like the base features; their NaNs do not drop
    rows (incremental-value tests need identical row sets).
    """
    feats = dict(fp["features"])
    if extra_features:
        feats.update(extra_features)
    days = fp["days"]
    if sample_freq == "W":
        from .cross_sectional import _rebalance_dates

        dates = _rebalance_dates(days, "W")
    else:
        dates = days

    blocks = []
    for name, panel in feats.items():
        p = rank_transform(panel) if rank_features else panel
        blocks.append(p.reindex(dates).stack().rename(name))
    y = fp["targets_rank"][horizon].reindex(dates).stack().rename("y")
    fwd = fp["targets_raw"][horizon].reindex(dates).stack().rename("fwd_ret")

    df = pd.concat(blocks + [y, fwd], axis=1)
    df.index.names = ["date", "pair"]
    subset = ["y", "mom_28", "size"] if require_target else ["mom_28", "size"]
    df = df.dropna(subset=subset)

    counts = df.groupby("date").size()
    keep = counts.index[counts >= min_names]
    return df[df.index.get_level_values("date").isin(keep)]


# ---------------------------------------------------------------------------
# Phase-4 features: perp funding carry + on-chain TVL trend (roadmap Teil 3)
# ---------------------------------------------------------------------------

def phase4_features(panels: dict) -> dict[str, pd.DataFrame]:
    """Funding-carry and TVL-trend panels, aligned to the price panels.

    funding_7    7d sum of daily perp funding — the crypto-specific carry
                 (longs pay shorts when positive => crowded longs, negative
                 expected return; Cakici 2024 / roadmap "Funding-Carry").
    funding_z    7d funding vs its trailing 90d distribution (crowding
                 *change* rather than level).
    tvl_chg_28   28d log change of the coin's own chain TVL (adoption trend,
                 Liu & Tsyvinski network factors) — only for coins that ARE
                 an L1/L2 gas token; NaN elsewhere (LightGBM handles NaN).

    PIT: funding events of UTC day t post at 00/08/16h — known at close t.
    TVL is lagged one day (DefiLlama may restate the running day).
    Coins without a Binance perp have NaN funding before perp listing — the
    perp launch date is itself historical information, no leak.
    """
    from .crypto_xsection import get_chain_map, get_chain_tvl, get_funding_panel

    memb = panels["membership_daily"]
    days = memb.index
    cols = list(memb.columns)
    parents = [c.split("~")[0] for c in cols]

    fund_daily = get_funding_panel(sorted(set(parents)), progress=False)
    fund = fund_daily.reindex(columns=parents)
    fund.columns = cols
    fund = fund.reindex(days)

    feats: dict[str, pd.DataFrame] = {}
    f7 = fund.rolling(7, min_periods=5).sum()
    feats["funding_7"] = f7
    mu = f7.rolling(90, min_periods=45).mean()
    sd = f7.rolling(90, min_periods=45).std()
    feats["funding_z"] = (f7 - mu) / sd

    chain_map = get_chain_map()
    tvl_cols = {}
    for col, parent in zip(cols, parents):
        base = parent[:-4]  # strip USDT
        chain = chain_map.get(base)
        if not chain:
            continue
        try:
            s = get_chain_tvl(chain)
        except Exception:
            continue
        tvl_cols[col] = s
    tvl = pd.DataFrame(tvl_cols).reindex(days).shift(1)
    tvl = tvl.reindex(columns=cols)
    feats["tvl_chg_28"] = np.log(tvl.where(tvl > 0)).diff(28)

    return {name: p.where(memb) for name, p in feats.items()}


# ---------------------------------------------------------------------------
# Cost model: per-side bps by liquidity class (21d median dollar volume)
# ---------------------------------------------------------------------------

COST_TIERS = (  # (min 21d median dollar volume, per-side bps)
    (100e6, 12.0),   # mega caps: 10 bps taker + ~2 bps spread/impact
    (20e6, 18.0),
    (5e6, 30.0),
    (1e6, 50.0),
    (0.0, 100.0),    # micro: conservative, this is the cost wall
)


def cost_panel(dvol_med21: pd.DataFrame) -> pd.DataFrame:
    """Per-coin, per-day cost in bps per side, staged by liquidity tier."""
    out = pd.DataFrame(COST_TIERS[-1][1], index=dvol_med21.index, columns=dvol_med21.columns)
    # Ascending floors: each higher tier overrides the cheaper-floor mask.
    for floor, bps in sorted(COST_TIERS[:-1]):
        out = out.mask(dvol_med21 >= floor, bps)
    return out.where(dvol_med21.notna())
