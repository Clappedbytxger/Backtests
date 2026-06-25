"""Strategy 0072 — RSI(2) mean reversion, BROAD ETF basket + capital deployment +
VIX-regime tail control. The funded-account (CTI) iteration of 0071.

0071 found a real edge (win 74%, perm p=0.024) but it failed CTI: CAGR ~3% (90%
in cash) and worst day -6.7% (> 5% daily limit). Three fixes here:
  1. BROAD basket (US indices + 9 sectors + regions + TLT/GLD) -> dips fire more
     often across uncorrelated names -> more capital deployed -> higher CAGR.
  2. DEPLOY capital on the currently-active signals (f per active sleeve, total
     capped) instead of 1/N (which left ~90% idle).
  3. VIX-regime tail control: block new dip-buys when VIX is elevated, and exit
     when VIX spikes -> cut the crash-dip days that breach the 5% daily limit.

Gate: CTI-viable only if worst day < 5% AND CAGR-at-7%-DD is double-digit.

Run:  python strategies/0072_rsi2_basket/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import (bootstrap_ci, deflated_sharpe_ratio,  # noqa: E402
                                   permutation_test, t_test_mean_return)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

BASKET = ["SPY", "QQQ", "DIA", "IWM",                       # US indices
          "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB",  # sectors
          "EFA", "EEM", "GLD", "TLT"]                        # regions + diversifiers
COST_FRAC = 0.0002  # ~2 bps/side ETF, daily -> negligible


def rsi(close: pd.Series, period: int = 2) -> pd.Series:
    delta = close.diff()
    ag = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    al = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)


def sleeve_signal(df, vix, entry_th=10, trend=200, sma_exit=5,
                  vix_entry_max=None, vix_exit=None, stop_pct=None):
    """Decision-time 0/1 long signal with optional VIX filter + stop."""
    close = df["Close"]
    r = rsi(close, 2)
    st = close.rolling(trend).mean()
    se = close.rolling(sma_exit).mean()
    v = vix.reindex(close.index).ffill() if vix is not None else None
    c, rt, stv, sev = close.to_numpy(), r.to_numpy(), st.to_numpy(), se.to_numpy()
    vv = v.to_numpy() if v is not None else None
    n = len(c)
    sig = np.zeros(n); in_pos = False; entry_px = 0.0
    for i in range(n):
        if not in_pos:
            ok = (not np.isnan(stv[i])) and rt[i] < entry_th and c[i] > stv[i]
            if ok and vix_entry_max is not None and vv is not None and vv[i] > vix_entry_max:
                ok = False  # no dip-buys in a high-VIX panic
            if ok:
                in_pos, entry_px = True, c[i]
        else:
            ex = c[i] > sev[i]
            if vix_exit is not None and vv is not None and vv[i] > vix_exit:
                ex = True
            if stop_pct is not None and c[i] < entry_px * (1 - stop_pct):
                ex = True
            if ex:
                in_pos = False
        sig[i] = 1.0 if in_pos else 0.0
    return pd.Series(sig, index=close.index)


def longest_uw(returns):
    eq = (1+returns).cumprod(); dd = eq/eq.cummax()-1
    uw = (dd < -1e-9).astype(int); longest = cur = 0
    for f in uw:
        cur = cur+1 if f else 0; longest = max(longest, cur)
    return longest


def build_portfolio(data, vix, f=0.15, max_deploy=1.0, **sig_kw):
    """Deploy `f` capital per active sleeve, total capped at `max_deploy`."""
    sigs, rets, trades_all = {}, {}, []
    for t, df in data.items():
        s = sleeve_signal(df, vix, **sig_kw)
        pos = s.shift(1).fillna(0.0)                 # held from t+1 (look-ahead-safe)
        sigs[t] = pos
        rets[t] = df["Close"].pct_change().fillna(0.0)
        # per-sleeve trades for win-rate
        chg = pos.diff().fillna(pos)
        # extract trade pnls
        in_t = False; ent = 0
        pv = pos.to_numpy(); rv = df["Close"].pct_change().fillna(0).to_numpy()
        for i in range(len(pv)):
            if not in_t and pv[i] > 0:
                in_t, ent = True, i
            elif in_t and pv[i] == 0:
                trades_all.append(float(np.prod(1+rv[ent:i])-1) - 2*COST_FRAC); in_t = False
    common = sorted(set().union(*[s.index for s in sigs.values()]))
    P = pd.DataFrame(sigs).reindex(common).fillna(0.0)
    R = pd.DataFrame(rets).reindex(common).fillna(0.0)
    raw = P * f
    total = raw.sum(axis=1)
    scale = np.where(total > max_deploy, max_deploy / total.replace(0, np.nan), 1.0)
    W = raw.mul(pd.Series(scale, index=raw.index).fillna(1.0), axis=0)
    gross = (W * R).sum(axis=1)
    turn = W.diff().abs().sum(axis=1).fillna(W.abs().sum(axis=1))
    net = gross - turn * COST_FRAC
    return net, W, pd.Series(trades_all)


def metrics_row(net, trades):
    m = compute_metrics(net)
    win = float((trades > 0).mean()) if len(trades) else float("nan")
    return {"cagr": m["cagr"], "sharpe": m["sharpe"], "sortino": m["sortino"],
            "maxdd": m["max_drawdown"], "worst_day": float(net.min()),
            "uw": longest_uw(net), "win": win, "n_trades": int(len(trades)),
            "avg_deploy": None}


def main() -> None:
    data = {}
    for t in BASKET:
        try:
            data[t] = get_prices(t, start="2004-01-01")
        except Exception as e:
            print(f"[skip {t}] {e}")
    try:
        vix = get_prices("^VIX", start="2004-01-01")["Close"]
    except Exception:
        vix = None
    print(f"Korb: {len(data)} ETFs, VIX: {'ja' if vix is not None else 'nein'}\n")

    print("=" * 104)
    print("0072 RSI(2) Broad-Basket + Deployment + VIX-Tail-Control   (Gate: worst day <5% & CAGR@7%DD zweistellig)")
    print("=" * 104)
    print(f"  {'Variante':40}{'CAGR':>7}{'Sharpe':>7}{'MaxDD':>7}{'worstD':>8}{'Win%':>6}{'Trades':>7}{'UW':>6}")
    configs = {
        "1/N-Baseline (f klein, kein VIX)":   dict(f=0.06, max_deploy=1.0),
        "Deploy f=0.15, cap100, kein VIX":    dict(f=0.15, max_deploy=1.0),
        "Deploy f=0.15, cap100, VIX-entry<30": dict(f=0.15, max_deploy=1.0, vix_entry_max=30),
        "Deploy f=0.15, cap80, VIX e<30 x>40": dict(f=0.15, max_deploy=0.8, vix_entry_max=30, vix_exit=40),
        "Deploy f=0.20, cap100, VIX e<28 x>38": dict(f=0.20, max_deploy=1.0, vix_entry_max=28, vix_exit=38),
        "Deploy f=0.15, cap70, VIX e<30 x>40 +Stop8%": dict(f=0.15, max_deploy=0.7, vix_entry_max=30, vix_exit=40, stop_pct=0.08),
    }
    out = {}
    best = None
    for lab, kw in configs.items():
        net, W, trades = build_portfolio(data, vix, **kw)
        r = metrics_row(net, trades)
        r["avg_deploy"] = float(W.sum(axis=1).mean())
        out[lab] = r
        print(f"  {lab:40}{r['cagr']*100:>+6.1f}%{r['sharpe']:>7.2f}{r['maxdd']*100:>6.1f}%"
              f"{r['worst_day']*100:>7.1f}%{r['win']*100:>5.0f}%{r['n_trades']:>7}{r['uw']:>6}")
        if best is None or r["sharpe"] > out[best]["sharpe"]:
            best = lab
    print(f"  (avg. Kapital-Deployment je Variante: " +
          ", ".join(f"{v['avg_deploy']*100:.0f}%" for v in out.values()) + ")")

    # full battery on the best (by Sharpe)
    bkw = configs[best]
    net, W, trades = build_portfolio(data, vix, **bkw)
    aret = pd.DataFrame({t: data[t]["Close"].pct_change() for t in data}).mean(axis=1).reindex(net.index).fillna(0)
    pos = (W.sum(axis=1) > 0).astype(float)
    com = net.index.intersection(pos.index).intersection(aret.index)
    perm = permutation_test(net.reindex(com).fillna(0), aret.reindex(com).fillna(0), pos.reindex(com).fillna(0), n_perm=2000)
    boot = bootstrap_ci(net, statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(net)
    mid = net.index[len(net)//2]
    is_s = compute_metrics(net[net.index <= mid])["sharpe"]; oos_s = compute_metrics(net[net.index > mid])["sharpe"]
    pps = net.mean()/net.std(ddof=1)
    dsr = deflated_sharpe_ratio(pps, len(net), len(configs), returns=net)
    r = out[best]
    print(f"\n  --- Beste Variante: {best} ---")
    print(f"    Permutation p={perm['p_value']:.3f} (Null {perm['null_mean']:.2f} vs real {perm['observed']:.2f}) | "
          f"Bootstrap-Sharpe-KI [{boot['ci_low']:.2f},{boot['ci_high']:.2f}] | t-p={tt['p_value']:.4f} | DSR={dsr['psr_deflated']:.3f}")
    print(f"    IS/OOS Sharpe: {is_s:.2f} / {oos_s:.2f}")

    # CTI sizing
    scale07 = 0.07 / abs(r["maxdd"])
    cagr7 = r["cagr"] * scale07; wd7 = r["worst_day"] * scale07
    print(f"\n  --- CTI-Eignung (beste Variante, 10% statisch + 5% daily) ---")
    print(f"    MaxDD {r['maxdd']*100:.1f}% | worst day {r['worst_day']*100:.1f}% | Win {r['win']*100:.0f}% | avg deploy {r['avg_deploy']*100:.0f}%")
    print(f"    Sizing auf 7% hist. DD: Risiko ×{scale07:.2f} -> CAGR ~{cagr7*100:+.1f}%/J, worst day ~{wd7*100:.1f}% "
          f"(Tageslimit 5% -> {'OK' if abs(wd7)<0.05 else 'BREACH'})")
    target_months = 0.10/cagr7*12 if cagr7 > 0 else float('inf')
    gate = abs(wd7) < 0.05 and cagr7 > 0.10
    print(f"    10%-Ziel in ~{target_months:.0f} Monaten  ->  CTI-GATE: {'BESTANDEN' if gate else 'NICHT bestanden'}")

    (RESULTS / "metrics.json").write_text(json.dumps({"configs": out, "best": best,
        "battery": {"perm_p": perm["p_value"], "dsr": dsr["psr_deflated"], "is": is_s, "oos": oos_s}}, indent=2, default=float))
    print(f"\n  gespeichert: {RESULTS/'metrics.json'}")


if __name__ == "__main__":
    main()
