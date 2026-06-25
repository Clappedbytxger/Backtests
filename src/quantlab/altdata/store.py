"""Structured storage + normalisation for the Alternative Data pipeline.

Ties the raw scrapers (:mod:`quantlab.altdata.github` / :mod:`quantlab.altdata.sec`) to
the local NLP (:mod:`quantlab.altdata.nlp`) and persists everything under
``data/cache/altdata/`` in a query-friendly shape:

* ``github/<repo>_commits.parquet``   — daily commit counts (the latest pull)
* ``github/<repo>_snapshots.parquet`` — appended star/issue snapshots over time
* ``filings.jsonl``                   — one record per SEC filing (form, date,
                                        divergence vs prior quarter, sentiment …)
* ``filing_text/<accession>.txt``     — the parsed filing text (kept so the *next*
                                        quarter can be diffed against it)
* ``events.jsonl``                    — the unified Alt-Data event ticker

Everything normalises onto a **daily** calendar so an alt-data stream can be overlaid on
price (:func:`series`) and screened for outliers (:func:`anomalies`). The ``seed`` path
fabricates a small realistic dataset so the dashboard is demonstrable fully offline.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.config import get_settings

from . import github as gh
from . import nlp
from . import sec
from .sources import WATCHLIST, AltSource, get_source, github_sources, sec_sources


# ── paths + jsonl helpers ─────────────────────────────────────────────────────


def _dir() -> Path:
    d = get_settings().cache_dir / "altdata"
    (d / "github").mkdir(parents=True, exist_ok=True)
    (d / "filing_text").mkdir(parents=True, exist_ok=True)
    return d


def _repo_key(repo: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", repo).strip("_")


def _append_jsonl(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _emit_event(kind: str, ticker: str, title: str, *, value: float | None = None,
                severity: str = "info", url: str | None = None) -> dict:
    ev = {"ts": _now(), "kind": kind, "ticker": ticker, "title": title,
          "value": value, "severity": severity, "url": url}
    _append_jsonl(_dir() / "events.jsonl", ev)
    return ev


# ── GitHub ingest ─────────────────────────────────────────────────────────────


def ingest_github(source: AltSource, days: int = 90) -> dict:
    """Pull a repo's snapshot + daily commits, persist, and emit anomaly events."""
    repo = source.repo
    key = _repo_key(repo)
    gdir = _dir() / "github"
    result = {"ticker": source.ticker, "repo": repo, "ok": False, "events": []}

    snap = gh.fetch_repo_snapshot(repo)
    if snap:
        snap["ticker"] = source.ticker
        sp = gdir / f"{key}_snapshots.parquet"
        hist = pd.read_parquet(sp) if sp.exists() else pd.DataFrame()
        hist = pd.concat([hist, pd.DataFrame([snap])], ignore_index=True)
        hist.to_parquet(sp)
        # star-growth anomaly vs prior snapshots
        if len(hist) > 4:
            z = nlp.robust_z(hist["stars"].astype(float).diff().dropna().values)
            if abs(z) >= 3:
                result["events"].append(_emit_event(
                    "github_stars", source.ticker,
                    f"{source.name}: ungewöhnliche Star-Bewegung in {repo} (z={z:.1f})",
                    value=round(z, 2), severity="warn"))
        result["snapshot"] = snap

    commits = gh.fetch_daily_commits(repo, days=days)
    if not commits.empty:
        commits.to_frame("commits").to_parquet(gdir / f"{key}_commits.parquet")
        z = nlp.robust_z(commits.values)
        result["commit_z"] = round(z, 2)
        if abs(z) >= 3:
            result["events"].append(_emit_event(
                "github_commits", source.ticker,
                f"{source.name}: Commit-Spike in {repo} ({int(commits.iloc[-1])} heute, z={z:.1f})",
                value=round(z, 2), severity="warn"))
        result["ok"] = True
    return result


def commit_series(repo: str) -> pd.Series:
    p = _dir() / "github" / f"{_repo_key(repo)}_commits.parquet"
    if not p.exists():
        return pd.Series(dtype="float64")
    return pd.read_parquet(p)["commits"]


# ── SEC ingest ────────────────────────────────────────────────────────────────


