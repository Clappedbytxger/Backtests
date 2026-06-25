"""CFTC Commitments-of-Traders (COT) loader with PIT release logic.

Source: CFTC Public Reporting API (Socrata), Legacy *Futures Only* report,
dataset ``6dca-aqww`` — weekly since 1986, free, no API key required.

Why legacy and not disaggregated: the hedging-pressure literature (Basu &
Miffre 2013; Keynes' normal backwardation) is defined on the legacy
commercial/non-commercial split, and the legacy series is the longest.

PIT contract (the trap this module exists to avoid)
---------------------------------------------------
COT positions are as of **Tuesday** (``ref_date``) but published **Friday
~15:30 ET** (``release_date = ref_date + 3 days``). 15:30 ET is *after* the
daily settlement of most futures (CME grains settle 13:20 CT, energy 14:30
ET), so a Friday-close signal must NOT yet see Friday's release. Joining is
therefore done on ``release_date`` and the consumer must additionally treat
the value as usable from the *next trading day* (``cot_features`` below shifts
accordingly). ``tests/test_cot.py`` guards this.

Holiday weeks can delay the release by a day; the +3d rule is the standard
academic treatment and errs on the early side only in those rare weeks, which
the extra next-trading-day shift absorbs for all but back-to-back holidays.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "cot"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# Legacy-report CFTC contract market codes for the GLBX curve universe.
# Verified against ``market_and_exchange_names`` in ``_validate_market_name``.
COT_CODES: dict[str, str] = {
    "CL": "067651",  # CRUDE OIL, LIGHT SWEET (NYMEX) / WTI
    "NG": "023651",  # NATURAL GAS (NYMEX)
    "HO": "022651",  # NY HARBOR ULSD / #2 HEATING OIL (NYMEX)
    "RB": "111659",  # GASOLINE BLENDSTOCK RBOB (NYMEX)
    "GC": "088691",  # GOLD (COMEX)
    "SI": "084691",  # SILVER (COMEX)
    "HG": "085692",  # COPPER- #1 (COMEX)
    "PL": "076651",  # PLATINUM (NYMEX)
    "PA": "075651",  # PALLADIUM (NYMEX)
    "ZC": "002602",  # CORN (CBT)
    "ZW": "001602",  # WHEAT-SRW (CBT)
    "ZS": "005602",  # SOYBEANS (CBT)
    "ZL": "007601",  # SOYBEAN OIL (CBT)
    "ZM": "026603",  # SOYBEAN MEAL (CBT)
    "LE": "057642",  # LIVE CATTLE (CME)
    "GF": "061641",  # FEEDER CATTLE (CME)
    "HE": "054642",  # LEAN HOGS (CME)
    # ── FX (CME currency futures) ───────────────────────────────────────────
    "6E": "099741",  # EURO FX (CME)
    "6B": "096742",  # BRITISH POUND (CME)
    "6J": "097741",  # JAPANESE YEN (CME)
    "6A": "232741",  # AUSTRALIAN DOLLAR (CME)
    "6C": "090741",  # CANADIAN DOLLAR (CME)
    "6S": "092741",  # SWISS FRANC (CME)
    "DX": "098662",  # U.S. DOLLAR INDEX (ICE)
    # ── Equity indices (CME, consolidated/e-mini) ───────────────────────────
    "ES": "13874+",  # S&P 500 CONSOLIDATED (CME)
    "NQ": "20974+",  # NASDAQ-100 CONSOLIDATED (CME)
    "YM": "12460+",  # DOW JONES INDUSTRIAL AVG (CBT)
}

# Substring the returned market name must contain — typo-proofing the code map.
_NAME_CHECK: dict[str, str] = {
    "CL": "WTI", "NG": "NAT GAS", "HO": "ULSD", "RB": "GASOLINE",
    "GC": "GOLD", "SI": "SILVER", "HG": "COPPER", "PL": "PLATINUM",
    "PA": "PALLADIUM", "ZC": "CORN", "ZW": "WHEAT", "ZS": "SOYBEANS",
    "ZL": "SOYBEAN OIL", "ZM": "SOYBEAN MEAL", "LE": "LIVE CATTLE",
    "GF": "FEEDER CATTLE", "HE": "LEAN HOG",
    "6E": "EURO FX", "6B": "BRITISH POUND", "6J": "JAPANESE YEN",
    "6A": "AUSTRALIAN DOLLAR", "6C": "CANADIAN DOLLAR", "6S": "SWISS FRANC",
    "DX": "USD", "ES": "S&P 500", "NQ": "NASDAQ", "YM": "DJIA",
}

_FIELDS = [
    "report_date_as_yyyy_mm_dd",
    "market_and_exchange_names",
    "cftc_contract_market_code",
    "open_interest_all",
    "comm_positions_long_all",
    "comm_positions_short_all",
    "noncomm_positions_long_all",
    "noncomm_positions_short_all",
]

RELEASE_LAG_DAYS = 3  # Tuesday ref -> Friday ~15:30 ET release


def _cache_path(root: str) -> Path:
    return CACHE_DIR / f"cot_legacy_{root}.parquet"


def _fetch_rows(code: str, start: str) -> list[dict]:
    params = {
        "$select": ",".join(_FIELDS),
        "$where": f"cftc_contract_market_code='{code}' "
                  f"AND report_date_as_yyyy_mm_dd>='{start}T00:00:00.000'",
        "$order": "report_date_as_yyyy_mm_dd",
        "$limit": "5000",
    }
    url = _API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def get_cot(
    root: str,
    start: str = "2009-06-01",
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Weekly legacy COT for one root, PIT-annotated.

    Returns a DataFrame indexed by ``ref_date`` (Tuesday) with columns
    ``open_interest``, ``comm_long``, ``comm_short``, ``noncomm_long``,
    ``noncomm_short``, ``hedging_pressure`` and ``release_date``.

    ``hedging_pressure = (comm_short - comm_long) / open_interest`` — the
    commercials' net *short* share of OI. High = hedgers pay speculators to
    carry the long side (Keynes) => expected positive risk premium for longs.
    """
    root = root.upper()
    if root not in COT_CODES:
        raise KeyError(f"No COT code mapped for {root}.")
    path = _cache_path(root)
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    rows = _fetch_rows(COT_CODES[root], start)
    if not rows:
        raise ValueError(f"CFTC returned no rows for {root} ({COT_CODES[root]}).")
    df = pd.DataFrame(rows)

    name = df["market_and_exchange_names"].iloc[-1].upper()
    if _NAME_CHECK[root] not in name:
        raise ValueError(
            f"COT code mismatch for {root}: expected '{_NAME_CHECK[root]}' "
            f"in market name, got '{name}'."
        )

    out = pd.DataFrame({
        "open_interest": pd.to_numeric(df["open_interest_all"]),
        "comm_long": pd.to_numeric(df["comm_positions_long_all"]),
        "comm_short": pd.to_numeric(df["comm_positions_short_all"]),
        "noncomm_long": pd.to_numeric(df["noncomm_positions_long_all"]),
        "noncomm_short": pd.to_numeric(df["noncomm_positions_short_all"]),
    })
    out.index = pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).rename("ref_date")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out["hedging_pressure"] = (out["comm_short"] - out["comm_long"]) / out["open_interest"]
    out["release_date"] = out.index + pd.Timedelta(days=RELEASE_LAG_DAYS)

    if use_cache:
        out.to_parquet(path)
    return out


def get_cot_panel(roots: list[str] | None = None, **kwargs) -> dict[str, pd.DataFrame]:
    """``{root: weekly COT DataFrame}`` for the universe."""
    roots = roots or list(COT_CODES)
    return {r: get_cot(r, **kwargs) for r in roots}


def cot_daily_panel(
    cot: dict[str, pd.DataFrame],
    trading_days: pd.DatetimeIndex,
    column: str = "hedging_pressure",
) -> pd.DataFrame:
    """PIT-safe daily panel of one COT column (columns = roots).

    Each weekly value is placed on its ``release_date``, reindexed to the
    trading calendar with forward-fill, then **shifted one trading day** —
    because the Friday 15:30-ET release lands *after* Friday's futures
    settlement, the first close that may act on it is the next trading day.
    """
    cols = {}
    for root, df in cot.items():
        s = df.set_index("release_date")[column]
        s = s[~s.index.duplicated(keep="last")].sort_index()
        daily = s.reindex(trading_days.union(s.index)).ffill().reindex(trading_days)
        cols[root] = daily.shift(1)
    return pd.DataFrame(cols, index=trading_days)
