"""Strategy 0068 — Multi-future trend following (fast + slow sleeve).

Idee B from NEXT-STRATEGIES-AND-LIVE-SYSTEM.md: time-series momentum
(Moskowitz/Ooi/Pedersen 2012, Hurst et al. 2017) as the second,
structurally-uncorrelated edge family. The deliverable is DIVERSIFICATION,
not standalone alpha — the registered question is whether a trend sleeve
improves the existing book (0036 overlay), not whether it beats it.

Pre-registered spec (no parameter fitting; trial count = 5 signal variants):
- Universe: 20 liquid GLBX futures (equity ES/NQ, bonds ZN/ZB/ZF, FX
  6E/6J/6B/6A, energy CL/NG/HO/RB, metals GC/SI/HG, ags ZC/ZW/ZS, livestock LE).
- Signals on roll-adjusted closes (instrument_id back-adjust, lesson 0048):
  fast = sign(21d return), slow = sign(252d return), slow2 = sign(504d),
  combo = 0.5*fast + 0.5*slow, combo2 = 0.5*fast + 0.5*slow2.
  The MIDDLE horizons (60-125d) are deliberately ABSENT (2025 literature:
  they whipsaw post-2022; pre-registered exclusion, not a fitted choice).
- Sizing: per-market inverse-vol risk parity — position = signal *
  (PER_MARKET_VOL / vol60_ann), vol estimated on info up to t-1.
- Weekly rebalance (last trading day of week), positions effective T+1,
  costs IBKR_FUTURES 2.5 bps/side on turnover.
- Battery: circular-shift permutation (per-market random signal offset —
  destroys timing, keeps position/turnover structure and costs), bootstrap
  Sharpe CI, DSR with n_trials=5, subperiods (2010-2018 / 2019-2026 and the
  hard 2010-2022 stretch), crisis convexity (2020Q1, 2022), and the actual
  test: correlation + portfolio value-add vs the 0036 overlay book.

Run:
    .venv/Scripts/python.exe strategies/0068_trend_following_multifuture/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.futures_curve import get_curve_contract, roll_adjusted_close  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

UNIVERSE = ["ES", "NQ", "ZN", "ZB", "ZF", "6E", "6J", "6B", "6A",
            "CL", "NG", "HO", "RB", "GC", "SI", "HG", "ZC", "ZW", "ZS", "LE"]
N_TRIALS = 5
COST_SIDE = 2.5 / 10_000.0
PER_MARKET_VOL = 0.10 / np.sqrt(len(UNIVERSE))  # ~10% portfolio vol if uncorrelated
VOL_LB = 60
ANN = np.sqrt(252)


def load_returns() -> pd.DataFrame:
    cols = {}
    for root in UNIVERSE:
        df = get_curve_contract(f"{root}.c.0")
        df = df[df.index.dayofweek < 5]
        adj = roll_adjusted_close(df["Close"], df["instrument_id"])
        cols[root] = adj.pct_change()
    ret = pd.DataFrame(cols)
    # require most of the panel observed (0057 thin-row lesson)
    ret = ret[ret.notna().mean(axis=1) >= 0.5]
    return ret


def build_positions(ret: pd.DataFrame, fast_w: float, slow_w: float,
                    slow_lb: int) -> pd.DataFrame:
    px = (1 + ret.fillna(0.0)).cumprod()
    sig = fast_w * np.sign(px / px.shift(21) - 1) + \
        slow_w * np.sign(px / px.shift(slow_lb) - 1)
    vol = ret.rolling(VOL_LB).std() * ANN
    raw = sig * (PER_MARKET_VOL / vol).clip(upper=2.0)  # cap leverage per market
    raw[vol.isna()] = 0.0
    # weekly rebalance: refresh on the last trading day of each week, hold in
    # between, applied T+1 (decision-time convention)
    week = pd.Series(raw.index.to_period("W-FRI"), index=raw.index)
    is_week_end = week.ne(week.shift(-1))
    mask = pd.DataFrame(
        np.repeat(is_week_end.values[:, None], raw.shape[1], axis=1),
        index=raw.index, columns=raw.columns)
    pos = raw.where(mask).ffill().shift(1).fillna(0.0)
    return pos


def portfolio(ret: pd.DataFrame, pos: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    gross = (pos * ret).sum(axis=1)
    turnover = pos.diff().abs().sum(axis=1).fillna(0.0)
    net = gross - turnover * COST_SIDE
    return net, turnover


def circular_shift_permutation(ret: pd.DataFrame, variant: dict,
                               n_perm: int = 500, seed: int = 42) -> float:
    """Null: per-market random circular shift of the SIGNAL (timing destroyed,
    position structure + costs preserved)."""
    obs_pos = build_positions(ret, **variant)
    obs_net, _ = portfolio(ret, obs_pos)
    obs_sharpe = obs_net.mean() / obs_net.std() * ANN
    rng = np.random.default_rng(seed)
    n = len(ret)
    null = np.zeros(n_perm)
    for i in range(n_perm):
        shifted = {}
        for c in obs_pos.columns:
            k = int(rng.integers(252, n - 252))
            shifted[c] = np.roll(obs_pos[c].values, k)
        p = pd.DataFrame(shifted, index=ret.index)
        net, _ = portfolio(ret, p)
        null[i] = net.mean() / net.std() * ANN
    return float((np.sum(null >= obs_sharpe) + 1) / (n_perm + 1))


def seg_sharpe(r: pd.Series, a: str, b: str) -> float:
    seg = r.loc[a:b]
    return float(seg.mean() / seg.std() * ANN) if seg.std() > 0 else np.nan


def main() -> None:
    print("0068 — Multi-Future-Trend (fast+slow Sleeve), 20 Maerkte, 2010-2026\n")
    ret = load_returns()
    print(f"Panel: {ret.shape[0]} Tage x {ret.shape[1]} Maerkte, "
          f"{ret.index[0].date()}..{ret.index[-1].date()}\n")

    variants = {
        "fast21":       {"fast_w": 1.0, "slow_w": 0.0, "slow_lb": 252},
        "slow252":      {"fast_w": 0.0, "slow_w": 1.0, "slow_lb": 252},
        "slow504":      {"fast_w": 0.0, "slow_w": 1.0, "slow_lb": 504},
        "combo21_252":  {"fast_w": 0.5, "slow_w": 0.5, "slow_lb": 252},
        "combo21_504":  {"fast_w": 0.5, "slow_w": 0.5, "slow_lb": 504},
    }
    out = {"universe": UNIVERSE, "n_trials": N_TRIALS, "variants": {}}
    nets, trial_sharpes = {}, []

    print(f"{'Variante':14}{'Sharpe':>8}{'CAGR':>8}{'MaxDD':>8}{'Vol':>7}{'TO/J':>7}")
    for name, v in variants.items():
        pos = build_positions(ret, **v)
        net, to = portfolio(ret, pos)
        m = compute_metrics(net)
        nets[name] = net
        trial_sharpes.append(net.mean() / net.std())
        out["variants"][name] = {
            "sharpe": m["sharpe"], "cagr": m["cagr"], "maxdd": m["max_drawdown"],
            "vol": m["annual_volatility"],
            "turnover_year": float(to.mean() * 252),
        }
        print(f"{name:14}{m['sharpe']:8.2f}{m['cagr']:8.1%}{m['max_drawdown']:8.1%}"
              f"{m['annual_volatility']:7.1%}{to.mean()*252:7.1f}")

    # Headline = the doc's pre-registered structure: fast + slow combo (252).
    head_name = "combo21_252"
    head = nets[head_name]
    sp = head.mean() / head.std()
    p_perm = circular_shift_permutation(ret, variants[head_name])
    boot = bootstrap_ci(head, statistic="sharpe", n_boot=2000)
    dsr = deflated_sharpe_ratio(observed_sharpe=sp, n_obs=len(head),
                                n_trials=N_TRIALS, returns=head,
                                trial_sharpes=trial_sharpes)
    out["headline"] = {
        "variant": head_name, "perm_p": p_perm,
        "boot_sharpe_ci": [boot["ci_low"], boot["ci_high"]],
        "dsr": dsr["psr_deflated"],
        "subperiods": {
            "2010-2018": seg_sharpe(head, "2010", "2018"),
            "2019-2026": seg_sharpe(head, "2019", "2026"),
            "2010-2022 (harte Dekade)": seg_sharpe(head, "2010", "2022"),
            "2020Q1 (Covid)": seg_sharpe(head, "2020-01", "2020-03"),
            "2022 (Bond-Crash)": seg_sharpe(head, "2022-01", "2022-12"),
        },
        "yearly": {str(y): float(g.sum()) for y, g in head.groupby(head.index.year)},
    }
    print(f"\nHeadline {head_name}: Permutation p={p_perm:.3f}, "
          f"Bootstrap-Sharpe-KI [{boot['ci_low']:+.2f}, {boot['ci_high']:+.2f}], "
          f"DSR {dsr['psr_deflated']:.3f}")
    for k, v in out["headline"]["subperiods"].items():
        print(f"  {k:28s} Sharpe {v:+.2f}")

    # ---- the REGISTERED question: does it diversify the existing book? ----
    overlay_eq = pd.read_csv(ROOT / "strategies" / "0036_quint_season_overlay" /
                             "results" / "equity.csv", index_col=0, parse_dates=True)
    book = overlay_eq.iloc[:, 0].pct_change().rename("book")
    both = pd.concat([book, head.rename("trend")], axis=1).dropna()
    corr = both["book"].corr(both["trend"])
    crisis = both[both["book"] < both["book"].quantile(0.05)]
    corr_crisis = crisis["book"].corr(crisis["trend"])
    trend_in_crisis = float(crisis["trend"].mean() * 1e4)

    mixes = {}
    m_book = compute_metrics(both["book"])
    for w in [0.0, 0.2, 0.3, 0.5]:
        mix = (1 - w) * both["book"] + w * both["trend"]
        m = compute_metrics(mix)
        mixes[f"{int(w*100)}% Trend"] = {"sharpe": m["sharpe"], "cagr": m["cagr"],
                                         "maxdd": m["max_drawdown"],
                                         "vol": m["annual_volatility"]}
    out["diversification"] = {
        "corr_full": float(corr), "corr_book_tail5pct": float(corr_crisis),
        "trend_mean_bps_in_book_tail": trend_in_crisis, "mixes": mixes,
    }
    print(f"\nKorrelation Trend vs 0036-Buch: {corr:+.3f} "
          f"(in den 5% schlechtesten Buch-Tagen: {corr_crisis:+.3f}, "
          f"Trend dort im Mittel {trend_in_crisis:+.1f} bps/Tag)")
    print(f"{'Mix':12}{'Sharpe':>8}{'CAGR':>8}{'MaxDD':>8}{'Vol':>7}")
    for k, m in mixes.items():
        print(f"{k:12}{m['sharpe']:8.2f}{m['cagr']:8.1%}{m['maxdd']:8.1%}{m['vol']:7.1%}")

    # ---- plots ----
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for name, net in nets.items():
        eq = (1 + net).cumprod()
        ax[0].plot(eq.index, eq.values, lw=1.0,
                   label=name + (" (headline)" if name == head_name else ""))
    ax[0].set_yscale("log"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    ax[0].set_title("0068 Trend-Varianten, netto (log)")
    eq_b = (1 + both["book"]).cumprod()
    eq_t = (1 + both["trend"]).cumprod()
    eq_m = (1 + 0.7 * both["book"] + 0.3 * both["trend"]).cumprod()
    ax[1].plot(eq_b.index, eq_b.values, label="0036-Buch", lw=1.0)
    ax[1].plot(eq_t.index, eq_t.values, label="Trend (combo)", lw=1.0)
    ax[1].plot(eq_m.index, eq_m.values, label="70/30-Mix", lw=1.2)
    ax[1].set_yscale("log"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    ax[1].set_title(f"Diversifikation: corr={corr:+.2f}")
    fig.tight_layout(); fig.savefig(RESULTS / "trend_overview.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nresults -> {RESULTS}")


if __name__ == "__main__":
    main()
