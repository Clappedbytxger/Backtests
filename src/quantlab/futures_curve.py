"""Futures term-structure (carry) data from Databento, with on-disk caching.

Sibling of ``futures_intraday.py`` but for the *curve*, not intraday bars. Carry
needs the nearest two contracts: Databento continuous symbology gives them as
``{ROOT}.c.0`` (front) and ``{ROOT}.c.1`` (second), each a daily OHLCV series.

The roll yield is ``front/second - 1`` (positive = backwardation = a long earns
the roll). To rank commodities cross-sectionally the raw spread must be
**annualized**, because the gap between the front and second contract differs by
market (energy ~1 month, grains/metals ~2, PGM ~3). Databento's continuous feed
returns only the alias (``CL.c.0``), not the resolved contract code, so the gap
is not recoverable from the data; we annualize with a documented per-root nominal
spacing (``CONTRACT_SPACING_MONTHS``). Exact per-date annualization from contract
expiries is a future refinement (needs the ``definition`` schema).

Coverage: GLBX.MDP3 = CME/NYMEX/COMEX/CBOT (energy, metals, grains, livestock).
ICE softs (SB/KC/CC/CT/OJ) are a separate dataset and not loaded here.

Auth: same key as ``futures_intraday`` (env ``DATABENTO_API_KEY`` or
``.databento.key``). Daily curve data is cheap (~$0.05 per contract-decade), but
the free credit is finite, so every pull is cost-estimated and hard-cached.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .futures_intraday import _client, estimate_cost

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "curve"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_DATASET = "GLBX.MDP3"
_START = "2010-06-06"  # GLBX.MDP3 inception

# CME/NYMEX/COMEX/CBOT roots with liquid, deep term structure.
CURVE_UNIVERSE = {
    "CL": "WTI Rohöl", "NG": "Erdgas", "HO": "Heizöl", "RB": "Benzin",
    "GC": "Gold", "SI": "Silber", "HG": "Kupfer", "PL": "Platin", "PA": "Palladium",
    "ZC": "Mais", "ZW": "Weizen", "ZS": "Sojabohnen", "ZL": "Sojaöl", "ZM": "Sojamehl",
    "LE": "Lebendrind", "GF": "Mastrind", "HE": "Mageschwein",
}

# Nominal months between the front (.c.0) and second (.c.1) liquid contract, from
# each market's standard active-month cycle. Used to annualize the raw roll yield
# so commodities with different contract spacing rank on the same scale.
CONTRACT_SPACING_MONTHS = {
    "CL": 1, "NG": 1, "HO": 1, "RB": 1,        # energy: monthly
    "GC": 2, "SI": 2, "HG": 2,                  # metals: ~bi-monthly active cycle
    "PL": 3, "PA": 3,                           # PGM: quarterly (Jan/Apr/Jul/Oct)
    "ZC": 2, "ZW": 2, "ZS": 2, "ZL": 2, "ZM": 2,  # grains: Mar/May/Jul/Sep/Dec
    "LE": 2, "GF": 2, "HE": 2,                  # livestock: ~bi-monthly
}


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol.replace('.', '_')}_ohlcv-1d.parquet"


def get_curve_contract(
    symbol: str,
    start: str = _START,
    end: str | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
    max_usd: float = 0.30,
) -> pd.DataFrame:
    """Daily OHLCV for one continuous contract (e.g. ``"CL.c.0"`` or ``"CL.c.1"``)."""
    end = end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    path = _cache_path(symbol)
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    est = estimate_cost(symbol, "ohlcv-1d", start, end, _DATASET)
    print(f"[databento curve] {symbol} 1d {start}..{end}: "
          f"{est['records']:,} bars, ${est['usd']:.4f}")
    if est["usd"] > max_usd:
        raise RuntimeError(f"Refusing: ${est['usd']:.2f} > max_usd ${max_usd:.2f}.")

    client = _client()
    data = client.timeseries.get_range(
        dataset=_DATASET, symbols=[symbol], schema="ohlcv-1d",
        start=start, end=end, stype_in="continuous",
    )
    df = data.to_df()
    if df.empty:
        raise ValueError(f"No data for {symbol} ({start}..{end}).")

    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    keep = ["Open", "High", "Low", "Close", "Volume"]
    # instrument_id changes exactly on a roll day -> the ground truth for
    # back-adjusting away the stitch gap (lesson 0028/0029).
    if "instrument_id" in df.columns:
        keep.append("instrument_id")
    df = df[keep].copy()
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    df.index.name = "Date"
    df = df[df["Close"] > 0]
    if use_cache:
        df.to_parquet(path)
    return df


def get_carry_panel(
    roots: list[str] | None = None,
    start: str = _START,
    end: str | None = None,
    **kwargs,
) -> dict[str, pd.DataFrame]:
    """Pull front (.c.0) and second (.c.1) daily closes for each root.

    Returns ``{root: DataFrame[front, second]}`` aligned on the common date index.
    """
    roots = roots or list(CURVE_UNIVERSE)
    out = {}
    for root in roots:
        f = get_curve_contract(f"{root}.c.0", start, end, **kwargs)
        s = get_curve_contract(f"{root}.c.1", start, end, **kwargs)
        out[root] = pd.DataFrame({"front": f["Close"], "second": s["Close"]}).dropna()
    return out


def front_month_panel(curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Front-contract close panel (columns = roots) — the tradeable price series."""
    return pd.DataFrame({root: c["front"] for root, c in curves.items()})


