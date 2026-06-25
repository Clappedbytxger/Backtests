"""Strategy 0069 — SMC Liquidity-Sweep + Break-of-Structure (spec Teil 7).

Per-asset backtests of the frozen config (config.yaml) through the causal SMC
engine (quantlab.smc). Prints headline performance BEFORE costs and AFTER costs
side by side for every asset, and saves trades + metrics to results/.

Data availability (cached / free):
  BTCUSD  -> ccxt Binance BTC/USDT 1h (cached)
  SPX/NDX -> Databento ES/NQ 1m resampled to M15, RTH-filtered (cached 1m)
  XAUUSD  -> Gold M5 (needs sourcing; skipped if absent)
  GBPUSD  -> GBP/USD M15 (needs sourcing; skipped if absent)

Run one asset:   python strategies/0069_smc_sweep_bos/run.py BTCUSD
Run all available: python strategies/0069_smc_sweep_bos/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
CACHE = ROOT / "data" / "cache"


# ───────────────────────── data loaders ──────────────────────────────────────

def _slice_period(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    idx = df.index
    return df[(idx >= pd.Timestamp(start, tz="UTC")) & (idx <= pd.Timestamp(end, tz="UTC"))]


def load_btc() -> pd.DataFrame | None:
    p = CACHE / "crypto" / "binance_BTC_USDT_1h.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


def _resample_m15_rth(symbol: str) -> pd.DataFrame | None:
    """ES/NQ 1m -> M15, RTH (09:30-16:00 ET). Cached to avoid recomputing."""
    out = CACHE / "futures" / f"{symbol}_c_0_ohlcv-15m_RTH.parquet"
    if out.exists():
        return pd.read_parquet(out)
    src = CACHE / "futures" / f"{symbol}_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
    if not src.exists():
        return None
    m1 = pd.read_parquet(src)
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    m15 = m1.resample("15min", label="left", closed="left").agg(agg).dropna()
    et = m15.tz_convert("US/Eastern")
    t = et.index.time
    rth = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    m15 = m15[rth].copy()
    m15.to_parquet(out)
    return m15


def load_es() -> pd.DataFrame | None:
    return _resample_m15_rth("ES")


def load_nq() -> pd.DataFrame | None:
    return _resample_m15_rth("NQ")


def _resample_from_1m(src_name: str, rule: str, out_name: str,
                      session_rth: bool = False) -> pd.DataFrame | None:
    """Resample a cached 1m parquet to ``rule`` bars; cache the result."""
    out = CACHE / "futures" / out_name
    if out.exists():
        return pd.read_parquet(out)
    src = CACHE / "futures" / src_name
    if not src.exists():
        return None
    m1 = pd.read_parquet(src)
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    bars = m1.resample(rule, label="left", closed="left").agg(agg).dropna()
    if session_rth:
        t = bars.tz_convert("US/Eastern").index.time
        m = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
        bars = bars[m].copy()
    bars.to_parquet(out)
    return bars


def load_gold() -> pd.DataFrame | None:
    # GC.v.0 = volume-front gold (the calendar front .c.0 maps to illiquid serial
    # months; GC is active only Feb/Apr/Jun/Aug/Oct/Dec). Resample 1m -> M5.
    return _resample_from_1m("GC_v_0_ohlcv-1m_2016-01-01_2026-05-31.parquet",
                             "5min", "GC_v_0_ohlcv-5m.parquet")


def load_gbpusd() -> pd.DataFrame | None:
    # GBP/USD SPOT (Dukascopy bid M15, 2016-2026) — the real instrument the video
    # trades. Falls back to the 6B-future proxy only if the spot cache is absent.
    spot = CACHE / "fx" / "GBPUSD_M15.parquet"
    if spot.exists():
        return pd.read_parquet(spot)
    return _resample_from_1m("6B_v_0_ohlcv-1m_2016-01-01_2026-05-31.parquet",
                             "15min", "6B_v_0_ohlcv-15m.parquet")


LOADERS = {"BTCUSD": load_btc, "SPX": load_es, "NDX": load_nq,
           "XAUUSD": load_gold, "GBPUSD": load_gbpusd}


def filter_session(df: pd.DataFrame, session: str) -> pd.DataFrame:
    if session == "none":
        return df
    t = df.index.tz_convert("UTC").time
    if session == "london_ny":      # 07:00-16:00 UTC (London open .. NY morning)
        m = (t >= pd.Timestamp("07:00").time()) & (t < pd.Timestamp("16:00").time())
        return df[m].copy()
    return df  # rth already applied at resample time for ES/NQ


# ───────────────────────── run + report ──────────────────────────────────────

def run_asset(name: str, cfg: dict, params: dict) -> dict | None:
    loader = LOADERS[name]
    df = loader()
    if df is None or df.empty:
        print(f"=== {name:7s} ===  [data not available — skipped]\n")
        return None

    df = _slice_period(df, params["test_start"], params["test_end"])
    df = filter_session(df, cfg["session"])
    if len(df) < 500:
        print(f"=== {name:7s} ===  [too few bars after filtering — skipped]\n")
        return None

    costs = SmcCosts(**cfg["costs"])
    res = run_smc_backtest(
        df,
        direction=cfg["direction"],
        exit_type=cfg["exit"],
        risk_frac=cfg["risk_frac"],
        n=cfg.get("n", params["n"]),
        forward=cfg.get("forward", params.get("forward")),
        k=params["k"],
        buffer_mult=cfg.get("buffer_mult", params["buffer_mult"]),
        atr_period=params["atr_period"],
        max_concurrent=cfg.get("max_concurrent", params.get("max_concurrent", 1)),
        costs=costs,
    )
    _print_asset(name, cfg, df, res)
    _save_asset(name, res)
    return res


def _ret_over_dd(m: dict) -> float:
    dd = abs(m["max_drawdown"])
    return m["total_return"] / dd if dd > 0 else float("nan")


def _print_asset(name: str, cfg: dict, df: pd.DataFrame, res: dict) -> None:
    g, n = res["metrics_gross"], res["metrics_net"]
    ts = res["trade_stats_net"]
    tr = res["trades"]
    r_gross = tr["r_mult_gross"].mean() if not tr.empty else float("nan")
    r_net = tr["r_mult_net"].mean() if not tr.empty else float("nan")

    print(f"=== {name:7s} === {cfg['label']}")
    print(f"  {cfg['timeframe']} | {cfg['direction']} | exit={cfg['exit']} | "
          f"risk={cfg['risk_frac']*100:.1f}% | session={cfg['session']} | "
          f"bars={len(df):,} | trades={ts['n_trades']} | ppy~{res['periods_per_year']}")
    print(f"  {'Kennzahl':<22}{'VOR Kosten':>14}{'NACH Kosten':>14}")
    rows = [
        ("CAGR", f"{g['cagr']*100:+.1f}%", f"{n['cagr']*100:+.1f}%"),
        ("Total Return", f"{g['total_return']*100:+.0f}%", f"{n['total_return']*100:+.0f}%"),
        ("Sharpe", f"{g['sharpe']:.2f}", f"{n['sharpe']:.2f}"),
        ("Sortino", f"{g['sortino']:.2f}", f"{n['sortino']:.2f}"),
        ("Max Drawdown", f"{g['max_drawdown']*100:.1f}%", f"{n['max_drawdown']*100:.1f}%"),
        ("Return/MaxDD", f"{_ret_over_dd(g):.2f}", f"{_ret_over_dd(n):.2f}"),
        ("Ø Trade (R)", f"{r_gross:+.3f}", f"{r_net:+.3f}"),
    ]
    for k, a, b in rows:
        print(f"  {k:<22}{a:>14}{b:>14}")
    print(f"  {'Trefferquote (netto)':<22}{'':>14}{ts['win_rate']*100:>13.0f}%")
    print(f"  {'Profit-Faktor (netto)':<22}{'':>14}{ts['profit_factor']:>14.2f}")
    print(f"  {'Ø Haltedauer (bars)':<22}{'':>14}{ts['avg_holding_days']:>14.0f}")
    print()


def _save_asset(name: str, res: dict) -> None:
    res["trades"].to_csv(RESULTS / f"trades_{name}.csv", index=False)
    out = {
        "metrics_gross": res["metrics_gross"],
        "metrics_net": res["metrics_net"],
        "trade_stats_net": res["trade_stats_net"],
        "periods_per_year": res["periods_per_year"],
        "avg_R_gross": float(res["trades"]["r_mult_gross"].mean()) if not res["trades"].empty else None,
        "avg_R_net": float(res["trades"]["r_mult_net"].mean()) if not res["trades"].empty else None,
    }
    (RESULTS / f"metrics_{name}.json").write_text(json.dumps(out, indent=2))


def main() -> None:
    cfg_all = yaml.safe_load((HERE / "config.yaml").read_text())
    params = cfg_all["params"]
    assets = cfg_all["assets"]
    which = sys.argv[1:] if len(sys.argv) > 1 else list(assets.keys())
    print(f"SMC sweep+BOS | N={params['n']} K={params['k']} "
          f"buffer={params['buffer_mult']}xATR({params['atr_period']}) | "
          f"entry Variant {params['entry_variant']} | "
          f"{params['test_start']}..{params['test_end']}\n")
    for name in which:
        run_asset(name, assets[name], params)


if __name__ == "__main__":
    main()
