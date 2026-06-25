"""Default watchlist for the Alternative Data pipeline.

Maps tradable tickers to their alternative-data handles: a GitHub repository (developer
activity is a real-time fundamental for tech/crypto) and/or an SEC CIK (10-K/10-Q
filings). The watchlist is intentionally small and curated — the pipeline is built to be
extended, not to crawl the whole market.

CIKs are the SEC's zero-padded central index keys (used by ``data.sec.gov``). Repos are
``owner/name``. ``asset_class`` drives how the dashboard groups the anomaly radar.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AltSource:
    ticker: str
    name: str
    asset_class: str            # "equity" | "crypto"
    repo: str | None = None     # GitHub "owner/name"
    cik: str | None = None      # SEC CIK (10 digits, zero-padded)
    price_ticker: str | None = None  # yfinance symbol if it differs from ``ticker``

    @property
    def yf(self) -> str:
        return self.price_ticker or self.ticker


# Curated default watchlist. Crypto tickers carry their core protocol repo; equities
# carry the company GitHub org (where meaningful) and the SEC CIK.
WATCHLIST: list[AltSource] = [
    AltSource("MSFT", "Microsoft", "equity", repo="microsoft/vscode", cik="0000789019"),
    AltSource("NVDA", "NVIDIA", "equity", repo="NVIDIA/cuda-samples", cik="0001045810"),
    AltSource("TSLA", "Tesla", "equity", cik="0001318605"),
    AltSource("CVX", "Chevron", "equity", cik="0000093410"),
    AltSource("XOM", "Exxon Mobil", "equity", cik="0000034088"),
    AltSource("COIN", "Coinbase", "equity", repo="coinbase/coinbase-pro-node", cik="0001679788"),
    AltSource("META", "Meta Platforms", "equity", repo="facebook/react", cik="0001326801"),
    AltSource("BTC-USD", "Bitcoin", "crypto", repo="bitcoin/bitcoin"),
    AltSource("ETH-USD", "Ethereum", "crypto", repo="ethereum/go-ethereum"),
    AltSource("SOL-USD", "Solana", "crypto", repo="solana-labs/solana"),
]

_BY_TICKER = {s.ticker: s for s in WATCHLIST}


def get_source(ticker: str) -> AltSource | None:
    return _BY_TICKER.get(ticker)


def github_sources() -> list[AltSource]:
    return [s for s in WATCHLIST if s.repo]


def sec_sources() -> list[AltSource]:
    return [s for s in WATCHLIST if s.cik]
