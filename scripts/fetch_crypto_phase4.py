"""One-time fetch of Phase-4 data: perp funding + chain TVL (sandbox off)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from quantlab import crypto_xsection as cx

uni = cx.build_universe(top_n=150)
parents = sorted({c.split("~")[0] for c in uni["membership"].columns})

print(f"=== Funding für {len(parents)} Paare ===", flush=True)
fund = cx.get_funding_panel(parents)
print(f"Funding-Panel: {fund.shape[0]} Tage x {fund.shape[1]} Paare mit Perp "
      f"({fund.index.min():%Y-%m-%d} .. {fund.index.max():%Y-%m-%d})")
cov = fund.notna().sum(axis=1)
print("Paare mit Funding je Jahr (Mittel):")
print(cov.groupby(cov.index.year).mean().round(1).to_string())

print("\n=== Chain-TVL ===", flush=True)
cmap = cx.get_chain_map()
hits = [p for p in parents if cmap.get(p[:-4])]
print(f"{len(hits)} Paare auf eine Chain mappbar; Beispiele: "
      f"{[(p, cmap[p[:-4]]) for p in hits[:8]]}")
ok = 0
for p in hits:
    try:
        s = cx.get_chain_tvl(cmap[p[:-4]])
        if len(s) > 100:
            ok += 1
    except Exception as e:
        print(f"  {p}: {type(e).__name__}")
print(f"TVL-Serien mit >100 Tagen: {ok}/{len(hits)}")
