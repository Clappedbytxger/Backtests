"""Pre-fetch intraday bars from Interactive Brokers into the cache.

Start TWS / IB Gateway first (API enabled, read-only is fine), then e.g.:

    python scripts/fetch_intraday.py BTC-USD 1h "2 Y"
    python scripts/fetch_intraday.py SPY    1h "1 Y"
    python scripts/fetch_intraday.py QQQ    30m "60 D"

The agent harness then uses this deep IBKR history for any intraday timeframe; if
nothing is cached it falls back to yfinance (~2 years of 1h).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.ib_data import get_intraday  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: fetch_intraday.py SYMBOL [TIMEFRAME=1h] [DURATION='2 Y']")
        return
    symbol = sys.argv[1]
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "1h"
    duration = sys.argv[3] if len(sys.argv) > 3 else "2 Y"
    try:
        df = get_intraday(symbol, timeframe=timeframe, duration=duration, force_refresh=True)
    except Exception as e:  # noqa: BLE001
        print(f"failed: {type(e).__name__}: {e}")
        return
    print(f"{symbol} {timeframe}: {len(df)} bars  {df.index[0]} -> {df.index[-1]}  (cached)")


if __name__ == "__main__":
    main()
