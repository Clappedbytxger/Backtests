"""Strategy 0024 — Chinese-New-Year gold window: forward / cross-asset test on silver.

0023 found that a pre-CNY window survives the permutation test on gold (GC=F,
Perm p=0.009) and on physical gold (GLD, p=0.019), while the Indian Akshaya-Tritiya
window is dead. The CNY result is a *lead*, not a validated edge — and crucially it
was selected/seen on GOLD. The honest next step (the 0021 playbook) is to apply the
FROZEN rule, with zero re-fitting, to instruments it was NOT mined on.

THE FROZEN RULE (identical for every instrument, no per-asset tuning):

    Long from 15 calendar days before Chinese New Year until 2 calendar days after,
    else flat. One trade per year. Window dates pre-committed from 0023.

INSTRUMENTS:
  * GC=F  — gold future. In-sample REFERENCE only (restates 0023), clearly labelled.
  * SI=F  — silver future. The genuine OOS test: silver is the sister precious metal
            that shares CNY jewellery/gift demand (China is a top silver jewellery and
            silverware market), but the window was chosen on GOLD, never on silver. If
            the same dates work without re-fitting, the CNY precious-metal seasonality
            generalizes to an UNSEEN asset — real cross-asset out-of-sample evidence.
  * SLV   — physically-backed silver ETF. Same spot silver, different instrument, NO
            futures roll → confirms any silver result is not a continuous-contract
            artifact.

Caveat (in report): silver is more industrial and more volatile than gold, so it is a
*related* but not identical demand story — a partial, honest OOS, not a clone.

Look-ahead safe (decision-time signal, engine T+1 shift), costs on, futures negative-
price guard (CLAUDE.md 0005). Permutation test is the arbiter, as in 0021. The true
temporal forward test (live CNY 2027+) is pre-registered in the report.

Run:
    .venv/Scripts/python.exe strategies/0024_cny_silver_forward_test/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics, trade_stats, run_backtest,
    bootstrap_ci, permutation_test,
)
from quantlab.significance import t_test_mean_return  # noqa: E402
from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

# FROZEN rule (from 0023) — no per-asset tuning.
DAYS_BEFORE = 15
DAYS_AFTER = 2

# Chinese New Year (first day of the Spring Festival), Gregorian, 2000-2026.
CHINESE_NEW_YEAR = {
    2000: (2, 5), 2001: (1, 24), 2002: (2, 12), 2003: (2, 1), 2004: (1, 22),
    2005: (2, 9), 2006: (1, 29), 2007: (2, 18), 2008: (2, 7), 2009: (1, 26),
    2010: (2, 14), 2011: (2, 3), 2012: (1, 23), 2013: (2, 10), 2014: (1, 31),
    2015: (2, 19), 2016: (2, 8), 2017: (1, 28), 2018: (2, 16), 2019: (2, 5),
    2020: (1, 25), 2021: (2, 12), 2022: (2, 1), 2023: (1, 22), 2024: (2, 10),
    2025: (1, 29), 2026: (2, 17),
}

INSTRUMENTS = [
    {"ticker": "GC=F", "name": "Gold-Future (GC=F)", "role": "reference (in-sample, 0023)",
     "cost": IBKR_FUTURES, "start": "2000-01-01", "futures": True},
    {"ticker": "SI=F", "name": "Silber-Future (SI=F)", "role": "OOS asset (sister metal, unseen)",
     "cost": IBKR_FUTURES, "start": "2000-01-01", "futures": True},
    {"ticker": "SLV", "name": "Silber-ETF physisch (SLV)", "role": "OOS instrument (same spot, no roll)",
     "cost": IBKR_LIQUID_ETF, "start": "2006-05-01", "futures": False},
]


def cny_window_signal(index, days_before=DAYS_BEFORE, days_after=DAYS_AFTER,
                      name="cny_win") -> pd.Series:
    """Long (1.0) from CNY-days_before to CNY+days_after each year, else flat.

    Decision-time signal; the engine applies the T+1 execution shift, so no
    look-ahead. Dates are frozen — no re-fitting per instrument.
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for y, (mo, da) in CHINESE_NEW_YEAR.items():
        event = pd.Timestamp(y, mo, da)
        start = event - pd.Timedelta(days=days_before)
        end = event + pd.Timedelta(days=days_after)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(inst: dict) -> dict:
    prices = get_prices(inst["ticker"], start=inst["start"])
    if inst["futures"] and (prices["Close"] <= 0).any():
        raise SystemExit(f"{inst['ticker']}: non-positive close — abort (CLAUDE.md 0005).")
    asset_ret = prices["Close"].pct_change().fillna(0.0)

    sig = cny_window_signal(prices.index)
    res = run_backtest(prices, sig, cost_model=inst["cost"])
    rets = res["returns"]

    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])
    m_bh = compute_metrics(asset_ret)
    perm = permutation_test(rets, asset_ret, res["position"], n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
    # t-test on in-window daily returns only (days actually held).
    tt = t_test_mean_return(rets[res["position"].shift(1).fillna(0.0) > 0])

    return {
        "ticker": inst["ticker"], "name": inst["name"], "role": inst["role"],
        "start": str(prices.index[0].date()), "end": str(prices.index[-1].date()),
        "metrics": m, "trades": ts, "bh": m_bh,
        "exposure": float(res["position"].abs().mean()),
        "perm_p": perm["p_value"], "boot_ci": [boot["ci_low"], boot["ci_high"]],
        "ttest_p": tt["p_value"],
        "equity": res["equity"], "bh_equity": (1 + asset_ret).cumprod(),
    }


def main() -> None:
    print("Strategy 0024 — CNY gold window FROZEN rule (CNY-15 .. CNY+2): "
          "cross-asset OOS on silver")
    print("  Frozen rule applied identically to every instrument — no per-asset tuning.\n")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    rows = []
    for inst in INSTRUMENTS:
        e = evaluate(inst)
        rows.append(e)

        safe = inst["ticker"].replace("=", "").lower()
        plotting.savefig(
            plotting.plot_equity(
                e["equity"], benchmark=e["bh_equity"],
                title=f"0024 {e['name']}: CNY-Fenster (−15/+2) vs. Buy & Hold",
                strategy_label="CNY-Fenster long (15T vor bis 2T nach)",
                benchmark_label=f"{inst['ticker']} Buy & Hold",
                caption=(
                    f"Kapitalkurve {e['start']}–{e['end']}, netto nach Kosten, log-Skala. "
                    f"Identische, eingefrorene CNY-Regel wie für Gold — KEIN Re-Fitting auf "
                    f"dieses Instrument. Rolle: {e['role']}. Permutation p={e['perm_p']:.3f}.")),
            PLOTS / f"window_{safe}.png")

        print(f"  === {e['name']}  [{e['role']}] ===")
        print(f"    sample {e['start']}–{e['end']}  | exposure {e['exposure']:.1%}")
        print(f"    trades {e['trades']['n_trades']}  win {e['trades']['win_rate']:.0%}  "
              f"expectancy/trade {e['trades']['expectancy']:.2%}  "
              f"avg hold {e['trades']['avg_holding_days']:.1f}d")
        print(f"    Sharpe {e['metrics']['sharpe']:.2f} (B&H {e['bh']['sharpe']:.2f})  "
              f"CAGR {e['metrics']['cagr']:.2%}  MaxDD {e['metrics']['max_drawdown']:.2%}")
        print(f"    Permutation p {e['perm_p']:.3f}  | Bootstrap-Sharpe-KI "
              f"[{e['boot_ci'][0]:.2f}, {e['boot_ci'][1]:.2f}]  | t-Test p {e['ttest_p']:.3f}\n")

    table = [{
        "ticker": r["ticker"], "role": r["role"], "start": r["start"], "end": r["end"],
        "n_trades": r["trades"]["n_trades"], "win_rate": r["trades"]["win_rate"],
        "expectancy_pct": r["trades"]["expectancy"] * 100.0,
        "sharpe": r["metrics"]["sharpe"], "bh_sharpe": r["bh"]["sharpe"],
        "cagr": r["metrics"]["cagr"], "max_dd": r["metrics"]["max_drawdown"],
        "exposure": r["exposure"], "perm_p": r["perm_p"],
        "boot_ci": r["boot_ci"], "ttest_p": r["ttest_p"],
    } for r in rows]
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump({"frozen_rule": {"days_before": DAYS_BEFORE, "days_after": DAYS_AFTER,
                                   "anchor": "chinese_new_year"},
                   "instruments": table}, fh, indent=2, default=str)
    pd.DataFrame(table).to_csv(RESULTS / "oos_comparison.csv", index=False)

    # Headline card = the silver-future OOS test (the actual point of 0024).
    si = next(r for r in rows if r["ticker"] == "SI=F")
    card = {
        "id": "0024",
        "label": "CNY-Fenster Forward auf Silber (SI=F, −15/+2)",
        "cagr": si["metrics"]["cagr"], "annual_volatility": si["metrics"]["annual_volatility"],
        "sharpe": si["metrics"]["sharpe"], "max_drawdown": si["metrics"]["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    print(f"  results -> {RESULTS}")


if __name__ == "__main__":
    main()
