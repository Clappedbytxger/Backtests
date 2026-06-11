"""Theory-driven commodity feature panels for the ML cross-section (PIT-safe).

Every feature has a documented economic cause (roadmap Teil 3); nothing here
is mined. All panels are daily, columns = roots, and **decision-time**: a
value at date ``t`` uses only information available at (or strictly before,
where releases lag) the close of ``t``. The portfolio engine additionally
``shift(1)``s holdings, so the full chain is leak-free by construction.

Feature inventory
-----------------
carry          annualized log(front/second); backwardation = scarcity premium
               (theory of storage / convenience yield). The front/second
               spread doubles as the *basis* — with no free spot series the
               front-second slope is the standard proxy, so "carry" covers
               both roadmap rows.
bm_63/bm_252   basis-momentum (Boons & Prado 2019): roll-adjusted front-leg
               minus second-leg cumulative return over the window — captures
               risk-premium variation the static basis misses.
mom_21/63/126/252  time-series momentum (underreaction, slow info diffusion).
hp / hp_z      hedging pressure (COT commercials net short / OI) level and
               1y z-score — Keynesian risk transfer premium.
oi_chg_13w     13-week log change in open interest (flow confirmation /
               exhaustion).
skew_252       realized skewness of daily returns, 1y — lottery preference
               premium (Bakshi et al.).
vol_20/vol_60  realized vol (annualized); vol_pct = 3y rolling percentile of
               vol_20. Conditioning/sizing features.
dxy_ret_63, real_rate, real_rate_chg_63, term_spread, vix, vix_pct
               macro state, constant per date — pure interaction fuel for the
               trees (a per-date-constant cannot rank the cross-section on
               its own, which is exactly the point).

Cross-sectional rank transform (GKX 2020): per date, map each feature to
(-0.5, 0.5) by rank. This makes scales comparable, kills outliers, and turns
every feature into a *relative* statement — note it makes a separate
"cross-sectional momentum" feature redundant (it IS rank-transformed TSM).

Targets: ``fwd_{5,21,63}`` raw forward returns of the roll-adjusted front
(for portfolio PnL) and ``y_{5,21,63}`` their per-date rank transform (the
regression target — robust to level drift and common moves).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .cot_data import COT_CODES, cot_daily_panel, get_cot_panel
from .futures_curve import (
    CONTRACT_SPACING_MONTHS,
    CURVE_UNIVERSE,
    get_carry_panel,
    get_curve_contract,
    roll_adjusted_close,
)

MOM_WINDOWS = (21, 63, 126, 252)
BM_WINDOWS = (63, 252)
TARGET_HORIZONS = (5, 21, 63)

FRED_MACRO = {
    "DTWEXBGS": "dxy",        # broad dollar index (daily)
    "DFII10": "real_rate",    # 10y TIPS real yield
    "T10Y2Y": "term_spread",  # 10y-2y treasury spread
    "VIXCLS": "vix",          # VIX close
}


def rank_transform(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-date cross-sectional rank into (-0.5, 0.5); NaNs stay NaN."""
    n = panel.notna().sum(axis=1)
    r = panel.rank(axis=1)
    return r.sub(0.5).div(n, axis=0).sub(0.5)


def _roll_adjusted_leg(root: str, leg: int) -> pd.Series:
    df = get_curve_contract(f"{root}.c.{leg}")
    if "instrument_id" not in df.columns:
        raise RuntimeError(
            f"{root}.c.{leg} cache lacks instrument_id — re-pull with force_refresh=True."
        )
    return roll_adjusted_close(df["Close"], df["instrument_id"])


