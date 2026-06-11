"""One-time fetch of the PIT crypto universe + price panels (sandbox off)."""
import sys
sys.path.insert(0, "src")
import pandas as pd
from quantlab import crypto_xsection as cx

print("=== Step 1: CMC weekly snapshots ===", flush=True)
uni = cx.build_universe(top_n=150)
memb = uni["membership"]
print(f"snapshots: {memb.index[0]:%Y-%m-%d} .. {memb.index[-1]:%Y-%m-%d} "
      f"({len(memb)} weeks), pairs ever in top-150 & mapped: {memb.shape[1]}")
print("members per snapshot (year mean):")
print(memb.sum(axis=1).groupby(memb.index.year).mean().round(1).to_string())

print("\n=== Step 2: Binance daily klines for all pairs ===", flush=True)
panels = cx.get_price_panels(uni)
close = panels["close"]
md = panels["membership_daily"]
print(f"close panel: {close.shape[0]} days x {close.shape[1]} pairs, "
      f"{close.index[0]:%Y-%m-%d} .. {close.index[-1]:%Y-%m-%d}")
print("investable members per day (year mean):")
print(md.sum(axis=1).groupby(md.index.year).mean().round(1).to_string())

print("\n=== Step 3: dead-coin spot checks ===", flush=True)
for d in ["2018-06-01", "2020-06-01", "2022-04-01", "2024-01-01"]:
    u = cx.get_universe_at(uni, d)
    print(f"{d}: {len(u)} mapped members; sample: {u[:12]}")

dead = [c for c in close.columns
        if close[c].last_valid_index() is not None
        and close[c].last_valid_index() < close.index[-1] - pd.Timedelta(days=30)]
print(f"\npairs whose Binance series ENDED >30d before panel end (dead/delisted): {len(dead)}")
print("examples:", sorted(dead)[:25])
