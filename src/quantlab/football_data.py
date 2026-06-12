"""football-data.co.uk loader with Parquet caching.

Free historical match results + odds for 20+ European leagues. Each CSV is
one league-season. Key columns (decimal odds):

* ``FTHG/FTAG/FTR``   — full-time goals + result (H/D/A)
* ``PSH/PSD/PSA``     — Pinnacle at football-data's collection time
                        (Fri afternoon for weekend games, Tue for midweek)
* ``PSCH/PSCD/PSCA``  — Pinnacle CLOSING odds (available since season 2019/20)
* ``B365H/B365D/B365A`` (+ ``B365C*`` closing) — Bet365, same timing

The collection-time odds are the decision-time quotes for a backtest; the
closing odds exist only for CLV measurement (using them as signal input would
be look-ahead).
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "football"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"

# Divisions: E0/E1 England PL/Championship, D1/D2 Germany, SP1 Spain,
# I1 Italy, F1 France, N1 Netherlands, P1 Portugal, B1 Belgium, T1 Turkey.


def get_season(
    division: str,
    season: str,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Load one league-season, e.g. ``get_season("E0", "2324")``.

    ``season`` is football-data's 4-digit code ("2324" = 2023/24). Returns the
    raw columns plus ``Season``, with ``Date`` parsed; rows without a result
    are dropped.
    """
    path = CACHE_DIR / f"{division}_{season}.parquet"
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    url = BASE_URL.format(season=season, division=division)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    if not resp.content.strip():
        raise ValueError(f"empty CSV for {division} {season} ({url})")

    df = pd.read_csv(
        io.BytesIO(resp.content),
        encoding="latin-1",
        on_bad_lines="skip",
    )
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.dropna(subset=["Date", "FTR"]).copy()
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    df["Season"] = season

    if use_cache:
        df.to_parquet(path)
    return df


def get_extra_league(
    country: str,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Extra-Liga-Datei laden, z. B. ``get_extra_league("AUT")``.

    football-data's ``/new/{COUNTRY}.csv``-Format: EINE Datei je Land über
    alle Saisons (z. B. AUT/DNK/SWZ/POL/ARG/MEX). **Enthält NUR
    Schlussquoten** (``PSCH/PSCD/PSCA`` Pinnacle, ``B365CH/...`` Bet365,
    Max/Avg/Betfair-Exchange) — keine Collection-Quoten, daher kein
    CLV-Backtest im 0063-Sinn möglich, nur Orakel-/Bias-Checks.
    """
    path = CACHE_DIR / f"extra_{country}.parquet"
    if use_cache and not force_refresh and path.exists():
        return pd.read_parquet(path)

    url = f"https://www.football-data.co.uk/new/{country}.csv"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content), encoding="latin-1", on_bad_lines="skip")
    df.columns = [c.replace("﻿", "").strip() for c in df.columns]
    df = df.dropna(subset=["Date", "Res"]).copy()
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    df["Country"] = country

    if use_cache:
        df.to_parquet(path)
    return df


def get_matches(
    divisions: list[str],
    seasons: list[str],
    use_cache: bool = True,
) -> pd.DataFrame:
    """Concatenate several league-seasons into one match panel."""
    frames = []
    for division in divisions:
        for season in seasons:
            try:
                frames.append(get_season(division, season, use_cache=use_cache))
            except Exception as exc:  # missing file on server etc.
                print(f"  skip {division} {season}: {exc}")
    if not frames:
        raise ValueError("no data loaded")
    return pd.concat(frames, ignore_index=True)
