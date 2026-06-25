"""SEC EDGAR filings engine — registers new 10-K / 10-Q reports per company.

Uses the modern ``data.sec.gov`` submissions JSON (the recommended machine endpoint;
no RSS/feedparser needed) to list a company's recent annual/quarterly filings, then
fetches the primary document and strips it to plain text for the divergence + sentiment
stages. SEC's fair-access policy requires a descriptive User-Agent with a contact —
set from the project owner's e-mail.

Network failures degrade to empty lists / ``None`` so one unreachable filing never kills
the ingest loop.
"""

from __future__ import annotations

import re

_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"
_UA = "Quant-OS-AltData/1.0 robinhumberg@gmx.de"
_FORMS = ("10-K", "10-Q")


def _headers() -> dict:
    return {"User-Agent": _UA, "Accept-Encoding": "gzip, deflate"}


def fetch_recent_filings(cik: str, forms: tuple[str, ...] = _FORMS,
                         limit: int = 8, timeout: int = 20) -> list[dict]:
    """List recent 10-K/10-Q filings for a CIK (newest first). Empty list on failure.

    Each record: ``{cik, form, filing_date, accession, primary_doc, url}``. The ``url``
    points at the primary HTML document, ready for :func:`fetch_filing_text`.
    """
    import requests

    cik10 = str(cik).zfill(10)
    try:
        r = requests.get(_SUBMISSIONS.format(cik=cik10), headers=_headers(), timeout=timeout)
        if r.status_code != 200:
            return []
        recent = r.json().get("filings", {}).get("recent", {})
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    forms_l = list(zip(recent.get("form", []), recent.get("filingDate", []),
                       recent.get("accessionNumber", []), recent.get("primaryDocument", [])))
    cik_int = str(int(cik10))
    for form, fdate, acc, doc in forms_l:
        if form not in forms:
            continue
        acc_nodash = acc.replace("-", "")
        out.append({
            "cik": cik10,
            "form": form,
            "filing_date": fdate,
            "accession": acc,
            "primary_doc": doc,
            "url": _ARCHIVE.format(cik_int=cik_int, acc_nodash=acc_nodash, doc=doc),
        })
        if len(out) >= limit:
            break
    return out


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Strip an SEC HTML filing to plain text (bs4 when available, regex fallback)."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(" ")
    except Exception:  # noqa: BLE001
        text = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", text).strip()


def fetch_filing_text(url: str, max_chars: int = 400_000, timeout: int = 30) -> str:
    """Download a filing's primary document and return plain text (capped). '' on failure."""
    import requests

    try:
        r = requests.get(url, headers=_headers(), timeout=timeout)
        if r.status_code != 200:
            return ""
        body = r.text[:2_000_000]  # cap raw HTML before parsing
    except Exception:  # noqa: BLE001
        return ""
    return html_to_text(body)[:max_chars]