def price_panels(roots: list[str] | None = None, ffill_limit: int = 10) -> dict[str, pd.DataFrame]:
    """Roll-adjusted synthetic price panels for both legs.

    The roots trade different calendars (and the PGM *front* contracts are
    structurally thin — the active month is the second), so the raw union
    panel is full of single-day holes that would kill every rolling window.
    ``front``/``second`` are therefore forward-filled mark-to-last (max
    ``ffill_limit`` days); ``observed`` flags the genuinely traded days so
    vol/skew can be computed on real, not filled, returns.
    """
    roots = roots or list(CURVE_UNIVERSE)
    front_raw = pd.DataFrame({r: _roll_adjusted_leg(r, 0) for r in roots})
    second_raw = pd.DataFrame({r: _roll_adjusted_leg(r, 1) for r in roots})

    # Databento daily bars are UTC-dated: Globex Sunday-evening sessions create
    # "Sunday" rows where only part of the universe prints a bar (and grain
    # Sunday sessions died ~2014). Those sparse rows poison weekly rebalance
    # dates (to_period("W") ends on Sunday => the rebalance lands exactly
    # there). Keep only days where at least half the universe actually traded.
    observed = front_raw.notna()
    calendar = front_raw.index[observed.sum(axis=1) >= 0.5 * len(roots)]
    return {
        "front_adj": front_raw.reindex(calendar).ffill(limit=ffill_limit),
        "second_adj": second_raw.reindex(calendar).ffill(limit=ffill_limit),
        "observed": observed.reindex(calendar),
    }


def _fred_daily(series_id: str, api_key: str | None = None) -> pd.Series:
    """FRED market-price series as a date-indexed Series, Parquet-cached.

    Plain (vintage-free) observations: these series (dollar index, yields,
    VIX) are market prices and do not revise, so ALFRED machinery is
    unnecessary — and FRED rejects full-vintage queries on dense daily
    series with HTTP 400 anyway.
    """
    import urllib.parse

    from .fundamental_data import CACHE_DIR, _fetch_json, read_api_key

    path = CACHE_DIR / f"fred_plain_{series_id}.parquet"
    if path.exists():
        return pd.read_parquet(path)["value"]

    params = {
        "series_id": series_id,
        "observation_start": "2008-01-01",
        "api_key": read_api_key("fred", api_key),
        "file_type": "json",
        "limit": 100000,
    }
    url = (
        "https://api.stlouisfed.org/fred/series/observations?"
        + urllib.parse.urlencode(params)
    )
    obs = _fetch_json(url).get("observations", [])
    if not obs:
        raise ValueError(f"FRED returned no observations for {series_id!r}.")
    df = pd.DataFrame(obs)
    df = df[df["value"] != "."]
    s = pd.Series(
        pd.to_numeric(df["value"], errors="coerce").values,
        index=pd.to_datetime(df["date"]),
        name="value",
    ).dropna()
    s.index.name = "ref_date"
    s.to_frame().to_parquet(path)
    return s


def macro_panel(trading_days: pd.DatetimeIndex, api_key: str | None = None) -> pd.DataFrame:
    """Daily macro features, shifted one day for release-time safety.

    These are market prices (no revisions), but same-evening publication can
    postdate futures settlements — the uniform ``shift(1)`` removes the
    ambiguity at negligible signal cost on 1W-3M horizons.
    """
    cols = {}
    for sid, name in FRED_MACRO.items():
        s = _fred_daily(sid, api_key=api_key)
        s = s.reindex(trading_days.union(s.index)).ffill().reindex(trading_days)
        cols[name] = s.shift(1)
    m = pd.DataFrame(cols, index=trading_days)

    out = pd.DataFrame(index=trading_days)
    out["dxy_ret_63"] = m["dxy"].pct_change(63)
    out["real_rate"] = m["real_rate"]
    out["real_rate_chg_63"] = m["real_rate"].diff(63)
    out["term_spread"] = m["term_spread"]
    out["vix"] = m["vix"]
    out["vix_pct"] = m["vix"].rolling(756, min_periods=252).rank(pct=True)
    return out


