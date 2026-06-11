"""Point-in-time crypto cross-section universe — survivorship is the endgame boss.

A universe built from "coins that exist today, projected backwards" silently
drops every dead coin (delistings, rugs, zero-volume fade-outs) and fabricates
the backtest. This loader therefore builds the universe the only honest way:

1. **PIT market-cap ranks** from CoinMarketCap's weekly historical snapshots
   (the same data behind coinmarketcap.com/historical/, free, weekly Sundays
   since 2013). A snapshot taken on date *s* contains exactly the top coins as
   ranked *on s* — including everything that later died (BCC, XEM, MIOTA,
   LUNA, FTT, ...).
2. **OHLCV including delisted pairs** from Binance ``/api/v3/klines``, which
   (verified) still serves full history for delisted symbols such as BCCUSDT,
   VENUSDT, SRMUSDT, ANCUSDT. Binance-only also acts as the wash-trading
   filter: one top-tier venue, real volume.

Universe membership at date t = top ``top_n`` of the most recent snapshot
<= t (PIT by construction), minus stablecoins/wrapped/pegged assets, mapped
to Binance USDT spot pairs that have already printed a bar by t. A coin
leaves the panel when its Binance series ends (delisting) — the pre-delisting
crash returns stay in the data, which is exactly the point.

Known imperfections (documented, accepted):
- CMC symbol -> Binance ``{SYMBOL}USDT`` mapping can collide or miss renames;
  a small alias map covers the big historical cases (BCH/BCC, VET/VEN, ...).
  An unmapped coin is treated as non-investable at that date (conservative —
  it shrinks the opportunity set, never invents one).
- Exchange renames (VENUSDT -> VETUSDT) appear as two columns; rolling
  features restart after the rename. Small cost, no leak.
- Final delisting week: after the last printed bar the position's return is
  treated as 0 until the next rebalance (the crash before delisting IS
  captured; only the post-halt limbo is neutral).

All HTTP fetching happens once (run with sandbox off, lesson 0045) and lands
in a Parquet cache; backtests run offline from the cache.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "crypto_xsection"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "cmc").mkdir(exist_ok=True)
(CACHE_DIR / "binance").mkdir(exist_ok=True)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

_CMC_URL = (
    "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listings/"
    "historical?date={date}&limit={limit}&convertId=2781"
)
_BINANCE_KLINES = (
    "https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d"
    "&startTime={start}&limit=1000"
)
_VISION_S3 = (
    "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    "?delimiter=/&prefix=data/spot/monthly/klines/"
)

# Binance spot opened 2017-07; USDT pairs exist from 2017-08.
BINANCE_EPOCH = "2017-08-01"

# Pegged / wrapped / staked-duplicate assets: they sit in the CMC top ranks
# but are not a cross-sectional bet on a crypto asset. (UST/USTC is excluded
# as a *stablecoin*; its collapse shows up through LUNA, which stays in.)
EXCLUDED_SYMBOLS = {
    # stablecoins
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "PAX", "UST", "USTC",
    "FDUSD", "USDD", "GUSD", "HUSD", "SUSD", "USDN", "FRAX", "LUSD", "USDE",
    "PYUSD", "USD1", "USDS", "USDF", "EURS", "EURT", "VAI", "RSV", "USDK",
    "SAI", "MUSD", "CUSD", "DGD", "DGX", "USDX", "OUSD", "USDJ", "MIM",
    # gold / FX pegs
    "XAUT", "PAXG", "DGTX",
    # wrapped / staked duplicates of other listed assets
    "WBTC", "WETH", "STETH", "WSTETH", "WBETH", "CBETH", "RETH", "WEETH",
    "BTCB", "WBNB", "HBTC", "RENBTC", "TBTC", "CDAI", "CETH", "CUSDC",
    "WTRX", "STSOL", "MSOL", "JITOSOL", "BNSOL", "EZETH", "RSETH", "METH",
    "SOLVBTC", "LBTC", "CBBTC", "CLBTC",
    # exchange IOU/duplicate listings that shadow another asset
    "WLUNA",
}

# CMC symbol -> candidate Binance base tickers, first match with data wins.
# Covers the era where Binance's ticker differed from CMC's.
SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "BCH": ("BCH", "BCHABC", "BCC"),
    "VET": ("VET", "VEN"),
    "MIOTA": ("IOTA",),
    "EGLD": ("EGLD", "ERD"),
    "NANO": ("NANO", "XRB"),
    "BSV": ("BSV", "BCHSV"),
    "LUNC": ("LUNC", "LUNA"),
    "XEC": ("XEC", "BCHA"),
    "POL": ("POL", "MATIC"),
    "GRT": ("GRT",),
}


def _fetch(url: str, retries: int = 4, delay: float = 1.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# 1. CMC weekly PIT snapshots
# ---------------------------------------------------------------------------

def snapshot_dates(start: str = BINANCE_EPOCH, end: str | None = None) -> pd.DatetimeIndex:
    """The weekly (Sunday) CMC snapshot grid between start and end."""
    end = end or (pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=1))
    return pd.date_range(pd.Timestamp(start), end, freq="W-SUN")


def get_cmc_snapshot(date: pd.Timestamp, limit: int = 200) -> pd.DataFrame:
    """One historical top-``limit`` snapshot (cached). Columns:
    ``rank, symbol, name, mcap, volume24h, price``; index reset."""
    path = CACHE_DIR / "cmc" / f"snap_{date:%Y%m%d}.parquet"
    if path.exists():
        return pd.read_parquet(path)

    raw = json.loads(_fetch(_CMC_URL.format(date=f"{date:%Y-%m-%d}", limit=limit)))
    payload = raw.get("data", {})
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    recs = []
    for r in rows:
        q = (r.get("quotes") or [{}])[0]
        recs.append(
            {
                "rank": r.get("cmcRank") or r.get("rank"),
                "symbol": str(r.get("symbol", "")).upper(),
                "name": r.get("name", ""),
                "mcap": q.get("marketCap", np.nan),
                "volume24h": q.get("volume24h", np.nan),
                "price": q.get("price", np.nan),
            }
        )
    df = pd.DataFrame(recs).dropna(subset=["rank"])
    if df.empty:
        raise ValueError(f"CMC snapshot {date:%Y-%m-%d} came back empty.")
    df["rank"] = df["rank"].astype(int)
    df = df.sort_values("rank").reset_index(drop=True)
    df.to_parquet(path)
    return df


def get_cmc_history(
    start: str = BINANCE_EPOCH,
    end: str | None = None,
    limit: int = 200,
    pause: float = 0.4,
    progress: bool = True,
) -> pd.DataFrame:
    """All weekly snapshots stacked long: index = snap_date, plus the
    snapshot columns. Fetches only missing weeks (resumable)."""
    frames = []
    dates = snapshot_dates(start, end)
    for i, d in enumerate(dates):
        cached = (CACHE_DIR / "cmc" / f"snap_{d:%Y%m%d}.parquet").exists()
        snap = get_cmc_snapshot(d, limit=limit)
        snap = snap.assign(snap_date=d)
        frames.append(snap)
        if not cached:
            if progress and i % 25 == 0:
                print(f"  CMC snapshot {d:%Y-%m-%d} ({i + 1}/{len(dates)})")
            time.sleep(pause)
    out = pd.concat(frames, ignore_index=True)
    return out.set_index("snap_date")


# ---------------------------------------------------------------------------
# 2. Binance daily OHLCV (incl. delisted symbols)
# ---------------------------------------------------------------------------

def list_binance_usdt_symbols(force_refresh: bool = False) -> set[str]:
    """Every Binance spot symbol that EVER existed (incl. delisted), from the
    public data.binance.vision S3 listing; filtered to plain USDT pairs."""
    path = CACHE_DIR / "binance_symbols.json"
    if path.exists() and not force_refresh:
        return set(json.loads(path.read_text()))

    symbols: list[str] = []
    marker = ""
    while True:
        url = _VISION_S3 + (f"&marker={marker}" if marker else "")
        xml = _fetch(url).decode()
        page = re.findall(r"<Prefix>data/spot/monthly/klines/([^<]+)/</Prefix>", xml)
        symbols.extend(page)
        if "<IsTruncated>true</IsTruncated>" not in xml:
            break
        marker = f"data/spot/monthly/klines/{page[-1]}/"
    usdt = sorted(
        s for s in symbols
        if s.endswith("USDT")
        and not re.search(r"(UP|DOWN|BULL|BEAR)USDT$", s)  # leveraged tokens
    )
    path.write_text(json.dumps(usdt))
    return set(usdt)


def get_binance_daily(symbol: str, force_refresh: bool = False) -> pd.DataFrame:
    """Full daily OHLCV for one Binance pair (works for delisted symbols).

    Columns ``Open, High, Low, Close, Volume, QuoteVolume, NTrades`` indexed
    by UTC date (bar open time). The still-running current UTC day is dropped.
    An empty result is cached as an empty frame so dead/never-listed symbols
    are not re-queried.
    """
    path = CACHE_DIR / "binance" / f"{symbol}.parquet"
    if path.exists() and not force_refresh:
        return pd.read_parquet(path)

    from urllib.parse import quote

    cursor = int(pd.Timestamp(BINANCE_EPOCH, tz="UTC").timestamp() * 1000)
    rows: list[list] = []
    while True:
        # quote() handles the rare non-ASCII listing (e.g. 币安人生USDT).
        batch = json.loads(_fetch(_BINANCE_KLINES.format(symbol=quote(symbol), start=cursor)))
        if isinstance(batch, dict):  # API error payload (bad symbol etc.)
            batch = []
        if not batch:
            break
        rows.extend(batch)
        nxt = batch[-1][0] + 86_400_000
        if nxt <= cursor or len(batch) < 1000:
            break
        cursor = nxt
        time.sleep(0.15)

    cols = ["Open", "High", "Low", "Close", "Volume", "QuoteVolume", "NTrades"]
    if not rows:
        df = pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], name="Date"))
    else:
        raw = pd.DataFrame(
            rows,
            columns=[
                "open_time", "Open", "High", "Low", "Close", "Volume",
                "close_time", "QuoteVolume", "NTrades", "tbb", "tbq", "ig",
            ],
        ).drop_duplicates(subset="open_time")
        idx = pd.to_datetime(raw["open_time"], unit="ms", utc=True).dt.tz_localize(None)
        raw.index = pd.DatetimeIndex(idx, name="Date")
        df = raw[cols].astype(float).sort_index()
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        df = df[df.index < today]
    df.to_parquet(path)
    return df


# ---------------------------------------------------------------------------
# 3. PIT universe assembly
# ---------------------------------------------------------------------------

def _binance_candidates(cmc_symbol: str, known: set[str]) -> list[str]:
    """All Binance USDT pairs a CMC symbol may map to (alias-aware).

    Every candidate becomes a (weekly) member; the daily panel later
    intersects membership with actually-printed bars, so the pair that
    traded *at that time* wins automatically (BCH -> BCCUSDT in 2018,
    BCHUSDT from 2019). During a rename overlap both pairs can briefly
    coexist — a few weeks across nine years, negligible in a 100+-name
    cross-section.
    """
    return [
        f"{base}USDT"
        for base in SYMBOL_ALIASES.get(cmc_symbol, (cmc_symbol,))
        if f"{base}USDT" in known
    ]


def build_universe(
    start: str = BINANCE_EPOCH,
    end: str | None = None,
    top_n: int = 150,
    snapshot_limit: int = 200,
) -> dict:
    """Assemble the weekly PIT universe (cache-only after the first fetch).

    Returns dict with:
        ``snapshots``   long CMC history (snap_date-indexed),
        ``membership``  weekly bool panel (snap_date x binance symbol):
                        coin was in the PIT top ``top_n`` AND mapped to a
                        Binance USDT pair (listed or not yet — price panels
                        later gate on actual bars),
        ``mcap``        weekly PIT market cap panel (same shape),
        ``mapping``     CMC symbol -> candidate Binance pairs (alias-aware).
    """
    hist = get_cmc_history(start, end, limit=snapshot_limit)
    known = list_binance_usdt_symbols()

    hist = hist[~hist["symbol"].isin(EXCLUDED_SYMBOLS)]
    hist = hist[hist["rank"] <= top_n]

    mapping: dict[str, list[str]] = {
        sym: _binance_candidates(sym, known) for sym in hist["symbol"].unique()
    }

    hist = hist.assign(pair=hist["symbol"].map(mapping))
    hist = hist[hist["pair"].map(len) > 0].explode("pair")
    # Same Binance pair claimed by two CMC rows in one snapshot (symbol
    # collision): keep the higher-ranked (larger) one.
    hist = (
        hist.reset_index()
        .sort_values(["snap_date", "rank"])
        .drop_duplicates(subset=["snap_date", "pair"], keep="first")
        .set_index("snap_date")
    )

    membership = (
        hist.assign(v=True).pivot_table(index="snap_date", columns="pair", values="v", aggfunc="first")
        .fillna(False).astype(bool)
    )
    mcap = hist.pivot_table(index="snap_date", columns="pair", values="mcap", aggfunc="first")
    return {
        "snapshots": hist,
        "membership": membership,
        "mcap": mcap,
        "mapping": {k: v for k, v in mapping.items() if v},
    }


def get_price_panels(
    universe: dict,
    start: str = BINANCE_EPOCH,
    end: str | None = None,
    pause: float = 0.05,
    progress: bool = True,
    pit_lag_days: int = 1,
) -> dict:
    """Daily panels for every pair ever in the universe.

    Returns dict of daily DataFrames (UTC dates x pairs):
        ``close, ret, dollar_volume`` plus
        ``membership_daily`` (weekly membership forward-filled — valid from
        the snapshot date until the next snapshot, PIT by construction, and
        additionally requiring an actual printed bar that day) and
        ``mcap_daily`` (weekly PIT mcap forward-filled the same way).

    Crypto trades 24/7 — the calendar is every UTC day, no Sunday trap
    (lesson 0057 checked: rows-per-date coverage is uniform by construction,
    a pair simply has NaN before listing and after delisting).
    """
    pairs = list(universe["membership"].columns)
    closes, dvols, parent = {}, {}, {}
    for i, p in enumerate(pairs):
        cached = (CACHE_DIR / "binance" / f"{p}.parquet").exists()
        df = get_binance_daily(p)
        if len(df):
            # Delist-relist trap (LUNAUSDT: Terra dies 2022-05-13, the SAME
            # ticker relists as Luna 2.0 on 2022-05-31): an interior gap
            # > 4 days splits the series into independent segments, so no
            # return/momentum window ever spans two different assets.
            gap = df.index.to_series().diff() > pd.Timedelta(days=4)
            for k, sub in df.groupby(gap.cumsum()):
                name = p if k == 0 else f"{p}~{k + 1}"
                closes[name] = sub["Close"]
                dvols[name] = sub["QuoteVolume"]
                parent[name] = p
        if not cached:
            if progress and i % 25 == 0:
                print(f"  Binance daily {p} ({i + 1}/{len(pairs)})")
            time.sleep(pause)

    close = pd.DataFrame(closes).sort_index()
    if end:
        close = close.loc[:end]
    close = close.loc[start:]
    dvol = pd.DataFrame(dvols).reindex(close.index)

    # Bars exist on every UTC day a pair is alive; an interior gap (rare halt)
    # is bridged mark-to-last for <=3 days, never across listing/delisting.
    alive = close.notna()
    first = alive.idxmax()
    last = alive[::-1].idxmax()
    close = close.ffill(limit=3)
    for p in close.columns:
        close.loc[: first[p], p] = close.loc[: first[p], p].where(alive.loc[: first[p], p], np.nan)
        close.loc[last[p] :, p] = close.loc[last[p] :, p].where(alive.loc[last[p] :, p], np.nan)

    ret = close.pct_change(fill_method=None)

    # The exact intraday capture time of a CMC snapshot is unknown, so a
    # Sunday snapshot is only used from Sunday+`pit_lag_days` on — strictly
    # point-in-time even in the worst case (snapshot taken at end of day).
    # Segment columns (LUNAUSDT~2) inherit the parent pair's membership;
    # the bars-present intersection picks the segment alive at that time.
    parents = [parent[c] for c in close.columns]
    memb_w = universe["membership"].reindex(columns=parents, fill_value=False)
    memb_w.columns = close.columns
    memb_w.index = memb_w.index + pd.Timedelta(days=pit_lag_days)
    mcap_w = universe["mcap"].reindex(columns=parents)
    mcap_w.columns = close.columns
    mcap_w.index = mcap_w.index + pd.Timedelta(days=pit_lag_days)

    memb = (
        memb_w.reindex(close.index, method="ffill").fillna(False)
        & close.notna()
    )
    mcap = (
        mcap_w.reindex(close.index, method="ffill")
        .where(memb)
    )
    return {
        "close": close,
        "ret": ret,
        "dollar_volume": dvol.where(close.notna()),
        "membership_daily": memb,
        "mcap_daily": mcap,
    }


def get_universe_at(universe: dict, date: str | pd.Timestamp) -> list[str]:
    """PIT top-N membership at ``date``: the most recent snapshot <= date."""
    date = pd.Timestamp(date)
    memb = universe["membership"]
    snaps = memb.index[memb.index <= date]
    if len(snaps) == 0:
        return []
    row = memb.loc[snaps[-1]]
    return sorted(row.index[row])
