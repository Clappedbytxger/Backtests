"""GitHub repository tracker — developer activity as an alternative fundamental.

Pulls a repo's current snapshot (stars / forks / open issues / subscribers) and its
recent daily commit counts from the public GitHub REST API. Authentication is optional
(a token in ``.github.key`` lifts the rate limit from 60 to 5000 req/h); without it the
tracker still works for a handful of repos.

All network calls degrade gracefully — a failure returns ``None`` / an empty frame so
the ingest loop never dies on one bad repo. The structured output is handed to
:mod:`quantlab.altdata.store` for daily normalisation and caching.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from quantlab.config import get_settings

_API = "https://api.github.com"
_UA = "Quant-OS-AltData/1.0 (research)"


def _read_token() -> str | None:
    key = get_settings().keys_dir / ".github.key"
    try:
        return key.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _headers() -> dict:
    h = {"User-Agent": _UA, "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    tok = _read_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def fetch_repo_snapshot(repo: str, timeout: int = 15) -> dict | None:
    """Current repo metadata snapshot. ``repo`` is ``owner/name``. None on failure."""
    import requests

    try:
        r = requests.get(f"{_API}/repos/{repo}", headers=_headers(), timeout=timeout)
        if r.status_code != 200:
            return None
        d = r.json()
    except Exception:  # noqa: BLE001 - network/JSON issues degrade to None
        return None
    return {
        "repo": repo,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stars": int(d.get("stargazers_count", 0)),
        "forks": int(d.get("forks_count", 0)),
        "open_issues": int(d.get("open_issues_count", 0)),
        "subscribers": int(d.get("subscribers_count", 0)),
        "pushed_at": d.get("pushed_at"),
    }


def fetch_daily_commits(repo: str, days: int = 90, max_pages: int = 6,
                        timeout: int = 15) -> pd.Series:
    """Daily commit counts for the last ``days`` days (UTC). Empty Series on failure.

    Lists commits with a ``since`` cut-off, paginating up to ``max_pages`` × 100 (a cap
    that keeps the rate-limit cost bounded). The result is reindexed to a complete daily
    calendar with 0 on quiet days, ready to match price data.
    """
    import requests

    since = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0)
    counts: dict[pd.Timestamp, int] = {}
    try:
        for page in range(1, max_pages + 1):
            r = requests.get(
                f"{_API}/repos/{repo}/commits",
                headers=_headers(),
                params={"since": since.isoformat(), "per_page": 100, "page": page},
                timeout=timeout,
            )
            if r.status_code != 200:
                break
            batch = r.json()
            if not batch:
                break
            for c in batch:
                ts = (c.get("commit", {}).get("author", {}) or {}).get("date")
                if not ts:
                    continue
                day = pd.Timestamp(ts).tz_convert("UTC").normalize().tz_localize(None)
                counts[day] = counts.get(day, 0) + 1
            if len(batch) < 100:
                break
    except Exception:  # noqa: BLE001
        if not counts:
            return pd.Series(dtype="float64")
    if not counts:
        return pd.Series(dtype="float64")
    s = pd.Series(counts).sort_index()
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full, fill_value=0).astype(float)