def _prev_filing_text(ticker: str, form: str, before_date: str) -> str:
    """Text of the previous same-form filing for this ticker (for the divergence diff)."""
    recs = [r for r in _read_jsonl(_dir() / "filings.jsonl")
            if r.get("ticker") == ticker and r.get("form") == form
            and r.get("filing_date", "") < before_date]
    if not recs:
        return ""
    recs.sort(key=lambda r: r.get("filing_date", ""))
    acc = recs[-1].get("accession")
    tp = _dir() / "filing_text" / f"{_repo_key(acc)}.txt"
    return tp.read_text(encoding="utf-8") if tp.exists() else ""


def ingest_sec(source: AltSource, max_filings: int = 4) -> dict:
    """Register new 10-K/10-Q filings: store text, compute divergence + sentiment, emit."""
    result = {"ticker": source.ticker, "cik": source.cik, "ok": False, "new": 0, "events": []}
    filings = sec.fetch_recent_filings(source.cik, limit=max_filings)
    if not filings:
        return result
    seen = {r.get("accession") for r in _read_jsonl(_dir() / "filings.jsonl")
            if r.get("ticker") == source.ticker}
    # oldest first so prior-quarter lookups resolve in order
    for f in sorted(filings, key=lambda r: r["filing_date"]):
        if f["accession"] in seen:
            continue
        text = sec.fetch_filing_text(f["url"])
        if not text:
            continue
        (_dir() / "filing_text" / f"{_repo_key(f['accession'])}.txt").write_text(text, encoding="utf-8")
        risk_now = nlp.extract_risk_factors(text)
        prev = _prev_filing_text(source.ticker, f["form"], f["filing_date"])
        risk_prev = nlp.extract_risk_factors(prev) if prev else ""
        divergence = nlp.text_divergence(risk_prev, risk_now) if prev else None
        senti = nlp.sentiment_score(text)
        rec = {
            "ticker": source.ticker, "name": source.name, "cik": source.cik,
            "form": f["form"], "filing_date": f["filing_date"],
            "accession": f["accession"], "url": f["url"],
            "n_chars": len(text), "sentiment": round(senti["compound"], 4),
            "risk_divergence": (round(divergence, 4) if divergence is not None else None),
            "ingested_at": _now(),
        }
        _append_jsonl(_dir() / "filings.jsonl", rec)
        result["new"] += 1
        sev = "alert" if (divergence is not None and divergence >= 0.15) else "info"
        dv = f" — {divergence*100:.0f}% Textänderung bei Risikofaktoren" if divergence is not None else ""
        result["events"].append(_emit_event(
            "sec_filing", source.ticker,
            f"{source.name} {f['form']} veröffentlicht{dv}",
            value=(round(divergence, 4) if divergence is not None else None),
            severity=sev, url=f["url"]))
    result["ok"] = result["new"] > 0 or True
    return result


def filings_for(ticker: str) -> list[dict]:
    recs = [r for r in _read_jsonl(_dir() / "filings.jsonl") if r.get("ticker") == ticker]
    recs.sort(key=lambda r: r.get("filing_date", ""))
    return recs


# ── ingest orchestration ──────────────────────────────────────────────────────


def ingest_all(tickers: list[str] | None = None, days: int = 90) -> dict:
    """Run GitHub + SEC ingest for the (optionally filtered) watchlist."""
    want = set(tickers) if tickers else None
    summary = {"github": [], "sec": [], "events": 0}
    for s in github_sources():
        if want and s.ticker not in want:
            continue
        r = ingest_github(s, days=days)
        summary["github"].append({"ticker": s.ticker, "ok": r["ok"], "n_events": len(r["events"])})
        summary["events"] += len(r["events"])
    for s in sec_sources():
        if want and s.ticker not in want:
            continue
        r = ingest_sec(s)
        summary["sec"].append({"ticker": s.ticker, "new": r["new"], "n_events": len(r["events"])})
        summary["events"] += len(r["events"])
    return summary


# ── read side: events, price-matched series, anomaly radar ────────────────────


def events(limit: int = 50) -> list[dict]:
    evs = _read_jsonl(_dir() / "events.jsonl")
    evs.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return evs[:limit]