def roll_adjusted_front_panel(
    roots: list[str] | None = None,
    start: str = _START,
    end: str | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Roll-adjusted front-month price panel — artifact-free returns.

    A naive ``.c.0`` continuous stitch books the roll gap into ``pct_change`` (a
    fiction: nobody holds a single contract across the roll). We detect the exact
    roll day from the ``instrument_id`` change and zero that day's return, then
    rebuild a synthetic price whose ``pct_change`` is the real return of holding +
    rolling the front (the gradual intra-contract convergence — i.e. the carry —
    is preserved; only the stitch gap is removed).

    Requires the front contracts to carry an ``instrument_id`` column; pull them
    with ``force_refresh=True`` once if cached from before this was retained.
    """
    roots = roots or list(CURVE_UNIVERSE)
    cols = {}
    for root in roots:
        f = get_curve_contract(f"{root}.c.0", start, end, **kwargs)
        if "instrument_id" not in f.columns:
            raise RuntimeError(
                f"{root}.c.0 has no instrument_id (re-pull with force_refresh=True)."
            )
        cols[root] = roll_adjusted_close(f["Close"], f["instrument_id"])
    return pd.DataFrame(cols)


def roll_adjusted_close(close: pd.Series, instrument_id: pd.Series) -> pd.Series:
    """Back-adjusted synthetic close: zero the return on each roll day.

    A roll day is where ``instrument_id`` changes (a new contract becomes front).
    The naive ``close.pct_change`` books the stitch gap there — a fiction. We zero
    that day's return and rebuild a price whose ``pct_change`` is the real return
    of holding+rolling the front (intra-contract convergence / carry preserved).
    """
    roll = instrument_id.ne(instrument_id.shift(1)) & instrument_id.shift(1).notna()
    ret = close.pct_change().where(~roll, 0.0)
    return (1.0 + ret.fillna(0.0)).cumprod()


def carry_signal(curves: dict[str, pd.DataFrame], annualize: bool = True) -> pd.DataFrame:
    """Daily cross-sectional carry panel (columns = roots).

    ``carry = log(front / second)`` — positive = backwardation = long earns the
    roll. With ``annualize`` the raw spread is scaled by ``12 / spacing_months``
    so markets with different contract spacing are comparable in the ranking.
    """
    cols = {}
    for root, panel in curves.items():
        raw = np.log(panel["front"] / panel["second"])
        if annualize:
            spacing = CONTRACT_SPACING_MONTHS.get(root, 1)
            raw = raw * (12.0 / spacing)
        cols[root] = raw
    return pd.DataFrame(cols)
