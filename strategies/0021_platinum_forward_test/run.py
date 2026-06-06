"""Strategy 0021 — Platinum turn-of-year: pre-registered forward / out-of-sample test.

0018 found, and 0019 cleaned up, a platinum turn-of-year window. The refined rule is:

    Long platinum from 18 Dec to 10 Jan each winter, else flat. One trade/winter.
    (10 Jan exit sits just BEFORE the mid-January Jan->Apr futures roll — see 0019.)

THE HONESTY PROBLEM. Seasonax mined this window on the FULL platinum history, and the
10-Jan exit refinement came from an in-sample exit scan in 0019. So there is NO clean
temporal out-of-sample period in the existing data — the IS/OOS split in 0018 is
internal consistency, not a forward test. The only *true* forward test is to trade the
frozen rule on UNSEEN future winters (Dec 2026 onward). That is pre-registered below.

What we CAN test honestly right now is whether the FROZEN rule, with zero re-fitting,
generalizes to instruments the window was NOT mined on:

  1. PPLT — physically-backed platinum ETF. Same SPOT platinum price, but a completely
     different instrument with NO futures roll. If the window works here too, the edge
     is not a PL=F continuous-contract / roll artifact (independent of 0019's reasoning).
  2. PA=F — palladium, the sister PGM metal sharing the macro (auto-catalyst demand +
     turn-of-year restocking + jewelry). The window was chosen on PLATINUM, never on
     palladium, so palladium is a genuinely UNSEEN asset. If the same dates work without
     any re-fitting, the turn-of-year PGM seasonality generalizes — real out-of-sample
     evidence for the *selection*, not just the instrument.

PL=F itself is included only as the in-sample REFERENCE (restating 0018/0019), clearly
labelled — it is not the forward proof.

Look-ahead safe (decision-time signal, engine T+1 shift), costs on, futures negative-
price guard (CLAUDE.md 0005). Permutation test is the arbiter, as always.

Run:
    .venv/Scripts/python.exe strategies/0021_platinum_forward_test/run.py
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

# FROZEN rule — identical for every instrument, no per-asset tuning.
START_MD = (12, 18)
EXIT_MD = (1, 10)

# Reference (in-sample) + two genuinely unseen instruments.
INSTRUMENTS = [
    {"ticker": "PL=F", "name": "Platin-Future (PL=F)", "role": "reference (in-sample)",
     "cost": IBKR_FUTURES, "start": "2000-01-01", "futures": True},
    {"ticker": "PPLT", "name": "Platin-ETF physisch (PPLT)", "role": "OOS instrument (same spot, no roll)",
     "cost": IBKR_LIQUID_ETF, "start": "2010-01-01", "futures": False},
    {"ticker": "PA=F", "name": "Palladium-Future (PA=F)", "role": "OOS asset (sister PGM, unseen)",
     "cost": IBKR_FUTURES, "start": "2000-01-01", "futures": True},
]


def date_window_signal(index, start_md=START_MD, end_md=EXIT_MD, name="pgm_win") -> pd.Series:
    """Long (1.0) from start_md to end_md each winter, else flat. The January exit
    wraps the year boundary. Decision-time; engine applies the T+1 shift."""
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    same_year = tuple(end_md) > tuple(start_md)
    for y in range(int(idx.year.min()) - 1, int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md)
        end_year = y if same_year else y + 1
        end = pd.Timestamp(end_year, *end_md)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(inst: dict) -> dict:
    prices = get_prices(inst["ticker"], start=inst["start"])
    if inst["futures"] and (prices["Close"] <= 0).any():
        raise SystemExit(f"{inst['ticker']}: non-positive close — abort (CLAUDE.md 0005).")
    asset_ret = prices["Close"].pct_change().fillna(0.0)

    sig = date_window_signal(prices.index)
    res = run_backtest(prices, sig, cost_model=inst["cost"])
    rets = res["returns"]

    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])
    m_bh = compute_metrics(asset_ret)
    perm = permutation_test(rets, asset_ret, res["position"], n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
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
    print("Strategy 0021 — Platinum turn-of-year FROZEN rule (18 Dec -> 10 Jan): "
          "out-of-sample on unseen instruments")
    print(f"  Frozen rule applied identically to every instrument — no per-asset tuning.\n")
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
                title=f"0021 {e['name']}: Saisonfenster 18.12.–10.1. vs. Buy & Hold",
                strategy_label="Saisonfenster long (18.12.–10.1.)",
                benchmark_label=f"{inst['ticker']} Buy & Hold",
                caption=(
                    f"Kapitalkurve {e['start']}–{e['end']}, netto nach Kosten, log-Skala. "
                    f"Identische, eingefrorene Regel wie für Platin — KEIN Re-Fitting auf "
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

    # Persist a compact comparison table.
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
        json.dump({"frozen_rule": {"start_md": list(START_MD), "exit_md": list(EXIT_MD)},
                   "instruments": table}, fh, indent=2, default=str)
    pd.DataFrame(table).to_csv(RESULTS / "oos_comparison.csv", index=False)

    print(f"  results -> {RESULTS}")


if __name__ == "__main__":
    main()
