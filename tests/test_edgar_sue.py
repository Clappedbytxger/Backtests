"""Offline PIT / correctness guards for the EDGAR SUE loader (strategy 0073)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantlab import edgar_data as ed  # noqa: E402


def _unit(start: str, end: str, filed: str, val: float, fp: str = "Q1") -> dict:
    return {"start": start, "end": end, "filed": filed, "val": val, "fp": fp}


def test_parse_keeps_only_quarterly_durations():
    """6M/9M YTD and 12M annual durations are dropped; ~3M kept."""
    units = [
        _unit("2020-01-01", "2020-03-31", "2020-05-01", 1.0),   # ~90d  keep
        _unit("2020-01-01", "2020-06-30", "2020-08-01", 2.1),   # ~180d drop (YTD)
        _unit("2020-01-01", "2020-12-31", "2021-02-01", 4.2),   # ~365d drop (FY)
    ]
    df = ed._parse_eps_units(units)
    assert len(df) == 1
    assert df.iloc[0]["ref_date"] == pd.Timestamp("2020-03-31")


def test_parse_dedupes_by_period_keeping_earliest_filing():
    """Same period end reported twice (original + later comparative) → keep the
    first filing and its originally-reported value (PIT-correct)."""
    units = [
        _unit("2021-01-01", "2021-03-31", "2021-05-01", 1.50),  # original
        _unit("2021-01-01", "2021-03-31", "2022-05-01", 1.55),  # later restatement
    ]
    df = ed._parse_eps_units(units)
    assert len(df) == 1
    assert df.iloc[0]["eps"] == 1.50
    assert df.iloc[0]["release_date"] == pd.Timestamp("2021-05-01")


def _synthetic_eps(n_years: int = 6) -> pd.DataFrame:
    """3 quarters/year (Q4 absent, as for a 10-K-only filer), rising EPS."""
    rows = []
    base = pd.Timestamp("2014-03-31")
    eps = 1.00
    for y in range(n_years):
        for q, month_end in enumerate(["03-31", "06-30", "09-30"]):
            ref = pd.Timestamp(f"{2014 + y}-{month_end}")
            rows.append({"fp": f"Q{q+1}", "ref_date": ref,
                         "release_date": ref + pd.Timedelta(days=35),
                         "eps": round(eps, 2)})
            eps += 0.05
    return pd.DataFrame(rows)


def test_release_after_period_end():
    """Every SUE row is dated by its filing, strictly after the period it
    describes — the core no-look-ahead invariant."""
    sue = ed.compute_sue(_synthetic_eps())
    assert (sue["release_date"] > sue["ref_date"]).all()


def test_sue_normaliser_is_causal():
    """Appending a future quarter must not change an earlier quarter's SUE —
    the YoY diff and the rolling std use only past observations."""
    base = _synthetic_eps()
    sue_a = ed.compute_sue(base)

    future = pd.concat([base, pd.DataFrame([{
        "fp": "Q1", "ref_date": pd.Timestamp("2020-03-31"),
        "release_date": pd.Timestamp("2020-05-05"), "eps": 99.0,  # wild future value
    }])], ignore_index=True)
    sue_b = ed.compute_sue(future)

    merged = sue_a.merge(sue_b, on="ref_date", suffixes=("_a", "_b"))
    assert np.allclose(merged["sue_a"], merged["sue_b"], equal_nan=True)


def test_sue_yoy_difference_value():
    """SUE numerator is EPS minus the same quarter one year earlier."""
    sue = ed.compute_sue(_synthetic_eps())
    # consecutive same-quarter EPS rise by 0.15 (3 steps × 0.05) year over year
    assert np.allclose(sue["eps_yoy_diff"].dropna().unique(), [0.15], atol=1e-9)
