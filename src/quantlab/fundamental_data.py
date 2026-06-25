"""PIT-aware fundamental data loaders with Parquet caching.

Design principles
-----------------
1. **Point-in-time correctness.**  Every row carries two date fields:

   - ``ref_date``     the reference period the number describes
                      (e.g. week ending Sunday for NASS crop condition)
   - ``release_date`` when the value became publicly available

   Backtests MUST join on ``release_date``, never on ``ref_date``.
   The PIT look-ahead guard in ``tests/test_pit.py`` enforces this.

2. **Parquet cache** under ``data/cache/fundamentals/`` keyed by call
   arguments — repeated runs are offline and deterministic.

3. **Failure modes documented per adapter.**  Read each docstring's
   "PIT notes" section before building signals from its output.

Adapters
--------
open_meteo   — ERA5 reanalysis via Open-Meteo (keyless)
usda_nass    — Crop Condition / Progress (NASS QuickStats, free API key)
usda_wasde   — Monthly S&D estimates via USDA FAS PSD API (no key)
eia          — Energy / ethanol weekly (EIA v2 API, free key)
fred         — Macro series with ALFRED vintage history (FRED API, free key)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "fundamentals"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# Free-API key resolution. Mirrors the Databento convention (futures_intraday.py):
# read the env var first, else a gitignored ``.<service>.key`` file in the project
# root (covered by the ``*.key`` rule in .gitignore). This keeps keys out of code
# and out of git, and lets every loader default ``api_key=None``.
#
# Register (all free):
#   EIA  -> https://www.eia.gov/opendata/register.php          -> .eia.key
#   NASS -> https://quickstats.nass.usda.gov/api               -> .nass.key
#   FRED -> https://fredaccount.stlouisfed.org/apikeys         -> .fred.key
#   FAS  -> https://apps.fas.usda.gov/opendataweb/             -> .fas.key
#   Gemini -> https://aistudio.google.com/apikey               -> .gemini.key
_KEY_ENV = {
    "eia":  "EIA_API_KEY",
    "nass": "NASS_API_KEY",
    "fred": "FRED_API_KEY",
    "fas":  "FAS_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "alpaca_key": "APCA_API_KEY_ID",
    "alpaca_secret": "APCA_API_SECRET_KEY",
}


def read_api_key(service: str, explicit: str | None = None) -> str:
    """Resolve an API key: explicit arg > encrypted vault > env var > gitignored keyfile.

    The encrypted BYOK vault (:mod:`quantlab.keystore`) takes precedence over env/keyfile
    when it is unlocked and holds the service — so keys entered in the Settings tab win,
    while the legacy plaintext ``.<service>.key`` files keep working as a fallback.

    Args:
        service: e.g. ``"gemini"``, ``"eia"``, ``"nass"``, ``"fred"``, ``"fas"``.
        explicit: a key passed directly (wins if given).

    Raises:
        RuntimeError: with a registration hint if no key can be found.
    """
    if explicit:
        return explicit
    try:  # encrypted BYOK vault (lazy import avoids any cycle)
        from quantlab.keystore import vault_key

        vk = vault_key(service)
        if vk:
            return vk
    except Exception:  # noqa: BLE001 - vault must never break key resolution
        pass
    env = os.environ.get(_KEY_ENV.get(service, ""))
    if env:
        return env
    keyfile = _PROJECT_ROOT / f".{service}.key"
    if keyfile.exists():
        return keyfile.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        f"No {service.upper()} API key. Set ${_KEY_ENV.get(service)} or create "
        f"{keyfile}. Register free — see read_api_key() docstring in "
        f"quantlab.fundamental_data."
    )

# ---------------------------------------------------------------------------
# Known agricultural / mining regions  (lat, lon)
# ---------------------------------------------------------------------------
REGION_COORDS: dict[str, tuple[float, float]] = {
    "sao_paulo_sugarcane":  (-22.0,  -47.0),   # SP state, Brazil — sugar cane belt
    "cote_divoire_cocoa":   (  6.8,   -5.3),   # Côte d'Ivoire — main cocoa
    "ghana_cocoa":          (  7.0,   -1.5),   # Ghana — second cocoa
    "minas_gerais_coffee":  (-19.5,  -43.5),   # Minas Gerais, Brazil — arabica
    "west_texas_cotton":    ( 33.0, -102.0),   # West Texas — US cotton
    "india_cotton":         ( 22.3,   72.5),   # Gujarat, India — cotton
    "florida_citrus":       ( 27.5,  -81.5),   # Florida — orange juice
    "corn_belt_iowa":       ( 42.0,  -93.5),   # Iowa — corn/soy
    "south_africa_platinum":(-25.7,   27.1),   # Bushveld Complex — PGMs
    "malaysia_palm_oil":    (  3.5,  109.5),   # Sarawak, Malaysia
    "indonesia_palm_oil":   ( -2.0,  113.9),   # Kalimantan, Indonesia
    "thailand_rubber":      (  9.0,  100.0),   # Southern Thailand
    "canada_canola":        ( 52.0, -106.0),   # Saskatchewan
    "india_monsoon":        ( 19.0,   73.0),   # Mumbai — monsoon index
}

# ---------------------------------------------------------------------------
# USDA FAS PSD commodity codes
# ---------------------------------------------------------------------------
WASDE_COMMODITY: dict[str, str] = {
    "sugar_centrifugal": "0240000",
    "coffee_green":      "0813100",
    "cotton":            "2631000",
    "corn":              "0440000",
    "soybeans":          "2222000",
    "wheat":             "0410000",
    "palm_oil":          "4243000",
    "canola_rapeseed":   "2226000",
    "beef_veal":         "2111000",
}

# Default Open-Meteo daily variables (ERA5 reanalysis)
_OM_DEFAULT_VARS: list[str] = [
    "precipitation_sum",
    "temperature_2m_mean",
    "temperature_2m_min",
    "temperature_2m_max",
    "et0_fao_evapotranspiration",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_path(prefix: str, **kwargs: object) -> Path:
    key = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.md5(key.encode()).hexdigest()[:10]
    return CACHE_DIR / f"{prefix}_{digest}.parquet"


def _fetch_json(url: str, retries: int = 3, delay: float = 1.5) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))


# ---------------------------------------------------------------------------
# Open-Meteo (ERA5 reanalysis, keyless)
# ---------------------------------------------------------------------------

_OM_BASE = "https://archive-api.open-meteo.com/v1/archive"


def get_weather_daily(
    lat: float,
    lon: float,
    start: str,
    end: str,
    variables: list[str] = _OM_DEFAULT_VARS,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Daily weather from ERA5 reanalysis via Open-Meteo (no API key needed).

    Args:
        lat / lon: geographic coordinates of the target region.
        start / end: ISO date strings, e.g. "2000-01-01".
        variables: ERA5 daily variables.  See ``_OM_DEFAULT_VARS`` for defaults.
        use_cache: read/write the Parquet cache.

    Returns:
        DataFrame indexed by ``ref_date`` with columns:
        ``release_date``, and one column per requested variable.

    PIT notes:
    - ERA5 data is a finalized reanalysis; all historical values are available
      now.  For the backtest ``release_date = ref_date + 1 day`` (conservative:
      the ERA5 near-real-time product has ~5-day latency in production).
    - The raw weather value is NOT a PIT-safe signal on its own — use
      ``features.weather_anomaly()`` which applies a rolling, past-only
      climatology.
    - For a live deployment, replace the archive endpoint with the ERA5T
      near-real-time endpoint and adjust the release-date lag accordingly.
    """
    path = _cache_path("om", lat=lat, lon=lon, start=start, end=end,
                       vars=sorted(variables))
    if use_cache and path.exists():
        return pd.read_parquet(path)

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(variables),
        "timezone": "UTC",
    }
    url = _OM_BASE + "?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)

    dates = pd.to_datetime(data["daily"]["time"])
    df = pd.DataFrame(index=dates)
    df.index.name = "ref_date"
    for var in variables:
        if var in data["daily"]:
            df[var] = data["daily"][var]

    df["release_date"] = df.index + pd.Timedelta(days=1)

    if use_cache:
        df.to_parquet(path)
    return df


