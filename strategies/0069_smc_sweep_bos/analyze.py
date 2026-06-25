"""Strategy 0069 — Phase 2 (benchmarks + combined portfolio) and the Teil-8
validation battery: permutation, bootstrap, IS/OOS, cost-sensitivity, parameter
plateau, distribution stats and DSR with an honest n_trials.

Reuses the loaders and frozen config from run.py. Everything is reported net of
costs and (where relevant) gross alongside, so the "vor/nach Kosten" pair stays
visible at each step.

Run:  python strategies/0069_smc_sweep_bos/analyze.py [ASSET ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.metrics import compute_metrics, sharpe_ratio  # noqa: E402
from quantlab.significance import (bootstrap_ci, deflated_sharpe_ratio,  # noqa: E402
                                   permutation_test, t_test_mean_return)
from quantlab.smc import SmcCosts, run_smc_backtest  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("smc_run", Path(__file__).with_name("run.py"))
_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

GRID_N = [2, 3]
GRID_K = [2, 3, 5]


# ───────────────────────── helpers ───────────────────────────────────────────

def load_asset_bars(name: str, cfg: dict, params: dict):
    """Session-filtered bars used by the SMC engine."""
    df = _run.LOADERS[name]()
    if df is None or df.empty:
        return None
    df = _run._slice_period(df, params["test_start"], params["test_end"])
    return _run.filter_session(df, cfg["session"])


def daily_close(name: str, params: dict) -> pd.Series:
    """Full (un-session-filtered) daily close for an honest buy & hold."""
    df = _run.LOADERS[name]()
    df = _run._slice_period(df, params["test_start"], params["test_end"])
    c = df["Close"]
    c.index = pd.DatetimeIndex(c.index).tz_convert("UTC")
    return c.resample("1D").last().dropna()


def buy_and_hold(name: str, params: dict) -> dict:
    c = daily_close(name, params)
    ret = c.pct_change().dropna()
    return compute_metrics(ret, periods_per_year=365 if name == "BTCUSD" else 252)


def donchian_baseline(df: pd.DataFrame, direction: str, cost_rt: float,
                      lookback: int = 20, ppy: int = 252) -> dict:
    """Fast Donchian trend baseline on the same bars (spec Teil 7.3).

    Long when close breaks the prior ``lookback``-bar high, short (if allowed)
    on the prior low; hold until the opposite break. Net of a round-trip cost on
    each position change.
    """
    c = df["Close"]
    hi = df["High"].rolling(lookback).max().shift(1)
    lo = df["Low"].rolling(lookback).min().shift(1)
    pos = pd.Series(np.nan, index=df.index)
    pos[c > hi] = 1.0
    pos[c < lo] = 0.0 if direction == "long" else -1.0
    pos = pos.ffill().fillna(0.0)
    bar_ret = c.pct_change().fillna(0.0)
    gross = pos.shift(1).fillna(0.0) * bar_ret
    switch = pos.diff().abs().fillna(0.0)
    net = gross - switch * cost_rt
    # aggregate to daily for comparable annualization
    d = net.groupby(pd.DatetimeIndex(net.index).tz_convert("UTC").normalize()).sum()
    return compute_metrics(d, periods_per_year=ppy)


def daily_position(trades: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    """±1/0 daily exposure reconstructed from the trade log (for permutation)."""
    dates = pd.DatetimeIndex(idx).tz_localize(None).normalize().unique().sort_values()
    pos = pd.Series(0.0, index=dates)
    for _, t in trades.iterrows():
        a = pd.Timestamp(t["entry_time"]).tz_localize(None).normalize()
        b = pd.Timestamp(t["exit_time"]).tz_localize(None).normalize()
        pos.loc[(pos.index >= a) & (pos.index <= b)] = float(t["direction"])
    return pos


def asset_daily_returns(name: str, idx: pd.DatetimeIndex, params: dict) -> pd.Series:
    c = daily_close(name, params)
    c.index = pd.DatetimeIndex(c.index).tz_localize(None).normalize()
    target = pd.DatetimeIndex(idx).tz_localize(None).normalize().unique().sort_values()
    return c.reindex(target).ffill().pct_change().fillna(0.0)


def _run_net(df, cfg, params, costs):
    return run_smc_backtest(
        df, direction=cfg["direction"], exit_type=cfg["exit"],
        risk_frac=cfg["risk_frac"], n=cfg.get("n", params["n"]),
        forward=cfg.get("forward", params.get("forward")), k=params["k"],
        buffer_mult=cfg.get("buffer_mult", params["buffer_mult"]),
        atr_period=params["atr_period"],
        max_concurrent=cfg.get("max_concurrent", params.get("max_concurrent", 1)),
        costs=costs)


# ───────────────────────── battery per asset ─────────────────────────────────

def battery(name: str, cfg: dict, params: dict) -> dict | None:
    df = load_asset_bars(name, cfg, params)
    if df is None or len(df) < 500:
        print(f"=== {name} ===  [data not available]\n")
        return None

    costs = SmcCosts(**cfg["costs"])
    res = _run_net(df, cfg, params, costs)
    tr = res["trades"]
    net = res["returns_net"]
    ppy = res["periods_per_year"]
    if tr.empty:
        print(f"=== {name} ===  [no trades]\n")
        return None

    # permutation vs random timing of the same exposure on the asset
    pos = daily_position(tr, df.index)
    aret = asset_daily_returns(name, df.index, params)
    common = net.index.intersection(pos.index).intersection(aret.index)
    perm = permutation_test(net.reindex(common).fillna(0.0),
                            aret.reindex(common).fillna(0.0),
                            pos.reindex(common).fillna(0.0), n_perm=2000)

    # bootstrap CI on mean net R per trade (the per-trade edge)
    rmult = tr["r_mult_net"].reset_index(drop=True)
    boot = bootstrap_ci(rmult, statistic="mean", n_boot=2000)
    tt = t_test_mean_return(rmult)

    # IS/OOS split over the construction (first half / second half)
    mid = df.index[len(df) // 2]
    is_df, oos_df = df[df.index <= mid], df[df.index > mid]
    is_s = _run_net(is_df, cfg, params, costs)["metrics_net"]["sharpe"]
    oos_s = _run_net(oos_df, cfg, params, costs)["metrics_net"]["sharpe"]

    # cost sensitivity {0, 1x, 2x}
    cs = {}
    for fac, lab in [(0.0, "0x"), (1.0, "1x"), (2.0, "2x")]:
        r = _run_net(df, cfg, params, costs.scaled(fac))
        cs[lab] = {"sharpe": r["metrics_net"]["sharpe"],
                   "avg_R": float(r["trades"]["r_mult_net"].mean()),
                   "cagr": r["metrics_net"]["cagr"]}

    # distribution: top-5/top-10 share of total profit, median trade
    pnl = tr["pnl_frac_net"].to_numpy()
    pos_sum = pnl[pnl > 0].sum()
    top5 = np.sort(pnl)[-5:].sum()
    top10 = np.sort(pnl)[-10:].sum()
    dist = {
        "median_R": float(np.median(tr["r_mult_net"])),
        "mean_R": float(tr["r_mult_net"].mean()),
        "top5_share": float(top5 / pos_sum) if pos_sum > 0 else float("nan"),
        "top10_share": float(top10 / pos_sum) if pos_sum > 0 else float("nan"),
    }

    out = {
        "n_trades": int(len(tr)),
        "sharpe_net": res["metrics_net"]["sharpe"],
        "sharpe_gross": res["metrics_gross"]["sharpe"],
        "perm_p": perm["p_value"], "perm_null_mean": perm["null_mean"],
        "boot_meanR_ci": [boot["ci_low"], boot["ci_high"]],
        "ttest_p": tt["p_value"],
        "is_sharpe": is_s, "oos_sharpe": oos_s,
        "cost_sens": cs, "dist": dist,
    }
    _print_battery(name, cfg, out)
    return out


def _print_battery(name: str, cfg: dict, o: dict) -> None:
    print(f"=== {name} === {cfg['label']}  (netto)")
    print(f"  Trades {o['n_trades']} | Sharpe vor {o['sharpe_gross']:.2f} -> nach {o['sharpe_net']:.2f}")
    print(f"  Permutation p={o['perm_p']:.3f} (Null-Mittel Sharpe {o['perm_null_mean']:.2f})")
    print(f"  Bootstrap mean-R 95%-KI [{o['boot_meanR_ci'][0]:+.3f}, {o['boot_meanR_ci'][1]:+.3f}]"
          f"  t-Test p={o['ttest_p']:.3f}")
    print(f"  IS/OOS Sharpe (netto): {o['is_sharpe']:.2f} / {o['oos_sharpe']:.2f}")
    cs = o["cost_sens"]
    print(f"  Kosten-Sens. Sharpe 0x/1x/2x: {cs['0x']['sharpe']:.2f} / "
          f"{cs['1x']['sharpe']:.2f} / {cs['2x']['sharpe']:.2f}  |  "
          f"Ø-R 0x/1x/2x: {cs['0x']['avg_R']:+.3f}/{cs['1x']['avg_R']:+.3f}/{cs['2x']['avg_R']:+.3f}")
    d = o["dist"]
    print(f"  Median-R {d['median_R']:+.3f} | Top-5 {d['top5_share']*100:.0f}% / "
          f"Top-10 {d['top10_share']*100:.0f}% des Bruttogewinns\n")


# ───────────────────────── benchmarks + parameter grid ───────────────────────

def benchmarks(assets: dict, params: dict) -> None:
    print("── Benchmarks: SMC (netto) vs Buy & Hold vs Donchian(20) ──")
    print(f"  {'Asset':8}{'SMC Sharpe':>12}{'B&H Sharpe':>12}{'Donch Sharpe':>14}"
          f"{'SMC CAGR':>10}{'B&H CAGR':>10}")
    for name, cfg in assets.items():
        df = load_asset_bars(name, cfg, params)
        if df is None or len(df) < 500:
            continue
        costs = SmcCosts(**cfg["costs"])
        res = _run_net(df, cfg, params, costs)
        if res["trades"].empty:
            continue
        bh = buy_and_hold(name, params)
        cost_rt = 2 * (cfg["costs"]["commission_bps"] + cfg["costs"]["spread_bps"]) / 1e4
        don = donchian_baseline(df, cfg["direction"], cost_rt, ppy=res["periods_per_year"])
        print(f"  {name:8}{res['metrics_net']['sharpe']:>12.2f}{bh['sharpe']:>12.2f}"
              f"{don['sharpe']:>14.2f}{res['metrics_net']['cagr']*100:>9.1f}%"
              f"{bh['cagr']*100:>9.1f}%")
    print()


def param_grid(assets: dict, params: dict) -> dict:
    """Scan N x K around the defaults; report net Sharpe plateau + n_trials."""
    print("── Parameter-Plateau: netto Sharpe über N x K (Default N=2,K=3) ──")
    cells = 0
    grid_out = {}
    for name, cfg in assets.items():
        df = load_asset_bars(name, cfg, params)
        if df is None or len(df) < 500:
            continue
        costs = SmcCosts(**cfg["costs"])
        row = []
        g = {}
        for nn in GRID_N:
            for kk in GRID_K:
                p2 = {**params, "n": nn, "k": kk}
                r = _run_net(df, cfg, p2, costs)
                s = r["metrics_net"]["sharpe"]
                g[f"N{nn}K{kk}"] = float(s)
                row.append(f"N{nn}K{kk}={s:+.2f}")
                cells += 1
        grid_out[name] = g
        print(f"  {name:8} " + "  ".join(row))
    print(f"  -> Gitter-Zellen gesamt (n_trials-Beitrag): {cells}\n")
    return {"grid": grid_out, "cells": cells}


# ───────────────────────── combined portfolio ────────────────────────────────

def combined_portfolio(assets: dict, params: dict) -> None:
    print("── Kombiniertes Portfolio (gleichgewichtete Asset-Sleeves, netto) ──")
    series = {}
    for name, cfg in assets.items():
        df = load_asset_bars(name, cfg, params)
        if df is None or len(df) < 500:
            continue
        res = _run_net(df, cfg, params, SmcCosts(**cfg["costs"]))
        if res["trades"].empty:
            continue
        s = res["returns_net"].copy()
        s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
        series[name] = s
    if not series:
        print("  [keine Assets]\n"); return
    allret = pd.DataFrame(series).sort_index()
    full = pd.date_range(allret.index.min(), allret.index.max(), freq="D")
    allret = allret.reindex(full).fillna(0.0)
    port = allret.mean(axis=1)   # equal-weight across sleeves
    m = compute_metrics(port, periods_per_year=365)
    print(f"  Assets: {list(series)}")
    print(f"  Portfolio Sharpe {m['sharpe']:.2f} | CAGR {m['cagr']*100:+.1f}% | "
          f"MaxDD {m['max_drawdown']*100:.1f}% | Return/MaxDD "
          f"{m['total_return']/abs(m['max_drawdown']):.2f}")
    contrib = {k: float((1+allret[k]).prod()-1) for k in series}
    print("  Beitrag je Asset (Total Return des Sleeves, netto): "
          + ", ".join(f"{k} {v*100:+.0f}%" for k, v in contrib.items()) + "\n")


def main() -> None:
    cfg_all = yaml.safe_load((HERE / "config.yaml").read_text())
    params, assets = cfg_all["params"], cfg_all["assets"]
    which = sys.argv[1:] if len(sys.argv) > 1 else list(assets.keys())
    sub = {k: assets[k] for k in which}

    print("######## Phase 2 — Benchmarks ########\n")
    benchmarks(sub, params)
    combined_portfolio(sub, params)

    print("######## Teil 8 — Validierungs-Batterie (netto) ########\n")
    batt = {}
    for name in which:
        b = battery(name, assets[name], params)
        if b:
            batt[name] = b

    grid = param_grid(sub, params)

    # honest n_trials: asset x (N x K grid) cells actually scanned
    n_trials = grid["cells"]
    print("── Deflated Sharpe (ehrliches n_trials = gescannte Gitter-Zellen) ──")
    for name, b in batt.items():
        df = load_asset_bars(name, assets[name], params)
        res = _run_net(df, assets[name], params, SmcCosts(**assets[name]["costs"]))
        net = res["returns_net"]
        per_period_sharpe = net.mean() / net.std(ddof=1) if net.std(ddof=1) > 0 else 0.0
        dsr = deflated_sharpe_ratio(per_period_sharpe, len(net), n_trials, returns=net)
        print(f"  {name:8} DSR={dsr['psr_deflated']:.3f}  (per-period Sharpe {per_period_sharpe:.3f})")
    print()

    (RESULTS / "battery.json").write_text(json.dumps(
        {"battery": batt, "grid": grid, "n_trials": n_trials}, indent=2, default=float))


if __name__ == "__main__":
    main()
