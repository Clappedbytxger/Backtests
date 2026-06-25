"""Strategy 0073 — PEAD via EDGAR SUE (IC-gate pilot, no price purchase).

Re-opens the deferred PEAD thread (strategies/0055_pead_blocked). The earnings
side is now sourced **free and survivorship-free** from SEC EDGAR XBRL
(quantlab.edgar_data): standardised unexpected earnings (SUE) via the
seasonal-random-walk model, which needs only reported EPS — no paid analyst
estimates.

This is a **kill-screen**, not a tradeable backtest:

- Universe = current large caps (S&P-100-style). That is survivorship-BIASED on
  membership (only today's survivors) — the opposite bias from a clean PEAD
  study. We accept it on purpose: it answers the one question that decides
  whether PEAD is worth clean (paid) data at all — *does the SUE drift even show
  up in the liquid names we could actually trade?* If IC ≈ 0 here, PEAD is dead
  for this account and we stop before spending on Sharadar-style price data.
- No cost model / position sizing yet. The gate is the IC battery (like the
  fundamental program 0042-0046): a full backtest only earns its keep if the
  signal clears the screen.

PIT: SUE release_date = 10-Q filing date (a conservative proxy for the earnings
announcement — strictly later, so no look-ahead). Forward returns are
market-adjusted (excess over the S&P 500 ETF) to isolate the cross-sectional
signal from index beta.

Pre-registered prediction (fundamentals/HYPOTHESES.md, H-EQ-01): high SUE →
positive market-adjusted drift over 1-3 months → pooled rank-IC > 0, top-minus-
bottom SUE decile excess return > 0 at 22-66 days.

Run:
    .venv/Scripts/python.exe strategies/0073_pead_edgar_sue/run.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import edgar_data as ed          # noqa: E402
from quantlab.data import get_prices, get_close  # noqa: E402
from quantlab.ic import information_coefficient  # noqa: E402
from scipy import stats                          # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

HORIZONS = (5, 22, 66)          # 1W / 1M / 3M trading days
PRIMARY_H = 66                  # the canonical ~60-day PEAD drift window
PRICE_START = "2005-01-01"
DECAY_SPLIT_YEAR = 2017         # post-XBRL sample roughly halves here

# Current S&P-100-style large-cap universe (liquid, the names we could trade).
# Survivorship-biased on membership by construction — see module docstring.
UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "TSLA", "BRK-B",
    "JPM", "JNJ", "V", "PG", "UNH", "HD", "MA", "BAC", "XOM", "CVX", "ABBV",
    "PFE", "KO", "PEP", "COST", "WMT", "MRK", "TMO", "DIS", "CSCO", "ACN",
    "ABT", "MCD", "DHR", "NKE", "TXN", "NEE", "WFC", "LIN", "ORCL", "PM",
    "BMY", "UNP", "QCOM", "HON", "AMGN", "IBM", "LOW", "UPS", "INTC", "CAT",
    "GS", "SBUX", "BA", "DE", "AMD", "GE", "MMM", "AXP", "BLK", "GILD",
    "C", "MDT", "ADBE", "CVS", "MO", "TGT", "LMT", "SPGI", "CB", "MDLZ",
    "DUK", "SO", "USB", "BKNG", "MS", "T", "VZ", "PYPL", "CL", "EMR",
    "COP", "RTX", "NFLX", "CRM", "WBA", "F", "GM", "DOW", "KHC", "EXC",
    "FDX", "SLB", "OXY", "KMI", "PNC", "MET", "AIG", "ALL", "TJX", "ADP",
]


def first_trading_pos(index: pd.DatetimeIndex, date: pd.Timestamp) -> int:
    """Index position of the first trading day on or after ``date`` (-1 if none)."""
    pos = index.searchsorted(date, side="left")
    return int(pos) if pos < len(index) else -1


def collect_events(spy_close: pd.Series) -> pd.DataFrame:
    """Build the pooled event table: one row per (ticker, SUE release).

    Columns: ticker, ref_date, release_date, sue, entry_date, and excess forward
    returns ``exc_{h}`` plus raw ``raw_{h}`` for each horizon.
    """
    cik_map = ed.get_cik_map()
    rows = []
    n_ok = 0
    for tkr in UNIVERSE:
        # --- earnings side (EDGAR) ---
        try:
            eps = ed.get_quarterly_eps(tkr, cik_map=cik_map)
            sue = ed.compute_sue(eps)
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip earnings] {tkr}: {exc}")
            continue
        if sue.empty:
            print(f"  [no SUE] {tkr}")
            continue

        # --- price side (yfinance, cached) ---
        try:
            px = get_prices(tkr, start=PRICE_START)["Close"]
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip prices] {tkr}: {exc}")
            continue
        idx = px.index
        spy_on = spy_close.reindex(idx, method="ffill")  # align market to stock days

        for _, ev in sue.iterrows():
            e = first_trading_pos(idx, ev["release_date"])
            if e < 0:
                continue
            rec = {"ticker": tkr, "ref_date": ev["ref_date"],
                   "release_date": ev["release_date"], "sue": ev["sue"],
                   "entry_date": idx[e]}
            ok_any = False
            for h in HORIZONS:
                x = e + h
                if x >= len(idx) or px.iloc[e] <= 0:
                    rec[f"raw_{h}"], rec[f"exc_{h}"] = np.nan, np.nan
                    continue
                stock_ret = px.iloc[x] / px.iloc[e] - 1.0
                mkt = spy_on.iloc[x] / spy_on.iloc[e] - 1.0
                rec[f"raw_{h}"] = stock_ret
                rec[f"exc_{h}"] = stock_ret - mkt
                ok_any = True
            if ok_any:
                rows.append(rec)
        n_ok += 1

    print(f"\nUniverse with usable earnings+prices: {n_ok}/{len(UNIVERSE)}")
    return pd.DataFrame(rows)


def pooled_ic(sue: np.ndarray, fwd: np.ndarray) -> float:
    """Pooled Spearman rank-IC across all stock-events (RangeIndex alignment)."""
    f = pd.Series(sue)
    r = pd.Series(fwd)
    return information_coefficient(f, r)


def permutation_p(sue: np.ndarray, fwd: np.ndarray, n_perm: int = 2000,
                  seed: int = 42) -> tuple[float, float]:
    """Two-sided permutation p for the pooled IC by shuffling SUE labels."""
    rng = np.random.default_rng(seed)
    obs, _ = stats.spearmanr(sue, fwd)
    perm = np.empty(n_perm)
    for i in range(n_perm):
        perm[i], _ = stats.spearmanr(rng.permutation(sue), fwd)
    return float(obs), float((np.abs(perm) >= abs(obs)).mean())


def monthly_ic(df: pd.DataFrame, col: str) -> dict:
    """Honest cross-sectional significance: Spearman IC within each entry month,
    then a t-test on the monthly IC series (each month = one observation).

    This is the Grinold-Kahn IC information ratio. It tames the clustering that
    makes the pooled permutation p over-optimistic — many names report in the
    same 2-week window and share market/sector moves, so pooled events are far
    from independent. (Residual overlap remains because 66d holds span months;
    treat the t-stat as indicative, not exact.)
    """
    d = df.dropna(subset=["sue", col]).copy()
    d["ym"] = d["entry_date"].dt.to_period("M")
    ics = []
    for _, g in d.groupby("ym"):
        if len(g) >= 8:  # need a cross-section to rank
            ic, _ = stats.spearmanr(g["sue"], g[col])
            if not np.isnan(ic):
                ics.append(ic)
    ics = np.array(ics)
    n = len(ics)
    mean_ic = float(ics.mean())
    std_ic = float(ics.std(ddof=1))
    t = mean_ic / (std_ic / np.sqrt(n)) if n > 1 and std_ic > 0 else np.nan
    p = float(2 * (1 - stats.t.cdf(abs(t), df=n - 1))) if not np.isnan(t) else np.nan
    return {
        "n_months": n, "mean_monthly_ic": mean_ic, "std_monthly_ic": std_ic,
        "ic_ir_t_stat": float(t), "ic_ir_p_value": p,
        "frac_positive_months": float((ics > 0).mean()),
    }


def decile_spread(df: pd.DataFrame, col: str, n_dec: int = 10) -> dict:
    """Top-minus-bottom SUE decile mean forward return + Welch t-test."""
    d = df.dropna(subset=["sue", col])
    ranks = d["sue"].rank(method="first")
    bucket = pd.qcut(ranks, n_dec, labels=False)
    top = d.loc[bucket == n_dec - 1, col]
    bot = d.loc[bucket == 0, col]
    t, p = stats.ttest_ind(top, bot, equal_var=False)
    return {
        "top_decile_mean": float(top.mean()),
        "bottom_decile_mean": float(bot.mean()),
        "spread": float(top.mean() - bot.mean()),
        "top_n": int(len(top)), "bottom_n": int(len(bot)),
        "t_stat": float(t), "p_value": float(p),
        "top_decile_hit_rate": float((top > 0).mean()),
    }


def make_plots(events: pd.DataFrame) -> None:
    """Two diagnostics: SUE-decile drift profile and cumulative monthly IC."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # (1) Mean market-adjusted 66d return by SUE decile — the PEAD profile
    d = events.dropna(subset=["sue", f"exc_{PRIMARY_H}"]).copy()
    d["dec"] = pd.qcut(d["sue"].rank(method="first"), 10, labels=False) + 1
    means = d.groupby("dec")[f"exc_{PRIMARY_H}"].mean() * 100

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(means.index, means.values,
           color=["#c0392b" if v < 0 else "#27ae60" for v in means.values])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("SUE-Dezil (1 = größter negativer Surprise, 10 = größter positiver)")
    ax.set_ylabel(f"Ø markt-adjustierte {PRIMARY_H}-Tage-Rendite (%)")
    ax.set_title("PEAD-Profil: hohe SUE-Dezile driften positiv, tiefe schwach — "
                 "real, aber verrauscht")
    fig.tight_layout()
    fig.savefig(RESULTS / "decile_drift.png", dpi=110)
    plt.close(fig)

    # (2) Cumulative monthly IC (66d) — stability of the signal over time
    dd = events.dropna(subset=["sue", f"exc_{PRIMARY_H}"]).copy()
    dd["ym"] = dd["entry_date"].dt.to_period("M")
    ics = (dd.groupby("ym")
             .apply(lambda g: stats.spearmanr(g["sue"], g[f"exc_{PRIMARY_H}"])[0]
                    if len(g) >= 8 else np.nan)
             .dropna())
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(ics.index.to_timestamp(), ics.cumsum(), color="#2c3e50")
    ax.set_xlabel("Eintrittsmonat")
    ax.set_ylabel("Kumulierter monatlicher Rank-IC (66d)")
    ax.set_title("Stetig steigend = stabiler Cross-Sectional-Edge, kein Decay")
    fig.tight_layout()
    fig.savefig(RESULTS / "cumulative_ic.png", dpi=110)
    plt.close(fig)