def build_feature_panels(
    roots: list[str] | None = None,
    include_macro: bool = True,
) -> dict:
    """All feature/target panels on the common trading calendar.

    Returns dict with ``features`` ({name: panel}), ``targets_raw``,
    ``targets_rank``, ``returns`` (daily roll-adjusted front returns) and
    ``vol20`` (for portfolio leg weighting).
    """
    roots = roots or [r for r in CURVE_UNIVERSE if r in COT_CODES]

    legs = price_panels(roots)
    front, second = legs["front_adj"], legs["second_adj"]
    days = front.index
    rets = front.pct_change()

    feats: dict[str, pd.DataFrame] = {}

    # Carry / basis: annualized front-second slope (theory of storage).
    curves = get_carry_panel(roots)
    raw_carry = {}
    for root, panel in curves.items():
        spacing = CONTRACT_SPACING_MONTHS.get(root, 1)
        raw_carry[root] = np.log(panel["front"] / panel["second"]) * (12.0 / spacing)
    # ffill bridges per-root holidays/thin days on the common calendar.
    feats["carry"] = pd.DataFrame(raw_carry).reindex(days).ffill(limit=10)

    # Basis-momentum: front-leg minus second-leg roll-adjusted return.
    for k in BM_WINDOWS:
        feats[f"bm_{k}"] = (
            front.pct_change(k) - second.pct_change(k)
        ).reindex(days)

    # Time-series momentum.
    for k in MOM_WINDOWS:
        feats[f"mom_{k}"] = front.pct_change(k)

    # COT: hedging pressure + open-interest flow (PIT: release + 1 day).
    cot = get_cot_panel(roots)
    hp = cot_daily_panel(cot, days, "hedging_pressure")
    feats["hp"] = hp
    feats["hp_z"] = (hp - hp.rolling(252, min_periods=126).mean()) / hp.rolling(
        252, min_periods=126
    ).std()
    oi = cot_daily_panel(cot, days, "open_interest")
    feats["oi_chg_13w"] = np.log(oi).diff(65)

    # Realized skew & vol regime — on *observed* returns per root (a filled
    # mark-to-last day has return 0 and would bias vol down / break skew),
    # rolling over the root's own trading days, then re-aligned to the
    # common calendar.
    rets_obs = rets.where(legs["observed"])

    def obs_rolling(window: int, min_p: int, fn: str) -> pd.DataFrame:
        out = {}
        for c in rets_obs.columns:
            s = rets_obs[c].dropna()
            out[c] = getattr(s.rolling(window, min_periods=min_p), fn)()
        return pd.DataFrame(out).reindex(days).ffill(limit=10)

    feats["skew_252"] = obs_rolling(252, 189, "skew")
    vol20 = obs_rolling(20, 15, "std") * np.sqrt(252)
    feats["vol_20"] = vol20
    feats["vol_60"] = obs_rolling(60, 45, "std") * np.sqrt(252)
    feats["vol_pct"] = vol20.rolling(756, min_periods=252).rank(pct=True)

    # Targets: forward return over h trading days, decided at close t.
    targets_raw = {h: front.pct_change(h).shift(-h) for h in TARGET_HORIZONS}
    targets_rank = {h: rank_transform(t) for h, t in targets_raw.items()}

    out = {
        "features": feats,
        "targets_raw": targets_raw,
        "targets_rank": targets_rank,
        "returns": rets,
        "vol20": vol20,
        "days": days,
    }
    if include_macro:
        out["macro"] = macro_panel(days)
    return out


def assemble_design_matrix(
    panels: dict,
    horizon: int = 21,
    rank_features: bool = True,
    sample_freq: str = "W",
) -> pd.DataFrame:
    """Long-format design matrix: rows = (date, root), columns = features + y.

    Args:
        panels: output of :func:`build_feature_panels`.
        horizon: target horizon in trading days (5/21/63).
        rank_features: per-date rank transform of commodity features
            (GKX-style). Macro columns are left raw (constant per date).
        sample_freq: subsample rows to weekly ("W") rebalance dates or "D"
            for all days. Weekly keeps the 5d target non-overlapping and
            cuts redundancy for the longer targets.

    Drops rows where the target or any momentum/carry core feature is NaN;
    COT/skew NaNs in the early warmup are left to the model (LightGBM) or
    filled with the cross-sectional median (linear models do that upstream).
    """
    feats = panels["features"]
    days = panels["days"]
    if sample_freq == "W":
        from .cross_sectional import _rebalance_dates

        dates = _rebalance_dates(days, "W")
    else:
        dates = days

    blocks = []
    for name, panel in feats.items():
        p = rank_transform(panel) if rank_features else panel
        blocks.append(p.reindex(dates).stack().rename(name))
    y = panels["targets_rank"][horizon].reindex(dates).stack().rename("y")
    fwd = panels["targets_raw"][horizon].reindex(dates).stack().rename("fwd_ret")

    df = pd.concat(blocks + [y, fwd], axis=1)
    df.index.names = ["date", "root"]

    if "macro" in panels:
        macro = panels["macro"].reindex(dates)
        df = df.join(macro, on="date")

    core = ["carry", "mom_252", "y"]
    return df.dropna(subset=[c for c in core if c in df.columns])
