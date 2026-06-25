"""Strategy 0071 — Connors-style RSI(2) short-term mean reversion (daily bars).

Built for the FUNDED-account profile (City Traders Imperium): high win rate, many
small profits, smooth equity, low drawdown, overnight/swing holds (1-5 days) — the
opposite of the SMC trend strategy (0069/0070). Daily bars => cost is negligible,
sidestepping the wall that killed every intraday mean-reversion test (0012-0015,
0038-0041).

Rules (canonical Connors RSI-2, long-only):
  - Trend filter: Close > SMA(200)  (only buy dips in an uptrend)
  - Entry:        RSI(2) < entry_th  (oversold)
  - Exit:         Close > SMA(5)  [optionally RSI(2) > 70], max-hold, optional stop
All conditions use info up to the close of day t; the engine holds from t+1
(look-ahead-safe via run_backtest's shift).

Focus of the report: WIN RATE, tail risk (worst trade / DD / longest underwater),
and CTI suitability (10% static DD + 5% daily limit).

Run:  python strategies/0071_rsi2_meanreversion/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.costs import IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import compute_metrics, max_drawdown, trade_stats  # noqa: E402
from quantlab.significance import (bootstrap_ci, deflated_sharpe_ratio,  # noqa: E402
                                   permutation_test, t_test_mean_return)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ASSETS = {"SPY": "S&P 500", "QQQ": "Nasdaq-100", "DIA": "Dow Jones",
          "IWM": "Russell 2000", "GLD": "Gold"}
INDEX_SLEEVES = ["SPY", "QQQ", "DIA", "IWM"]
COST = IBKR_LIQUID_ETF  # ~2 bps/side; at daily frequency this is negligible


def rsi(close: pd.Series, period: int = 2) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    ag = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    al = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = ag / al.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def build_signal(df: pd.DataFrame, entry_th: float = 10, trend: int = 200,
                 sma_exit: int = 5, exit_rsi: float | None = None,
                 max_hold: int | None = None, stop_pct: float | None = None) -> pd.Series:
    """Stateful long-only RSI-2 position-intent series (decision-time)."""
    close = df["Close"]
    r = rsi(close, 2)
    sma_t = close.rolling(trend).mean()
    sma_e = close.rolling(sma_exit).mean()
    c, rt, st, se = close.to_numpy(), r.to_numpy(), sma_t.to_numpy(), sma_e.to_numpy()
    n = len(c)
    sig = np.zeros(n)
    in_pos = False
    entry_px = 0.0
    hold = 0
    for i in range(n):
        if not in_pos:
            if not np.isnan(st[i]) and rt[i] < entry_th and c[i] > st[i]:
                in_pos, entry_px, hold = True, c[i], 0
        else:
            hold += 1
            ex = c[i] > se[i]
            if exit_rsi is not None and rt[i] > exit_rsi:
                ex = True
            if max_hold is not None and hold >= max_hold:
                ex = True
            if stop_pct is not None and c[i] < entry_px * (1 - stop_pct):
                ex = True
            if ex:
                in_pos = False
        sig[i] = 1.0 if in_pos else 0.0
    return pd.Series(sig, index=close.index)


def longest_underwater(returns: pd.Series) -> int:
    eq = (1 + returns).cumprod()
    dd = eq / eq.cummax() - 1
    uw = (dd < -1e-9).astype(int)
    longest = cur = 0
    for f in uw:
        cur = cur + 1 if f else 0
        longest = max(longest, cur)
    return longest


def evaluate(name: str, df: pd.DataFrame, **kw) -> dict:
    sig = build_signal(df, **kw)
    res = run_backtest(df, sig, cost_model=COST)
    ret = res["returns"]
    m = compute_metrics(ret)
    ts = trade_stats(res["trades"])
    bh = compute_metrics(df["Close"].pct_change().fillna(0.0))
    return {"name": name, "res": res, "ret": ret, "m": m, "ts": ts, "bh": bh,
            "time_in_mkt": float((res["position"] != 0).mean()),
            "worst_day": float(ret.min()), "uw_days": longest_underwater(ret),
            "worst_trade": float(res["trades"]["pnl"].min()) if not res["trades"].empty else float("nan")}


def main() -> None:
    data = {}
    for t in ASSETS:
        try:
            data[t] = get_prices(t, start="1999-01-01")
        except Exception as e:
            print(f"[skip {t}] {e}")

    print("=" * 100)
    print("0071 RSI(2) Mean-Reversion — default: entry RSI<10, trend SMA200, exit Close>SMA5, long-only, daily")
    print("=" * 100)
    print(f"  {'Asset':12}{'Trades':>7}{'Win%':>6}{'PF':>6}{'Payoff':>7}{'ØHold':>6}"
          f"{'CAGR':>7}{'Sharpe':>7}{'MaxDD':>7}{'%inMkt':>7}{'B&H Sh':>7}")
    evals = {}
    for t, full in data.items():
        e = evaluate(t, full)
        evals[t] = e
        m, ts = e["m"], e["ts"]
        print(f"  {t+' '+ASSETS[t]:12}"[:12] + f"{ts['n_trades']:>7}{ts['win_rate']*100:>5.0f}%"
              f"{ts['profit_factor']:>6.2f}{ts['payoff_ratio']:>7.2f}{ts['avg_holding_days']:>6.1f}"
              f"{m['cagr']*100:>+6.1f}%{m['sharpe']:>7.2f}{m['max_drawdown']*100:>6.1f}%"
              f"{e['time_in_mkt']*100:>6.0f}%{e['bh']['sharpe']:>7.2f}")

    # equal-weight portfolio of the index sleeves
    rets = pd.DataFrame({t: evals[t]["ret"] for t in INDEX_SLEEVES if t in evals})
    rets = rets.dropna(how="all").fillna(0.0)
    port = rets.mean(axis=1)
    pm = compute_metrics(port)
    print(f"\n  Equal-Weight-Portfolio ({[t for t in INDEX_SLEEVES if t in evals]}):")
    print(f"    CAGR {pm['cagr']*100:+.1f}%  Sharpe {pm['sharpe']:.2f}  Sortino {pm['sortino']:.2f}  "
          f"MaxDD {pm['max_drawdown']*100:.1f}%  worst day {port.min()*100:.1f}%  "
          f"längste UW {longest_underwater(port)} Tage")

    # ---- battery on the portfolio ----
    mid = port.index[len(port) // 2]
    is_s = compute_metrics(port[port.index <= mid])["sharpe"]
    oos_s = compute_metrics(port[port.index > mid])["sharpe"]
    # permutation: stack the sleeve positions into a daily exposure, vs avg asset ret
    pos = pd.DataFrame({t: evals[t]["res"]["position"] for t in INDEX_SLEEVES if t in evals}).fillna(0).mean(axis=1)
    aret = pd.DataFrame({t: data[t]["Close"].pct_change() for t in INDEX_SLEEVES if t in evals}).mean(axis=1).fillna(0.0)
    com = port.index.intersection(pos.index).intersection(aret.index)
    perm = permutation_test(port.reindex(com).fillna(0), aret.reindex(com).fillna(0), pos.reindex(com).fillna(0), n_perm=2000)
    boot = bootstrap_ci(port, statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(port)
    pps = port.mean() / port.std(ddof=1)
    # n_trials: grid below = 3 entry x 2 exit x 2 stop = 12, x sleeves -> ~12
    dsr = deflated_sharpe_ratio(pps, len(port), 12, returns=port)
    print(f"\n  --- Test-Batterie (Portfolio) ---")
    print(f"    IS/OOS Sharpe: {is_s:.2f} / {oos_s:.2f}")
    print(f"    Permutation p={perm['p_value']:.3f} (Null {perm['null_mean']:.2f} vs real {perm['observed']:.2f})")
    print(f"    Bootstrap Sharpe 95%-KI [{boot['ci_low']:.2f},{boot['ci_high']:.2f}]  t-p={tt['p_value']:.4f}  DSR={dsr['psr_deflated']:.3f}")

    # ---- robustness grid + tail (stop vs no stop) ----
    print(f"\n  --- Robustheit + Tail (SPY): Stop/Max-Hold zähmen den Fat-Tail? ---")
    print(f"    {'Variante':28}{'Win%':>6}{'PF':>6}{'CAGR':>7}{'MaxDD':>7}{'worstTrade':>11}")
    spy = data["SPY"]
    variants = {
        "entry<10, kein Stop":        dict(entry_th=10),
        "entry<5 (aggressiver)":      dict(entry_th=5),
        "entry<15 (häufiger)":        dict(entry_th=15),
        "entry<10, max-hold 10d":     dict(entry_th=10, max_hold=10),
        "entry<10, Stop -5%":         dict(entry_th=10, stop_pct=0.05),
        "entry<10, exit RSI>70":      dict(entry_th=10, exit_rsi=70, sma_exit=5),
    }
    grid = {}
    for lab, kw in variants.items():
        e = evaluate("SPY", spy, **kw)
        grid[lab] = {"win": e["ts"]["win_rate"], "pf": e["ts"]["profit_factor"],
                     "cagr": e["m"]["cagr"], "maxdd": e["m"]["max_drawdown"], "worst_trade": e["worst_trade"]}
        print(f"    {lab:28}{e['ts']['win_rate']*100:>5.0f}%{e['ts']['profit_factor']:>6.2f}"
              f"{e['m']['cagr']*100:>+6.1f}%{e['m']['max_drawdown']*100:>6.1f}%{e['worst_trade']*100:>10.1f}%")

    # ---- CTI suitability ----
    scale10 = 0.10 / abs(pm["max_drawdown"])
    scale07 = 0.07 / abs(pm["max_drawdown"])
    print(f"\n  --- CTI-Eignung (Portfolio, 10% statisch + 5% daily) ---")
    print(f"    MaxDD {pm['max_drawdown']*100:.1f}% | worst day {port.min()*100:.1f}% (Tageslimit 5%)")
    print(f"    Sizing auf 7% hist. DD (Puffer): Risiko ×{scale07:.2f} -> CAGR ~{pm['cagr']*scale07*100:+.1f}%/J, "
          f"worst day ~{port.min()*scale07*100:.1f}%")
    print(f"    -> 10%-Ziel in ~{0.10/(pm['cagr']*scale07)*12:.0f} Monaten (kein Zeitlimit)")

    out = {"per_asset": {t: {"win": evals[t]["ts"]["win_rate"], "pf": evals[t]["ts"]["profit_factor"],
                             "cagr": evals[t]["m"]["cagr"], "sharpe": evals[t]["m"]["sharpe"],
                             "maxdd": evals[t]["m"]["max_drawdown"], "n_trades": evals[t]["ts"]["n_trades"],
                             "time_in_mkt": evals[t]["time_in_mkt"]} for t in evals},
           "portfolio": {"cagr": pm["cagr"], "sharpe": pm["sharpe"], "maxdd": pm["max_drawdown"],
                         "worst_day": float(port.min()), "is_sharpe": is_s, "oos_sharpe": oos_s,
                         "perm_p": perm["p_value"], "dsr": dsr["psr_deflated"]},
           "grid": grid}
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\n  gespeichert: {RESULTS/'metrics.json'}")


if __name__ == "__main__":
    main()