# ---------------------------------------------------------------------------
# USDA NASS QuickStats  (Crop Condition / Progress, free API key)
# ---------------------------------------------------------------------------

_NASS_BASE = "https://quickstats.nass.usda.gov/api/api_GET/"


def get_nass_crop_condition(
    commodity: str,
    state_fips: str,
    start_year: int,
    end_year: int,
    api_key: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Weekly crop condition (good + excellent %) from USDA NASS QuickStats.

    Args:
        commodity: e.g. ``"CORN"``, ``"COTTON"``, ``"SOYBEANS"``.
        state_fips: two-digit FIPS code, e.g. ``"48"`` Texas, ``"17"`` Illinois.
        start_year / end_year: inclusive crop year range.
        api_key: free key from https://quickstats.nass.usda.gov/api

    Returns:
        DataFrame indexed by ``ref_date`` (week-ending Sunday) with columns:
        ``release_date`` (Monday after week-ending), ``pct_good``,
        ``pct_excellent``, ``pct_good_excellent`` (sum of both).

    PIT notes:
    - NASS Crop Progress reports are released on **Mondays at 4 PM ET**.
    - week_ending date is the preceding Sunday.
    - ``release_date = ref_date + 1 day`` (Monday).
    - For daily backtests that enter on the release day, use entry at close
      on Tuesday to guarantee the number was known at order time.
    """
    path = _cache_path("nass_cc", commodity=commodity, state=state_fips,
                       y0=start_year, y1=end_year)
    if use_cache and path.exists():
        return pd.read_parquet(path)

    api_key = read_api_key("nass", api_key)
    # NOTE: do NOT filter on unit_desc — NASS rejects "PCT AREA" as an invalid
    # query (HTTP 400). CONDITION data is returned in PCT regardless; we select the
    # GOOD/EXCELLENT classes below.
    params = {
        "key": api_key,
        "commodity_desc": commodity,
        "statisticcat_desc": "CONDITION",
        "freq_desc": "WEEKLY",
        "state_fips_code": state_fips,
        "year__GE": str(start_year),
        "year__LE": str(end_year),
        "format": "JSON",
    }
    url = _NASS_BASE + "?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)

    rows = data.get("data", [])
    if not rows:
        raise ValueError(
            f"NASS returned no data for commodity={commodity!r} "
            f"state_fips={state_fips!r}.  "
            "Check the API key and parameter names."
        )

    df_raw = pd.DataFrame(rows)
    df_raw["Value"] = pd.to_numeric(
        df_raw["Value"].str.replace(",", ""), errors="coerce"
    )
    df_raw["week_ending"] = pd.to_datetime(df_raw["week_ending"])

    # The condition level (GOOD/EXCELLENT/...) is encoded in ``short_desc``
    # ("... CONDITION, MEASURED IN PCT GOOD"), NOT in ``class_desc`` (which holds
    # e.g. "UPLAND" for cotton). Match on the short_desc suffix — robust across
    # commodities (corn/cotton/soybeans all use the same "PCT <LEVEL>" suffix).
    sd = df_raw["short_desc"].str.upper().str.strip()
    good = (
        df_raw[sd.str.endswith("PCT GOOD")][["week_ending", "Value"]]
        .rename(columns={"Value": "pct_good"})
    )
    exc = (
        df_raw[sd.str.endswith("PCT EXCELLENT")][["week_ending", "Value"]]
        .rename(columns={"Value": "pct_excellent"})
    )

    df = (
        good.merge(exc, on="week_ending", how="outer")
        .sort_values("week_ending")
        .rename(columns={"week_ending": "ref_date"})
        .set_index("ref_date")
    )
    df["pct_good_excellent"] = (
        df["pct_good"].fillna(0.0) + df["pct_excellent"].fillna(0.0)
    )
    df["release_date"] = df.index + pd.Timedelta(days=1)

    if use_cache:
        df.to_parquet(path)
    return df


# ---------------------------------------------------------------------------
# USDA FAS PSD  (WASDE S&D estimates, no API key)
# ---------------------------------------------------------------------------

_FAS_BASE = "https://apps.fas.usda.gov/psdonline/api/data/commodity"
_WASDE_RELEASE_DOM = 10   # approximate day-of-month for WASDE release


def get_wasde_psd(
    commodity_code: str,
    country_code: str = "00",
    start_year: int = 2000,
    end_year: int | None = None,
    attribute: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Monthly WASDE S&D estimates via USDA FAS PSD Online API (no key needed).

    Args:
        commodity_code: FAS PSD code.  Use ``WASDE_COMMODITY`` dict for
            common crops, e.g. ``WASDE_COMMODITY["corn"]``.
        country_code: ``"00"`` = world total, ``"US"`` = United States.
        start_year / end_year: market-year range.
        attribute: filter to one attribute (e.g. ``"Production"``,
            ``"Ending Stocks"``).  ``None`` = return all.
        use_cache: read/write Parquet cache.

    Returns:
        DataFrame indexed by ``ref_date`` (first day of the calendar month)
        with columns: ``release_date``, ``attribute``, ``value``, ``unit``.

    PIT notes:
    - The FAS PSD API does NOT expose WASDE release dates.
      ``release_date`` is approximated as the 10th of the calendar month —
      this is the typical WASDE release day; the true date varies by ±3 days.
      Document this proxy in any REPORT.md that uses this data.
    - ``surprise = current_value − prior_month_value`` is the naïve proxy
      for analyst consensus (no free consensus data exists).  Build this in
      ``features.wasde_surprise()``.
    - Market year ≠ calendar year for most crops.  The ``cal_year`` and
      ``cal_month`` fields from the API are used directly.
    """
    end_year = end_year or pd.Timestamp.now().year
    path = _cache_path(
        "wasde_psd", code=commodity_code, country=country_code,
        y0=start_year, y1=end_year, attr=attribute or "all"
    )
    if use_cache and path.exists():
        return pd.read_parquet(path)

    params = {
        "commodityCode": commodity_code,
        "marketYear": 0,          # 0 = all years
        "countryCode": country_code,
        "reportid": 1,
    }
    url = _FAS_BASE + "?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)

    df_raw = pd.DataFrame(data)
    if df_raw.empty:
        raise ValueError(
            f"FAS PSD returned no data for commodity_code={commodity_code!r}."
        )

    df_raw = df_raw.rename(columns={
        "calendarYear": "cal_year",
        "month": "cal_month",
        "attributeName": "attribute",
        "value": "value",
        "unitDesc": "unit",
    })
    for col in ("cal_year", "cal_month", "value"):
        df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

    df_raw = df_raw.dropna(subset=["cal_year", "cal_month", "value"])
    df_raw["cal_year"] = df_raw["cal_year"].astype(int)
    df_raw["cal_month"] = df_raw["cal_month"].astype(int)

    def _make_date(row: pd.Series, day: int) -> pd.Timestamp:
        try:
            return pd.Timestamp(int(row["cal_year"]), int(row["cal_month"]), day)
        except Exception:
            return pd.NaT

    df_raw["ref_date"] = df_raw.apply(lambda r: _make_date(r, 1), axis=1)
    df_raw["release_date"] = df_raw.apply(
        lambda r: _make_date(r, _WASDE_RELEASE_DOM), axis=1
    )

    if attribute:
        df_raw = df_raw[df_raw["attribute"] == attribute]

    df_raw = df_raw[df_raw["cal_year"].between(start_year, end_year)]
    df_raw = df_raw.dropna(subset=["ref_date"])
    df_raw = (
        df_raw.set_index("ref_date")[["release_date", "attribute", "value", "unit"]]
        .sort_index()
    )

    if use_cache:
        df_raw.to_parquet(path)
    return df_raw


# ---------------------------------------------------------------------------
# EIA v2 API  (energy / ethanol, free API key)
# ---------------------------------------------------------------------------

_EIA_BASE = "https://api.eia.gov/v2"

# Convenience routes for commodity-relevant EIA series
EIA_ROUTES: dict[str, str] = {
    "ethanol_production":  "petroleum/pnp/fuel/data/",
    "ethanol_stocks":      "petroleum/stoc/wstk/data/",
    "crude_stocks":        "petroleum/stoc/wstk/data/",
    "nat_gas_storage":     "natural-gas/stor/wkly/data/",
    "electricity_monthly": "electricity/electric-power-operational-data/data/",
}


def get_eia_series(
    route: str,
    api_key: str | None = None,
    facets: dict[str, list[str]] | None = None,
    frequency: str = "weekly",
    data_cols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Weekly (or monthly) EIA series via v2 API.

    Args:
        route: EIA v2 route, e.g. ``"petroleum/pnp/fuel/data/"``.
            See ``EIA_ROUTES`` for shortcuts.
        api_key: free key from https://www.eia.gov/opendata/register.php
        facets: dict of facet filters, e.g. ``{"product": ["EPD0XS0"]}``.
        frequency: ``"weekly"``, ``"monthly"``, or ``"annual"``.
        data_cols: list of data columns, default ``["value"]``.
        start / end: ISO date strings (optional).
        use_cache: read/write Parquet cache.

    Returns:
        DataFrame indexed by ``ref_date`` (= EIA "period") with columns:
        ``release_date`` (= ref_date for EIA; EIA period IS the release week),
        plus one column per ``data_cols`` entry.

    PIT notes:
    - EIA weekly data releases are typically on Thursdays at 10:30 AM ET.
    - The "period" field in EIA v2 is the week of the release, not the
      reference period (e.g. week ending date).  We treat ``release_date =
      ref_date`` as a conservative approximation.
    - Minor weekly revisions occur; no ALFRED-style vintage tracking needed
      for the small revision magnitudes typical of EIA series.
    """
    data_cols = data_cols or ["value"]
    path = _cache_path(
        "eia", route=route, facets=str(sorted((facets or {}).items())),
        freq=frequency, start=start or "", end=end or ""
    )
    if use_cache and path.exists():
        return pd.read_parquet(path)

    api_key = read_api_key("eia", api_key)
    params: dict[str, str | int] = {
        "api_key": api_key,
        "frequency": frequency,
        "length": 5000,
        "offset": 0,
    }
    for i, col in enumerate(data_cols):
        params[f"data[{i}]"] = col
    if facets:
        for k, vals in facets.items():
            for i, v in enumerate(vals):
                params[f"facets[{k}][{i}]"] = v
    if start:
        params["start"] = start
    if end:
        params["end"] = end

    url = f"{_EIA_BASE}/{route}?" + urllib.parse.urlencode(params)
    resp = _fetch_json(url)

    rows = resp.get("response", {}).get("data", [])
    if not rows:
        raise ValueError(
            f"EIA returned no data for route={route!r}.  "
            "Check the api_key, route, and facets."
        )

    df = pd.DataFrame(rows)
    df["ref_date"] = pd.to_datetime(df["period"])
    df["release_date"] = df["ref_date"]   # EIA period = release week

    for col in data_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["release_date"] + [c for c in data_cols if c in df.columns]
    df = df.set_index("ref_date")[keep].sort_index()

    if use_cache:
        df.to_parquet(path)
    return df


# ---------------------------------------------------------------------------
# FRED / ALFRED  (macro series with vintage history, free API key)
# ---------------------------------------------------------------------------

_FRED_BASE = "https://api.stlouisfed.org/fred"


def get_fred_vintage(
    series_id: str,
    api_key: str | None = None,
    start: str = "2000-01-01",
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """FRED series with full ALFRED vintage history for PIT-correct backtesting.

    Fetches the complete revision history so that for any backtest date t you
    can reconstruct exactly which value was public knowledge at time t.

    Args:
        series_id: FRED identifier, e.g. ``"INDPRO"`` (US industrial production),
            ``"TOTALSA"`` (total US auto sales), ``"CHNTOTALSAI"`` (China auto).
        api_key: free key from https://fred.stlouisfed.org/docs/api/api_key.html
        start: earliest observation date (ISO).
        end: latest vintage date to include.  Defaults to today.
        use_cache: read/write Parquet cache.

    Returns:
        DataFrame (long format, NOT indexed) with columns:
        ``ref_date``     the observation period (e.g. 2020-01-01 for January)
        ``release_date`` = ALFRED ``realtime_start`` for this vintage
        ``value``        the reported value as of that vintage

        Multiple rows per ``ref_date`` reflect successive revisions.  Use
        ``as_of(df, backtest_date)`` to get the PIT-correct view.

    PIT notes:
    - This is the ALFRED approach — the gold standard for revised macro data.
    - Series with large revisions (GDP, industrial production, employment) need
      this; exchange rates and market prices do not.
    - Cache is keyed by series_id + end date.  Invalidate when you need fresher
      vintages by passing ``use_cache=False`` or deleting the cache file.
    """
    end = end or pd.Timestamp.now().strftime("%Y-%m-%d")
    path = _cache_path("fred", series=series_id, start=start, end=end)
    if use_cache and path.exists():
        return pd.read_parquet(path)

    api_key = read_api_key("fred", api_key)
    params = {
        "series_id":          series_id,
        "realtime_start":     "1776-07-04",   # full vintage history
        "realtime_end":       end,
        "observation_start":  start,
        "api_key":            api_key,
        "file_type":          "json",
        "limit":              100000,
    }
    url = f"{_FRED_BASE}/series/observations?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)

    obs = data.get("observations", [])
    if not obs:
        raise ValueError(f"FRED returned no observations for {series_id!r}.")

    df = pd.DataFrame(obs)
    df = df[df["value"] != "."]   # FRED uses "." for missing
    df["ref_date"] = pd.to_datetime(df["date"])
    df["release_date"] = pd.to_datetime(df["realtime_start"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    df = (
        df[["ref_date", "release_date", "value"]]
        .dropna()
        .sort_values(["ref_date", "release_date"])
        .reset_index(drop=True)
    )

    if use_cache:
        df.to_parquet(path)
    return df


def as_of(
    vintage_df: pd.DataFrame,
    backtest_date: str | pd.Timestamp,
) -> pd.DataFrame:
    """Return the ALFRED vintage values as known on ``backtest_date``.

    For each ``ref_date``, returns the most recent value whose
    ``release_date <= backtest_date``.  This reconstructs the PIT-correct
    view a trader would have had on that day.

    Args:
        vintage_df: output of ``get_fred_vintage()``.
        backtest_date: the point-in-time cutoff.

    Returns:
        DataFrame indexed by ``ref_date`` with a single ``value`` column.
    """
    cutoff = pd.Timestamp(backtest_date)
    subset = vintage_df[vintage_df["release_date"] <= cutoff]
    return (
        subset.sort_values("release_date")
        .groupby("ref_date")["value"]
        .last()
        .rename("value")
        .to_frame()
    )


def build_pit_series(
    vintage_df: pd.DataFrame,
    price_index: pd.DatetimeIndex,
) -> pd.Series:
    """Build a daily PIT series aligned to a price index.

    For each day in ``price_index``, finds the most recent ALFRED vintage value
    whose ``release_date`` falls on or before that day (i.e. the value a trader
    would know on that day), then forward-fills.

    This is the bridge between the vintage DataFrame and a standard
    ``pd.Series`` aligned to prices for use in IC / backtest computations.

    Args:
        vintage_df: output of ``get_fred_vintage()``.
        price_index: DatetimeIndex of the asset price series.

    Returns:
        pd.Series indexed like ``price_index``, NaN where no vintage is
        yet available.
    """
    # Build a release-date-indexed series (latest value per release date)
    by_release = (
        vintage_df.sort_values(["ref_date", "release_date"])
        .groupby("release_date")["value"]
        .last()
    )
    # Reindex to the full price calendar and forward-fill
    daily = by_release.reindex(price_index, method="ffill")
    # Zero out any dates before the first release
    if not by_release.empty:
        daily[daily.index < by_release.index.min()] = np.nan
    return daily