def _price(ticker: str, years: int) -> pd.Series:
    from quantlab.data import get_close

    start = (pd.Timestamp.today() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")
    try:
        return get_close(ticker, start=start).dropna()
    except Exception:  # noqa: BLE001
        return pd.Series(dtype="float64")


def _sentiment_daily(ticker: str, index: pd.DatetimeIndex) -> pd.Series:
    """Step-forward sentiment from filings, aligned to a daily index."""
    recs = filings_for(ticker)
    if not recs:
        return pd.Series(dtype="float64")
    pts = pd.Series({pd.Timestamp(r["filing_date"]): float(r["sentiment"])
                     for r in recs if r.get("sentiment") is not None}).sort_index()
    if pts.empty:
        return pd.Series(dtype="float64")
    return pts.reindex(index.union(pts.index)).ffill().reindex(index)


def series(ticker: str, years: int = 3, max_points: int = 800) -> dict:
    """Price overlaid with the asset's alt-data score (commits or sentiment) + z-score.

    Returns the price line, a normalised score line with its rolling anomaly z, the
    chosen ``score_kind``, and the filing markers — the payload behind the
    Sentiment-vs-Price chart.
    """
    src = get_source(ticker)
    price = _price(src.yf if src else ticker, years)
    if price.empty:
        return {"ok": False, "error": f"no price data for {ticker}"}
    price.index = pd.to_datetime(price.index)

    score_kind = None
    score = pd.Series(dtype="float64")
    if src and src.repo:
        commits = commit_series(src.repo)
        if not commits.empty:
            score = commits.rolling(7, min_periods=1).mean()  # 7d-smoothed commit rate
            score_kind = "commits"
    if score.empty:
        senti = _sentiment_daily(ticker, price.index)
        if not senti.empty:
            score = senti
            score_kind = "sentiment"

    z = nlp.rolling_anomaly_z(score) if not score.empty else pd.Series(dtype="float64")

    # downsample price for a snappy chart; align score onto the sampled dates
    step = max(1, len(price) // max_points)
    pr = price.iloc[::step]
    score_al = score.reindex(price.index).ffill()
    z_al = z.reindex(price.index).ffill()
    score_pts = [{"t": _iso(ix), "value": _r(score_al.get(ix)), "z": _r(z_al.get(ix))}
                 for ix in pr.index] if score_kind else []
    price_pts = [{"t": _iso(ix), "close": _r(v)} for ix, v in pr.items()]

    markers = [{"t": r["filing_date"], "label": f"{r['form']}",
                "divergence": r.get("risk_divergence"), "sentiment": r.get("sentiment"),
                "url": r.get("url")} for r in filings_for(ticker)]
    return {
        "ok": True, "ticker": ticker, "name": (src.name if src else ticker),
        "score_kind": score_kind, "price": price_pts, "score": score_pts,
        "filings": markers,
    }


def anomalies() -> list[dict]:
    """One bubble per watchlist asset: alt-data anomaly z (x) vs recent price move (y).

    Bubble size = |z| (magnitude of the alt-data outlier). This is the data behind the
    Anomalie-Radar — assets whose developer activity or filing text just spiked.
    """
    pts: list[dict] = []
    for s in WATCHLIST:
        z = 0.0
        kind = None
        detail = ""
        if s.repo:
            c = commit_series(s.repo)
            if not c.empty:
                z = nlp.robust_z(c.rolling(3, min_periods=1).mean().values)
                kind = "commits"
                detail = f"{int(c.iloc[-1])} Commits/Tag"
        if kind is None:
            fs = filings_for(s.ticker)
            if fs and fs[-1].get("risk_divergence") is not None:
                dv = float(fs[-1]["risk_divergence"])
                z = dv / 0.05  # ~5% text change ≈ 1σ baseline
                kind = "filing"
                detail = f"{dv*100:.0f}% Textänderung ({fs[-1]['form']})"
        # recent price move (5d) as the y-axis
        px = _price(s.yf, 1)
        ret5 = float(px.pct_change(5).iloc[-1]) if len(px) > 6 else 0.0
        z_disp = max(-8.0, min(8.0, z))  # clamp the radar axis; magnitude kept in detail
        pts.append({
            "ticker": s.ticker, "name": s.name, "asset_class": s.asset_class,
            "kind": kind, "z": _r(z_disp), "z_raw": _r(z), "price_ret_5d": _r(ret5),
            "size": _r(min(abs(z), 6.0)), "detail": detail,
        })
    return pts


def status() -> dict:
    d = _dir()
    filings = _read_jsonl(d / "filings.jsonl")
    return {
        "n_filings": len(filings),
        "n_events": len(_read_jsonl(d / "events.jsonl")),
        "n_repos_tracked": len(list((d / "github").glob("*_commits.parquet"))),
        "n_sources": len(WATCHLIST),
        "last_event": (events(1)[0]["ts"] if _read_jsonl(d / "events.jsonl") else None),
    }


# ── offline demo seed ─────────────────────────────────────────────────────────


def seed() -> dict:
    """Fabricate a small realistic dataset so the desk renders without network access."""
    rng = np.random.default_rng(42)
    gdir = _dir() / "github"
    # clear prior seed artefacts
    for f in ["events.jsonl", "filings.jsonl"]:
        (_dir() / f).unlink(missing_ok=True)

    today = pd.Timestamp.today().normalize()
    for s in github_sources():
        idx = pd.date_range(today - pd.Timedelta(days=120), today, freq="D")
        base = rng.integers(3, 25)
        commits = pd.Series(np.clip(rng.poisson(base, len(idx)), 0, None), index=idx, dtype=float)
        commits.iloc[-3:] += rng.integers(6, 16)  # a recent spike for the radar
        commits.to_frame("commits").to_parquet(gdir / f"{_repo_key(s.repo)}_commits.parquet")
        _emit_event("github_commits", s.ticker,
                    f"{s.name}: Commit-Spike in {s.repo} ({int(commits.iloc[-1])} heute)",
                    value=round(nlp.robust_z(commits.values), 2), severity="warn")

    sample_texts = {
        "low": "The company delivered strong revenue growth and record profit with robust momentum and favorable demand.",
        "high": ("Risk factors increased materially. We face significant litigation, regulatory "
                 "investigation, supply disruption, impairment risk and heightened volatility that "
                 "could adversely affect results, alongside potential recession headwinds."),
    }
    for i, s in enumerate(sec_sources()):
        for q, form, day, key in [(0, "10-K", today - pd.Timedelta(days=200), "low"),
                                  (1, "10-Q", today - pd.Timedelta(days=8), "high" if i % 2 == 0 else "low")]:
            txt = sample_texts[key] * 40
            acc = f"SEED-{s.ticker}-{q}"
            (_dir() / "filing_text" / f"{_repo_key(acc)}.txt").write_text(txt, encoding="utf-8")
            prev = _prev_filing_text(s.ticker, form, day.strftime("%Y-%m-%d"))
            div = nlp.text_divergence(prev, txt) if prev else (0.22 if key == "high" else None)
            senti = nlp.sentiment_score(txt)
            rec = {"ticker": s.ticker, "name": s.name, "cik": s.cik, "form": form,
                   "filing_date": day.strftime("%Y-%m-%d"), "accession": acc,
                   "url": f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={s.cik}",
                   "n_chars": len(txt), "sentiment": round(senti["compound"], 4),
                   "risk_divergence": (round(div, 4) if div is not None else None),
                   "ingested_at": _now()}
            _append_jsonl(_dir() / "filings.jsonl", rec)
            if div is not None and div >= 0.15:
                _emit_event("sec_filing", s.ticker,
                            f"{s.name} {form} veröffentlicht — {div*100:.0f}% Textänderung bei Risikofaktoren",
                            value=round(div, 4), severity="alert",
                            url=rec["url"])
            elif q == 1:
                _emit_event("sec_filing", s.ticker, f"{s.name} {form} veröffentlicht",
                            value=(round(div, 4) if div is not None else None), severity="info")
    return {"ok": True, **status()}


# ── small formatters ──────────────────────────────────────────────────────────


def _r(x, d: int = 4):
    try:
        v = float(x)
        return None if (np.isnan(v) or np.isinf(v)) else round(v, d)
    except (TypeError, ValueError):
        return None


def _iso(ts) -> str:
    return str(ts.date()) if hasattr(ts, "date") else str(ts)
