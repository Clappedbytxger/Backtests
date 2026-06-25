"""SEC EDGAR fundamental loader for PEAD / SUE research (free, survivorship-free).

EDGAR retains filings for delisted companies, so reported quarterly EPS is
**survivorship-free on the earnings side**.  Survivorship-free *prices* for
delisted names remain a separate gap — see ``strategies/0055_pead_blocked`` —
so a live PEAD edge still needs a clean price source (e.g. Sharadar SEP) before
it can be trusted.  This loader powers the *kill-screen* pilot (0073): it tests
whether the SUE signal shows up at all in the liquid names we could trade.

Endpoints (all free, no API key; SEC requires a descriptive ``User-Agent`` that
identifies the caller, and asks for <=10 requests/second):

- ticker -> CIK map:  ``https://www.sec.gov/files/company_tickers.json``
- XBRL concept:       ``https://data.sec.gov/api/xbrl/companyconcept/
                        CIK##########/us-gaap/<Concept>.json``

PIT design
----------
Each EPS row carries:

- ``ref_date``     the fiscal quarter end the EPS describes (period end)
- ``release_date`` the filing date of the 10-Q/10-K that first reported it

The 10-Q *filing* date is a **conservative** proxy for the earnings announcement:
the press-release 8-K usually precedes the 10-Q by 2-4 weeks, so entering on the
filing date is strictly later than the real announcement — it cannot look ahead,
it only enters late (which makes the drift test more honest, not less).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "edgar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# SEC fair-access policy: a descriptive UA with contact info is mandatory.
# (Generic browser UAs get throttled/blocked on data.sec.gov.)
_UA = "Backtests quant research robinhumberg@gmx.de"

# us-gaap EPS concepts, in fallback order. Diluted is the standard SUE input;
# fall back to basic when a filer never tagged diluted (rare for large caps).
_EPS_CONCEPTS = ("EarningsPerShareDiluted", "EarningsPerShareBasic")

# A fiscal quarter's reporting period spans ~3 months. We keep only duration
# entries in this day band to isolate true quarterly EPS (drops 6M/9M YTD and
# 12M annual figures that 10-Q/10-K also tag).
_QUARTER_MIN_DAYS = 80
_QUARTER_MAX_DAYS = 100


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------

def _sec_get_json(url: str, retries: int = 4, delay: float = 0.5) -> dict | list:
    """GET a SEC JSON endpoint with the required UA and polite retry/backoff."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept-Encoding": "gzip, deflate"})
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode())
        except Exception as exc:  # noqa: BLE001 — surface after retries
            last_exc = exc
            time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"SEC fetch failed after {retries} tries: {url}") from last_exc


# ---------------------------------------------------------------------------
# Ticker -> CIK map
# ---------------------------------------------------------------------------

