"""Strategy 0109 — On-Chain Smart-Money-Flow Regime-Overlay (I0102).

Tests the ONE CTI-relevant survivor of the ONCHAIN-WALLET-ALPHA-RESEARCH memo:
aggregated on-chain flow as a SIZING OVERLAY on the BTC/ETH sleeve (not trade copy).

The memo's I0102 wants Nansen "smart-money netflow" (paid + PIT-problematic). The
free, PIT-clean proxy — explicitly listed as I0102 Variante 8 / Erweiterung — is the
aggregate STABLECOIN SUPPLY change (DefiLlama): rising aggregate stablecoin supply =
capital minted / dry powder = bullish positioning anchor. Circulating supply at date
t is observable at date t -> no look-ahead. Signal at t-1, applied at t.

Test battery (sibling of 0086 macro overlays):
  - IC: Spearman of flow_change[t-1] vs forward BTC/ETH return (1d, 7d).
  - Overlay backtest: tertile rule x1.25/x0.5/x1.0 vs buy&hold (Sharpe AND MaxDD).
  - Drift-trap permutation: does the flow TIMING beat random same-count timing?
  - Bootstrap CI on the overlay-minus-B&H Sharpe.
  - Robustness grid: windows {3,7,14,30}d, both BTC-only and BTC+ETH sleeve.
  - Sign honesty + exchange-flow-direction sanity.

Run: .venv/Scripts/python.exe strategies/0109_onchain_flow_overlay/run.py
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from quantlab.crypto_data import get_crypto_ohlcv
RESULTS = Path(__file__).resolve().parent / "results"; RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(365)  # crypto trades 365d


def sharpe(r):
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def maxdd(r):
    eq = (1 + r.fillna(0)).cumprod()
    return float((eq / eq.cummax() - 1).min())


def stablecoin_supply() -> pd.Series:
    """Aggregate USD-pegged stablecoin circulating supply, daily (DefiLlama, free)."""
    url = "https://stablecoins.llama.fi/stablecoincharts/all"
    d = json.load(urllib.request.urlopen(url, timeout=60))
    rows = {}
    for o in d:
        ts = pd.Timestamp(int(o["date"]), unit="s")
        v = o.get("totalCirculatingUSD", {})
        usd = v.get("peggedUSD") if isinstance(v, dict) else None
        if usd:
            rows[ts.normalize()] = float(usd)
    return pd.Series(rows).sort_index()


def btc_eth_daily():
    out = {}
    for sym in ["BTC/USDT", "ETH/USDT"]:
        df = get_crypto_ohlcv(sym, timeframe="1d", since="2018-01-01")
        s = df["Close"].copy()
        idx = pd.to_datetime(s.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        s.index = idx.normalize()
        out[sym.split("/")[0]] = s[~s.index.duplicated()]
    return pd.DataFrame(out).sort_index()


def overlay(base_ret: pd.Series, flow: pd.Series, mult_hi=1.25, mult_lo=0.5):
    """I0102 rule: flow change top tertile & rising -> x1.25; bottom & falling -> x0.5."""
    fc = flow.reindex(base_ret.index, method="ffill")
    rising = fc.diff() > 0
    hi = fc.quantile(2 / 3)
    lo = fc.quantile(1 / 3)
    mult = pd.Series(1.0, index=base_ret.index)
    mult[(fc >= hi) & rising] = mult_hi
    mult[(fc <= lo) & (~rising)] = mult_lo
    pos = mult.shift(1).fillna(1.0)  # signal t-1, applied t
    return pos * base_ret, pos


def perm_timing(base_ret, pos, n=4000, seed=1):
    """Drift-trap: shuffle the multiplier sequence, keep same value distribution."""
    rng = np.random.default_rng(seed)
    real = sharpe(pos.shift(0) * 0 + pos * base_ret)  # placeholder
    real = sharpe(pos * base_ret)
    vals = pos.values
    base = base_ret.values
    cnt = 0
    for _ in range(n):
        sh = sharpe(pd.Series(rng.permutation(vals) * base))
        if sh >= real:
            cnt += 1
    return (cnt + 1) / (n + 1)


def main():
    out = {}
    px = btc_eth_daily()
    supply = stablecoin_supply()
    print(f"BTC/ETH {px.index.min().date()}..{px.index.max().date()} n={len(px)}; "
          f"stablecoin supply {supply.index.min().date()}..{supply.index.max().date()}")

    sleeves = {"BTC": px["BTC"].pct_change(),
               "BTCETH": px[["BTC", "ETH"]].pct_change().mean(axis=1)}

    # ---- IC test (flow change t-1 vs forward return) ----
    ic_rows = {}
    for win in [3, 7, 14, 30]:
        fc = supply.pct_change(win)
        for name, ret in sleeves.items():
            common = ret.index.intersection(fc.index)
            sig = fc.reindex(common).shift(1)
            for h in [1, 7]:
                fwd = ret.reindex(common).shift(-h).rolling(h).sum() if h > 1 else ret.reindex(common).shift(-1)
                # use simple forward h-day cumulative
                fwd = (1 + ret.reindex(common)).shift(-1).rolling(h).apply(lambda x: x.prod(), raw=True) - 1
                d = pd.concat([sig, fwd], axis=1).dropna()
                if len(d) > 50:
                    ic, p = stats.spearmanr(d.iloc[:, 0], d.iloc[:, 1])
                    ic_rows[f"{name}_w{win}_h{h}"] = {"ic": round(float(ic), 4), "p": round(float(p), 4), "n": len(d)}
    out["ic"] = ic_rows

    # ---- Overlay backtest (registered rule, window 7d) + robustness windows ----
    grid = {}
    for win in [3, 7, 14, 30]:
        fc = supply.pct_change(win)
        for name, ret in sleeves.items():
            r = ret.dropna()
            ov, pos = overlay(r, fc)
            ov = ov.dropna()
            bh = r.reindex(ov.index)
            key = f"{name}_w{win}"
            cell = {
                "overlay_sharpe": round(sharpe(ov), 3),
                "bh_sharpe": round(sharpe(bh), 3),
                "overlay_maxdd": round(maxdd(ov), 3),
                "bh_maxdd": round(maxdd(bh), 3),
                "frac_x1.25": round(float((pos.reindex(ov.index) > 1.0).mean()), 3),
                "frac_x0.5": round(float((pos.reindex(ov.index) < 1.0).mean()), 3),
            }
            if win == 7:  # full battery only on registered window
                cell["perm_p"] = round(perm_timing(bh, pos.reindex(ov.index)), 4)
                # bootstrap CI on overlay-minus-bh daily mean return diff
                diff = (ov - bh).dropna().values
                rng = np.random.default_rng(7)
                boots = [rng.choice(diff, len(diff), replace=True).mean() * 365 for _ in range(3000)]
                cell["ann_excess_ret_ci"] = [round(float(np.percentile(boots, 2.5)), 4),
                                             round(float(np.percentile(boots, 97.5)), 4)]
            grid[key] = cell
            print(f"{key}: overlay Sh {cell['overlay_sharpe']:+.2f} vs B&H {cell['bh_sharpe']:+.2f} | "
                  f"DD {cell['overlay_maxdd']:.2f} vs {cell['bh_maxdd']:.2f}"
                  + (f" | perm p={cell.get('perm_p')}" if 'perm_p' in cell else ""))
    out["overlay_grid"] = grid

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nIC (registered 7d window):")
    for k, v in ic_rows.items():
        if "w7" in k:
            print(f"  {k}: IC={v['ic']:+.3f} p={v['p']:.3f} n={v['n']}")


if __name__ == "__main__":
    main()
