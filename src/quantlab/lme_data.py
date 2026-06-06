"""Free LME base-metal price loader (westmetall.com scrape, Parquet-cached).

Why this exists
---------------
yfinance has no usable zinc series: the front-month symbol ``ZNC=F`` froze around
2019 and returns a single repeated print from 2020 on (see strategy 0025 report).
The Bloomberg Commodity Zinc Subindex (``BCOMZS``, 35y) that Seasonax uses is a
*futures total-return index* behind a Bloomberg/Investing.com paywall.

westmetall.com publishes the **LME official Cash-Settlement** (and 3-month) price
daily, for free, back to 2008. That is the physical spot reference — *no futures
roll artifact* — which is arguably a cleaner test of a supply/demand seasonal than
a roll-yield-laden index. We scrape the per-year HTML tables and cache to Parquet
so repeated backtests are deterministic and offline.

Limitations (document in any report that uses this):
  * History starts 2008 (~18 years), not the 35y of BCOMZS.
  * Cash-Settlement is the LME spot, not an investable total return; it ignores
    roll/carry. Good for a *timing* test, not for a tradable equity curve.
  * Single free source — values are not cross-checked against a second feed.
"""

from __future__ import annotations

import datetime as dt
import re
import urllib.request
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_BASE = "https://www.westmetall.com/en/markdaten.php?action=table&field={field}&year={year}"
_UA = {"User-Agent": "Mozilla/5.0"}

# westmetall field codes for the LME cash-settlement tables.
_FIELDS = {
    "zinc": "LME_Zn_cash",
    "copper": "LME_Cu_cash",
    "aluminium": "LME_Al_cash",
    "lead": "LME_Pb_cash",
    "nickel": "LME_Ni_cash",
    "tin": "LME_Sn_cash",
}

# Each row: <td>31. December 2015</td><td>1,600.00</td> (cash) <td>...</td> (3m) ...
_ROW_RE = re.compile(
    r"<tr>\s*<td[^>]*>\s*([0-9]{1,2}\.\s*[A-Za-z]+\s*[0-9]{4})\s*</td>"
    r"\s*<td[^>]*>\s*([0-9.,]*)\s*</td>"
)


def _fetch_year(field: str, year: int) -> list[tuple[dt.datetime, float]]:
    """Scrape one year's daily cash-settlement rows from westmetall."""
    url = _BASE.format(field=field, year=year)
    req = urllib.request.Request(url, headers=_UA)
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    out: list[tuple[dt.datetime, float]] = []
    for d_str, p_str in _ROW_RE.findall(html):
        if not p_str:
            continue  # holiday / missing settlement
        try:
            date = dt.datetime.strptime(re.sub(r"\s+", " ", d_str.strip()), "%d. %B %Y")
            price = float(p_str.replace(",", ""))
        except ValueError:
            continue
        if price > 0:
            out.append((date, price))
    return out


def get_lme_metal(
    metal: str = "zinc",
    start: str | None = "2000-01-01",
    end: str | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Load daily LME Cash-Settlement for ``metal`` as an OHLCV-shaped frame.

    Only a settlement *level* exists, so ``Open/High/Low/Close`` are all set to the
    cash-settlement price and ``Volume`` to 0 — enough for the close-to-close
    backtest engine. Index is ascending dates.

    Args:
        metal: one of :data:`_FIELDS` (``"zinc"``, ``"copper"``, ...).
        start/end: ISO bounds (inclusive/exclusive) applied after download.
        use_cache / force_refresh: Parquet cache controls.
    """
    if metal not in _FIELDS:
        raise ValueError(f"Unknown metal '{metal}'. Known: {sorted(_FIELDS)}")
    field = _FIELDS[metal]
    cache = CACHE_DIR / f"lme_{metal}_cash.parquet"

    if use_cache and not force_refresh and cache.exists():
        df = pd.read_parquet(cache)
    else:
        rows: list[tuple[dt.datetime, float]] = []
        for year in range(2008, dt.date.today().year + 1):
            try:
                rows.extend(_fetch_year(field, year))
            except Exception as exc:  # noqa: BLE001 — one bad year shouldn't kill the load
                print(f"  warn: LME {metal} {year} fetch failed ({exc})")
        if not rows:
            raise ValueError(f"No LME {metal} data scraped from westmetall.")
        s = (pd.Series(dict(rows)).sort_index())
        s.index = pd.DatetimeIndex(s.index, name="Date")
        s = s[~s.index.duplicated(keep="last")]
        df = pd.DataFrame({"Open": s, "High": s, "Low": s, "Close": s, "Volume": 0.0})
        if use_cache:
            df.to_parquet(cache)

    if start is not None:
        df = df.loc[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df.loc[df.index < pd.Timestamp(end)]
    return df


def get_lme_zinc(**kwargs) -> pd.DataFrame:
    """Convenience wrapper: daily LME zinc Cash-Settlement (2008+)."""
    return get_lme_metal("zinc", **kwargs)