def get_cik_map(force_refresh: bool = False) -> dict[str, str]:
    """Map upper-case ticker -> 10-digit zero-padded CIK string.

    Cached as JSON under ``data/cache/edgar/``.  SEC's ``company_tickers.json``
    lists currently-registered tickers; delisted issuers keep their CIK, so a
    historical ticker may need a manual CIK (pass it straight to
    :func:`get_quarterly_eps`).
    """
    cache = CACHE_DIR / "cik_map.json"
    if cache.exists() and not force_refresh:
        return json.loads(cache.read_text(encoding="utf-8"))

    data = _sec_get_json("https://www.sec.gov/files/company_tickers.json")
    out: dict[str, str] = {}
    for row in data.values():
        out[str(row["ticker"]).upper()] = f"{int(row['cik_str']):010d}"
    cache.write_text(json.dumps(out), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Quarterly EPS
# ---------------------------------------------------------------------------

def _parse_eps_units(units: list[dict]) -> pd.DataFrame:
    """Extract originally-reported quarterly EPS rows from a concept's units.

    The **period end** (``ref_date``) is the source of truth, NOT the XBRL
    ``fy/fp`` tags: a 10-Q tags its prior-year comparative quarter with the
    *current* filing's fiscal context, so the same period end appears twice with
    different ``fy/fp`` and a later filing date.  We therefore dedupe by
    ``ref_date`` and keep the **earliest filing** — the original announcement,
    with the value as first reported (PIT-correct).
    """
    rows = []
    for e in units:
        start, end, filed = e.get("start"), e.get("end"), e.get("filed")
        val = e.get("val")
        if not (start and end and filed) or val is None:
            continue
        dur = (pd.Timestamp(end) - pd.Timestamp(start)).days
        if not (_QUARTER_MIN_DAYS <= dur <= _QUARTER_MAX_DAYS):
            continue  # quarterly (3M) durations only — drops 6M/9M YTD and 12M FY
        rows.append({
            "fp": e.get("fp"),
            "ref_date": pd.Timestamp(end),
            "release_date": pd.Timestamp(filed),
            "eps": float(val),
        })
    if not rows:
        return pd.DataFrame(columns=["fp", "ref_date", "release_date", "eps"])

    df = pd.DataFrame(rows)
    # earliest filing per period end = original announcement (drops later
    # comparatives / restatements that carry the same ref_date)
    df = df.sort_values("release_date").groupby("ref_date", as_index=False).first()
    return df.sort_values("ref_date").reset_index(drop=True)


def get_quarterly_eps(
    ticker: str,
    cik: str | None = None,
    cik_map: dict[str, str] | None = None,
    force_refresh: bool = False,
    polite_sleep: float = 0.12,
) -> pd.DataFrame:
    """Originally-reported quarterly EPS for one issuer (survivorship-free).

    Args:
        ticker: upper-cased automatically; used for the CIK lookup and cache key.
        cik: pass an explicit 10-digit CIK to bypass the ticker map (needed for
            delisted tickers not in ``company_tickers.json``).
        cik_map: pre-loaded :func:`get_cik_map` result (avoids re-fetching it per
            ticker in a loop).
        force_refresh: ignore the Parquet cache and re-fetch from SEC.
        polite_sleep: seconds to sleep after a live fetch (SEC <=10 req/s).

    Returns:
        DataFrame sorted by ``ref_date`` with columns
        ``fy, fp, ref_date, release_date, eps``.  Empty if the issuer tagged no
        usable quarterly EPS.

    Note: 10-K filings report only the full year, so **Q4 is usually absent**.
    SUE is computed year-over-year per fiscal period, so missing Q4 simply means
    no Q4 events — it does not corrupt the Q1-Q3 seasonal differences.
    """
    ticker = ticker.upper()
    cache = CACHE_DIR / f"eps_{ticker}_{hashlib.md5(ticker.encode()).hexdigest()[:6]}.parquet"
    if cache.exists() and not force_refresh:
        return pd.read_parquet(cache)

    if cik is None:
        cik_map = cik_map or get_cik_map()
        cik = cik_map.get(ticker)
        if cik is None:
            raise KeyError(f"No CIK for ticker '{ticker}' in SEC map (delisted? pass cik=).")

    df = pd.DataFrame(columns=["fy", "fp", "ref_date", "release_date", "eps"])
    for concept in _EPS_CONCEPTS:
        url = (f"https://data.sec.gov/api/xbrl/companyconcept/"
               f"CIK{cik}/us-gaap/{concept}.json")
        try:
            payload = _sec_get_json(url)
        except RuntimeError:
            time.sleep(polite_sleep)
            continue
        time.sleep(polite_sleep)
        units = payload.get("units", {}).get("USD/shares", [])
        parsed = _parse_eps_units(units)
        if not parsed.empty:
            df = parsed
            break  # diluted preferred; stop at first concept that has data

    df.to_parquet(cache)
    return df


def compute_sue(eps_df: pd.DataFrame, std_window: int = 8, min_periods: int = 4) -> pd.DataFrame:
    """Standardised Unexpected Earnings via the seasonal-random-walk model.

    ``SUE_q = (EPS_q - EPS_{q-4y}) / std(past seasonal differences)``

    The expected EPS is last year's same fiscal quarter (seasonal random walk),
    so this needs **no analyst estimates** — only reported EPS.  The normaliser
    is the rolling std of *prior* seasonal differences (``shift(1)`` → strictly
    past), so a quarter never standardises itself.

    Args:
        eps_df: output of :func:`get_quarterly_eps`.
        std_window: number of past seasonal differences in the rolling std.
        min_periods: minimum past differences required to emit a SUE.

    Returns:
        DataFrame with ``fy, fp, ref_date, release_date, eps, eps_yoy_diff, sue``
        (rows without a valid normaliser dropped).
    """
    if eps_df.empty:
        return eps_df.assign(eps_yoy_diff=[], sue=[])

    df = eps_df.sort_values("ref_date").drop_duplicates("ref_date").reset_index(drop=True)

    # Seasonal expectation = same quarter one year earlier. Match each period end
    # to the observation closest to ref_date - 365d (within ±45d) via merge_asof
    # nearest. This is robust to a missing Q4 (10-K = annual only) and to small
    # fiscal-calendar drift, unlike a fixed lag-4 on a non-contiguous series.
    prior = df[["ref_date", "eps"]].rename(
        columns={"ref_date": "prior_end", "eps": "eps_prior"}
    )
    prior["match_date"] = prior["prior_end"] + pd.Timedelta(days=365)
    prior = prior.sort_values("match_date")
    merged = pd.merge_asof(
        df.sort_values("ref_date"), prior,
        left_on="ref_date", right_on="match_date",
        direction="nearest", tolerance=pd.Timedelta(days=45),
    )
    merged["eps_yoy_diff"] = merged["eps"] - merged["eps_prior"]

    # PIT normaliser: std of *prior* seasonal diffs only (shift before rolling),
    # so a quarter never standardises itself.
    past = merged["eps_yoy_diff"].shift(1)
    merged["sue_std"] = past.rolling(std_window, min_periods=min_periods).std()
    merged["sue"] = merged["eps_yoy_diff"] / merged["sue_std"]
    merged = merged.replace([float("inf"), float("-inf")], pd.NA)
    cols = ["fp", "ref_date", "release_date", "eps", "eps_yoy_diff", "sue"]
    return merged.dropna(subset=["sue"])[cols].reset_index(drop=True)