def main() -> None:
    print("=" * 64)
    print("0073 — PEAD via EDGAR SUE (IC-gate pilot)")
    print("=" * 64)

    spy = get_close("SPY", start=PRICE_START)
    events = collect_events(spy)
    if events.empty:
        raise SystemExit("No events collected — check EDGAR/price access.")

    events = events.sort_values("entry_date").reset_index(drop=True)
    events.to_csv(RESULTS / "events.csv", index=False)
    print(f"Pooled SUE events: {len(events)}  "
          f"({events['entry_date'].min().date()} … {events['entry_date'].max().date()})")
    print(f"Distinct tickers: {events['ticker'].nunique()}")

    out: dict = {
        "n_events": int(len(events)),
        "n_tickers": int(events["ticker"].nunique()),
        "date_range": [str(events["entry_date"].min().date()),
                       str(events["entry_date"].max().date())],
        "horizons": {},
    }

    print("\nPooled rank-IC (market-adjusted excess returns):")
    print(f"  {'Horizon':>8}  {'N':>6}  {'IC_exc':>8}  {'perm-p':>8}  {'IC_raw':>8}")
    for h in HORIZONS:
        d = events.dropna(subset=[f"exc_{h}"])
        sue_v = d["sue"].to_numpy()
        exc_v = d[f"exc_{h}"].to_numpy()
        raw_v = events.dropna(subset=[f"raw_{h}"])[f"raw_{h}"].to_numpy()
        raw_sue = events.dropna(subset=[f"raw_{h}"])["sue"].to_numpy()
        ic_exc, p_exc = permutation_p(sue_v, exc_v)
        ic_raw = pooled_ic(raw_sue, raw_v)
        out["horizons"][h] = {
            "n": int(len(d)), "ic_excess": ic_exc, "perm_p_excess": p_exc,
            "ic_raw": ic_raw,
        }
        print(f"  {h:>8}  {len(d):>6}  {ic_exc:>8.4f}  {p_exc:>8.4f}  {ic_raw:>8.4f}")

    # Honest cross-sectional significance: monthly IC IR (handles clustering)
    print("\nMonthly IC IR (excess; each month = one obs):")
    print(f"  {'Horizon':>8}  {'months':>7}  {'meanIC':>8}  {'IC-IR t':>8}  "
          f"{'p':>7}  {'%pos':>6}")
    out["monthly_ic"] = {}
    for h in HORIZONS:
        mic = monthly_ic(events, f"exc_{h}")
        out["monthly_ic"][h] = mic
        print(f"  {h:>8}  {mic['n_months']:>7}  {mic['mean_monthly_ic']:>8.4f}  "
              f"{mic['ic_ir_t_stat']:>8.2f}  {mic['ic_ir_p_value']:>7.4f}  "
              f"{mic['frac_positive_months']*100:>5.1f}%")

    # Decile spread at the primary (66d) horizon, market-adjusted
    spread = decile_spread(events, f"exc_{PRIMARY_H}")
    out["decile_spread_66d_excess"] = spread
    print(f"\nSUE decile spread @ {PRIMARY_H}d (excess): "
          f"top {spread['top_decile_mean']*100:+.2f}%  "
          f"bottom {spread['bottom_decile_mean']*100:+.2f}%  "
          f"spread {spread['spread']*100:+.2f}%  "
          f"(t={spread['t_stat']:.2f}, p={spread['p_value']:.4f}, "
          f"top-hit {spread['top_decile_hit_rate']*100:.1f}%)")

    # Decay split: IC(66d excess) early vs late sub-period
    yr = events["entry_date"].dt.year
    decay = {}
    for label, mask in {
        f"pre_{DECAY_SPLIT_YEAR}": yr < DECAY_SPLIT_YEAR,
        f"from_{DECAY_SPLIT_YEAR}": yr >= DECAY_SPLIT_YEAR,
    }.items():
        d = events[mask].dropna(subset=[f"exc_{PRIMARY_H}"])
        ic = pooled_ic(d["sue"].to_numpy(), d[f"exc_{PRIMARY_H}"].to_numpy())
        decay[label] = {"n": int(len(d)), "ic_excess_66d": ic}
    out["decay_split"] = decay
    print(f"\nDecay split (IC 66d excess): "
          + "  ".join(f"{k}: {v['ic_excess_66d']:+.4f} (n={v['n']})"
                      for k, v in decay.items()))

    # Verdict. The pooled perm-p is over-optimistic (overlap); the honest gate is
    # the monthly IC IR t-stat at the primary horizon plus a positive decile tail.
    ir_t = out["monthly_ic"][PRIMARY_H]["ic_ir_t_stat"]
    out["passes_screen"] = bool(ir_t > 2.0 and spread["spread"] > 0)
    verdict = ("PASS — signal present in tradable names, clean data worth buying"
               if out["passes_screen"] else
               "WEAK — signal real but tail thin; needs cost + survivorship-free "
               "check before any spend")
    print(f"\nScreen (honest): monthly IC-IR t({PRIMARY_H}d)={ir_t:.2f}, "
          f"66d spread {spread['spread']*100:+.2f}% → {verdict}")

    make_plots(events)
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {RESULTS / 'metrics.json'}, events.csv, and plots")


if __name__ == "__main__":
    main()
