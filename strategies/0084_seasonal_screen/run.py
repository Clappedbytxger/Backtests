"""Strategy 0084 — Seasonal screen (handoff Seasonax ideas I0045-I0052 + I0031).

Batch kill-screen for the lower-priority seasonal Seasonax leads (#s16) plus the
Santa-rally (I0031). All share one harness: a pre-registered date-window (long or
short), tested with the DRIFT-TRAP permutation (window timing vs random same-count
timing) — the mandatory filter for Seasonax windows (lessons 0016/0017, and #s16
itself flags these as auto-optimised + drift/ survivorship-prone).

Windows pre-registered literally from #s16 (summer ~14 Jun -> late Jul / early Sep).
A lead requires permutation p<0.05 AND a bootstrap per-trade-mean CI excluding 0 in
the hypothesised direction. Single stocks are additionally SURVIVORSHIP-biased
(today's S&P 500) — flagged, treated as exploratory only.

Run:
    .venv/Scripts/python.exe strategies/0084_seasonal_screen/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import trade_stats  # noqa: E402
from quantlab.seasonal import date_window_signal, turn_of_year_signal  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)
SUMMER_A = ((6, 14), (7, 28))   # palladium/gasoline/FX (#s16)
SUMMER_B = ((6, 14), (9, 5))    # equities/sectors (#s16 ~14 Jun -> early Sep)


def fetch_ret(ticker: str, invert: bool = False) -> pd.DataFrame:
    p = get_prices(ticker, start="2000-01-01")
    if invert:
        p = p.copy()
        p["Close"] = 1.0 / p["Close"]
    return p


def test_window(prices: pd.DataFrame, smd, emd, direction: int, cost) -> dict:
    sig = direction * date_window_signal(prices.index, smd, emd)
    bt = run_backtest(prices, sig, cost_model=cost)
    ar = prices["Close"].pct_change().fillna(0.0)
    perm = permutation_test(bt["gross_returns"], ar, bt["position"], n_perm=4000, metric="sharpe")
    ts = trade_stats(bt["trades"])
    tr = bt["trades"]["pnl"] if len(bt["trades"]) else pd.Series(dtype=float)
    boot = bootstrap_ci(tr, statistic="mean", n_boot=4000) if len(tr) > 3 else {"ci_low": float("nan"), "ci_high": float("nan")}
    return {"n": ts["n_trades"], "win": ts["win_rate"], "exp_pct": ts["expectancy"] * 100,
            "perm_p": perm["p_value"], "boot_ci_pct": [boot["ci_low"] * 100, boot["ci_high"] * 100]}


def basket_test(tickers, smd, emd, direction, cost, invert=False) -> dict:
    """Equal-weight basket: average per-name windowed trade returns."""
    exps, wins, ns = [], [], []
    all_tr = []
    for t in tickers:
        try:
            p = fetch_ret(t, invert)
        except Exception:  # noqa: BLE001
            continue
        sig = direction * date_window_signal(p.index, smd, emd)
        bt = run_backtest(p, sig, cost_model=cost)
        ts = trade_stats(bt["trades"])
        if ts["n_trades"]:
            exps.append(ts["expectancy"]); wins.append(ts["win_rate"]); ns.append(ts["n_trades"])
            all_tr.extend(bt["trades"]["pnl"].tolist())
    if not all_tr:
        return {"n": 0}
    tr = pd.Series(all_tr)
    boot = bootstrap_ci(tr, statistic="mean", n_boot=4000)
    return {"n_names": len(exps), "mean_exp_pct": float(np.mean(exps) * 100),
            "mean_win": float(np.mean(wins)), "trade_mean_ci_pct": [boot["ci_low"] * 100, boot["ci_high"] * 100],
            "n_trades": len(all_tr)}


def main() -> None:
    out: dict = {}
    print(f"{'idea / asset':28}{'n':>4}{'win%':>7}{'exp%':>8}{'perm_p':>9}{'boot_CI%':>20}")

    single = [
        ("I0045 Palladium PA=F", "PA=F", SUMMER_A, +1, IBKR_FUTURES),
        ("I0046 Gasoline RB=F", "RB=F", SUMMER_A, +1, IBKR_FUTURES),
        ("I0048 Apple AAPL", "AAPL", SUMMER_B, +1, IBKR_LIQUID_ETF),
        ("I0052 JPY (1/USDJPY)", "USDJPY=X", SUMMER_A, +1, IBKR_LIQUID_ETF),
    ]
    out["single"] = {}
    for label, tk, (smd, emd), d, cost in single:
        inv = tk.startswith("USD")
        try:
            r = test_window(fetch_ret(tk, inv), smd, emd, d, cost)
        except Exception as e:  # noqa: BLE001
            print(f"{label:28} skipped ({str(e)[:30]})"); continue
        out["single"][label] = r
        print(f"{label:28}{r['n']:>4}{r['win']*100:>6.0f}%{r['exp_pct']:>+7.2f}%{r['perm_p']:>9.3f}"
              f"   [{r['boot_ci_pct'][0]:+.2f},{r['boot_ci_pct'][1]:+.2f}]")

    # baskets
    print("\nBaskets (survivorship-flagged for single stocks):")
    baskets = [
        ("I0049 S&P summer-long (surv-bias)", ["AAPL", "REGN", "MSI", "CTAS", "TDG", "PG", "PEP", "GOOGL", "AMZN", "JPM"], SUMMER_B, +1, IBKR_LIQUID_ETF, False),
        ("I0050 Energy/Semis summer-short (surv-bias)", ["EOG", "MU", "INTC", "TPR"], SUMMER_B, -1, IBKR_LIQUID_ETF, False),
        ("I0051 Sector long XLV+XLK", ["XLV", "XLK"], SUMMER_B, +1, IBKR_LIQUID_ETF, False),
        ("I0051 Sector short XLE", ["XLE"], SUMMER_B, -1, IBKR_LIQUID_ETF, False),
        ("I0047 DM-FX long (CHF/JPY/EUR)", ["USDCHF=X", "USDJPY=X", "EURUSD=X"], SUMMER_A, +1, IBKR_LIQUID_ETF, None),
    ]
    out["baskets"] = {}
    for label, tks, (smd, emd), d, cost, inv in baskets:
        # FX basket: invert the USDxxx names, keep EURUSD as-is
        if inv is None:
            exps = []
            all_tr = []
            for t in tks:
                p = fetch_ret(t, t.startswith("USD"))
                sig = d * date_window_signal(p.index, smd, emd)
                bt = run_backtest(p, sig, cost_model=cost)
                ts = trade_stats(bt["trades"])
                if ts["n_trades"]:
                    exps.append(ts["expectancy"]); all_tr.extend(bt["trades"]["pnl"].tolist())
            tr = pd.Series(all_tr); boot = bootstrap_ci(tr, "mean", 4000)
            r = {"n_names": len(exps), "mean_exp_pct": float(np.mean(exps)*100), "mean_win": float("nan"),
                 "trade_mean_ci_pct": [boot["ci_low"]*100, boot["ci_high"]*100], "n_trades": len(all_tr)}
        else:
            r = basket_test(tks, smd, emd, d, cost, inv)
        out["baskets"][label] = r
        if r.get("n", 1) == 0:
            print(f"{label:42} no data"); continue
        print(f"{label:42} names={r.get('n_names','?')} mean-exp {r['mean_exp_pct']:+.2f}% "
              f"trade-mean-CI [{r['trade_mean_ci_pct'][0]:+.2f},{r['trade_mean_ci_pct'][1]:+.2f}]%")

    # I0031 Santa rally (turn-of-year) on ^GSPC + Russell, permutation
    print("\nI0031 Santa rally (turn-of-year):")
    out["santa"] = {}
    for tk in ["^GSPC", "^RUT"]:
        p = get_prices(tk, start="2000-01-01")
        sig = turn_of_year_signal(p.index)
        bt = run_backtest(p, sig, cost_model=IBKR_LIQUID_ETF)
        ar = p["Close"].pct_change().fillna(0.0)
        perm = permutation_test(bt["gross_returns"], ar, bt["position"], n_perm=4000, metric="sharpe")
        ts = trade_stats(bt["trades"])
        out["santa"][tk] = {"n": ts["n_trades"], "win": ts["win_rate"], "exp_pct": ts["expectancy"]*100, "perm_p": perm["p_value"]}
        print(f"  {tk:8} n={ts['n_trades']} win {ts['win_rate']*100:.0f}% exp {ts['expectancy']*100:+.2f}% perm p={perm['p_value']:.3f}")

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    leads = [k for k, v in out["single"].items() if v["perm_p"] < 0.05 and v["boot_ci_pct"][0] > 0]
    print(f"\nSingle-asset leads (perm<0.05 & CI>0): {leads if leads else 'none'}")


if __name__ == "__main__":
    main()
