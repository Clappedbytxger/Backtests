"""Alternative Data Ingestion Pipeline for Quant-OS.

Aggregates unstructured, non-traditional data streams (GitHub developer activity, SEC
10-K/10-Q filings), structures them with local NLP (lexicon sentiment + TF-IDF text
divergence + robust anomaly z-scores) and normalises everything onto a daily calendar so
it can be matched with price data.

Public surface:
* :mod:`quantlab.altdata.nlp`     — sentiment, text divergence, anomaly statistics (pure)
* :mod:`quantlab.altdata.github`  — repository tracker (commits / stars / issues)
* :mod:`quantlab.altdata.sec`     — EDGAR 10-K/10-Q engine
* :mod:`quantlab.altdata.store`   — storage, daily normalisation, price-match, anomaly scan
* :mod:`quantlab.altdata.sources` — the curated watchlist
"""

from __future__ import annotations

from . import github, nlp, sec, sources, store

__all__ = ["nlp", "github", "sec", "store", "sources"]
