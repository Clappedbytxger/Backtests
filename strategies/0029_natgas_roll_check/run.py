"""Strategy 0029 — Natural-gas autumn window: roll-artifact check.

0028 found a strong, permutation-significant (p=0.001), macro-justified gas window
21 Sep -> 1 Nov. The open risk is *worse* than platinum's (0019): NG futures roll
**monthly** (each contract terminates ~3 business days before the 1st of the
delivery month), so the autumn window straddles **two** front-month rolls — the
Oct contract expires ~late September, the Nov contract ~late October. Going into
winter the curve is in **contango** (winter contracts pricier), so a naive stitch
in the yfinance continuous series would print a spurious *positive* return on each
roll day — exactly the days that would inflate a long autumn edge.

A first probe of the raw series is ambiguous: late-Sep days 27-29 and late-Oct days
28-30 carry large positive *mean* returns, BUT with huge std (7-10% vs ~3% normal)
and the actual price *levels* show no consistent every-year jump (2018/2022 roll
smoothly, only crisis years 2021 spike). That smells like genuine fat-tail moves,
not a mechanical contango gap. This script decides it with three angles:

  1. **Average seasonal path** — mean cumulative return by trading-day offset. A
     mechanical roll gap would show as a sharp step at the two roll offsets; genuine
     spot strength accrues smoothly.
  2. **Per-calendar-day mean AND hit rate** — a mechanical stitch is *consistent*
     (positive almost every year, low variance); a fat-tail is a few big years
     (high variance, hit rate near 50%). Hit rate on the suspected roll days is the
     discriminator 0019 lacked.
  3. **Roll-day exclusion test** — reconstruct each winter's trade return with the
     roll-zone days removed (Sep 24-30, Oct 24-31). If the edge mostly survives
     without the roll days, it is not a roll artifact; report how much expectancy and
     significance sit on the roll days.

Definitive contract-level confirmation needs single-contract data (Norgate/Barchart)
and the second contract's price to compute the true inter-contract gap; yfinance
gives neither, so this is a strong triangulation, not a contract-by-contract proof.

Run:
    .venv/Scripts/python.exe strategies/0029_natgas_roll_check/run.py
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
from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

TICKER = "NG=F"
NAME = "Erdgas (Natural-Gas-Future)"
START_MD = (9, 21)
END_MD = (11, 1)
COST_MODEL = IBKR_FUTURES

# Suspected monthly-roll zones inside the window (front-month termination ~3 bus.
# days before the 1st of the delivery month -> late in the prior calendar month).
ROLL_ZONES = [((9, 24), (9, 30)), ((10, 24), (10, 31))]


def in_roll_zone(m: int, d: int) -> bool:
    for (lo, hi) in ROLL_ZONES:
        if lo <= (m, d) <= hi:
            return True
    return False


def date_window_signal(index, start_md=START_MD, end_md=END_MD,
                       exclude_roll=False, name="natgas_autumn") -> pd.Series:
    """Long (1.0) over 21 Sep -> 1 Nov each year, else flat.

    If ``exclude_roll`` is set, the position is forced flat (0) on the suspected
    roll-zone calendar days, isolating the non-roll-day contribution. Decision-time
    signal; the engine applies the T+1 shift, so no look-ahead.
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for y in range(int(idx.year.min()), int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md)
        end = pd.Timestamp(y, *end_md)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    if exclude_roll:
        roll_mask = np.array([in_roll_zone(t.month, t.day) for t in idx])
        pos[roll_mask] = 0.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices: pd.DataFrame, signal: pd.Series) -> dict:
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    return {"metrics": compute_metrics(rets), "trades": trade_stats(res["trades"]),
            "exposure": float(res["position"].abs().mean()),
            "returns": rets, "res": res}


def main() -> None:
    print(f"Strategy 0029 — {NAME} roll-artifact check ({TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close — abort (CLAUDE.md 0005).")
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    first_year, last_year = int(prices.index[0].year), int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-01-01"

    # === 1. Per-winter aligned paths + per-day collection (base window) ========
    base_pos = date_window_signal(prices.index)
    held = base_pos.shift(1).fillna(0.0)            # actually-held (look-ahead safe)
    in_win = held > 0

    winter_paths, day_cal = {}, {}
    prev, cur_year = False, None
    for dt, flag in in_win.items():
        if flag:
            if not prev:
                cur_year = dt.year
                winter_paths[cur_year] = []
                day_cal[cur_year] = []
            winter_paths[cur_year].append(asset_ret.loc[dt])
            day_cal[cur_year].append((dt.month, dt.day))
        prev = flag

    max_len = max(len(v) for v in winter_paths.values())
    path_mat = np.full((len(winter_paths), max_len), np.nan)
    for i, (_, rets) in enumerate(sorted(winter_paths.items())):
        cum = np.cumprod(1.0 + np.array(rets)) - 1.0
        path_mat[i, :len(cum)] = cum
    mean_path = np.nanmean(path_mat, axis=0) * 100.0

    # Per-calendar-day mean return AND hit rate (consistency discriminator).
    cal_rows = []
    for yr, days in day_cal.items():
        for (m, d), r in zip(days, winter_paths[yr]):
            cal_rows.append({"md": f"{m:02d}-{d:02d}", "ret": r, "m": m, "d": d})
    cal_df = pd.DataFrame(cal_rows)
    cal_g = cal_df.groupby("md")["ret"]
    cal_mean = cal_g.mean() * 100.0
    cal_hit = cal_g.apply(lambda s: (s > 0).mean()) * 100.0
    cal_mean, cal_hit = cal_mean.sort_index(), cal_hit.sort_index()

    # Roll-day hit-rate / consistency summary.
    roll_rows = cal_df[cal_df.apply(lambda r: in_roll_zone(r["m"], r["d"]), axis=1)]
    nonroll_rows = cal_df[~cal_df.apply(lambda r: in_roll_zone(r["m"], r["d"]), axis=1)]
    roll_hit = float((roll_rows["ret"] > 0).mean())
    nonroll_hit = float((nonroll_rows["ret"] > 0).mean())
    roll_mean = float(roll_rows["ret"].mean()) * 100.0
    nonroll_mean = float(nonroll_rows["ret"].mean()) * 100.0
    roll_std = float(roll_rows["ret"].std(ddof=1)) * 100.0
    nonroll_std = float(nonroll_rows["ret"].std(ddof=1)) * 100.0

    # === 2. Decompose each winter's trade into roll vs non-roll legs ===========
    decomp = []
    for yr in sorted(winter_paths):
        rs = np.array(winter_paths[yr])
        is_roll = np.array([in_roll_zone(m, d) for (m, d) in day_cal[yr]])
        full = np.prod(1.0 + rs) - 1.0
        non = np.prod(1.0 + rs[~is_roll]) - 1.0 if (~is_roll).any() else 0.0
        roll = np.prod(1.0 + rs[is_roll]) - 1.0 if is_roll.any() else 0.0
        decomp.append({"year": yr, "full_pct": full * 100, "nonroll_pct": non * 100,
                       "roll_pct": roll * 100, "n_roll_days": int(is_roll.sum())})
    dec_df = pd.DataFrame(decomp)
    share_on_roll = (dec_df["roll_pct"].mean() /
                     dec_df["full_pct"].mean()) if dec_df["full_pct"].mean() else float("nan")

    # === 3. Full vs roll-excluded strategy (significance survives the roll?) ====
    def full_bundle(exclude_roll: bool) -> dict:
        sig = date_window_signal(prices.index, exclude_roll=exclude_roll)
        e = evaluate(prices, sig)
        rets = e["returns"]
        perm = permutation_test(rets, asset_ret, e["res"]["position"], n_perm=2000)
        boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
        tt = t_test_mean_return(rets)
        e_is = evaluate(prices.loc[:split_date],
                        date_window_signal(prices.loc[:split_date].index, exclude_roll=exclude_roll))
        e_oos = evaluate(prices.loc[split_date:],
                         date_window_signal(prices.loc[split_date:].index, exclude_roll=exclude_roll))
        return {"e": e, "perm": perm, "boot": boot, "tt": tt,
                "sharpe_is": e_is["metrics"]["sharpe"], "sharpe_oos": e_oos["metrics"]["sharpe"],
                "exp_is": e_is["trades"]["expectancy"] * 100, "exp_oos": e_oos["trades"]["expectancy"] * 100}

    base = full_bundle(exclude_roll=False)
    cleaned = full_bundle(exclude_roll=True)

    # === Plots =================================================================
    import matplotlib.pyplot as plt

    # Plot 1: average seasonal path with roll offsets annotated.
    fig, ax = plt.subplots(figsize=(11, 5.4))
    x = np.arange(max_len)
    ax.plot(x, mean_path, marker="o", linewidth=1.8, color="#264653")
    ax.axhline(0, color="black", linewidth=0.8)
    # Approximate roll offsets: ~4-6 trading days in (late Sep) and ~mid window (late Oct).
    ax.set_xlabel("Handelstag im Fenster (0 = Einstieg ~21. Sep.)")
    ax.set_ylabel("Ø kumulierte Rendite (%)")
    ax.set_title(f"0029 {NAME} — durchschnittlicher Saison-Pfad im Fenster",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Mittlere kumulierte Rendite über alle Herbste, ausgerichtet am Einstieg (~21. Sep.). "
        "Zwei Monatsrolls liegen im Fenster (~Ende Sep. bei Tag ~4-6, ~Ende Okt. nahe dem Ende). "
        "Ein scharfer Stufensprung genau an diesen Offsets wäre Roll-Gap-Verdacht; ein glatter, "
        "über das ganze Fenster verteilter Anstieg = echte Spot-Stärke."))
    plotting.savefig(fig, PLOTS / "avg_seasonal_path.png")

    # Plot 2: per-calendar-day mean (bars) + hit rate (line), roll zones shaded.
    fig, ax1 = plt.subplots(figsize=(13, 5.4))
    colors = ["#e9c46a" if in_roll_zone(int(md[:2]), int(md[3:])) else "#2a9d8f"
              for md in cal_mean.index]
    ax1.bar(range(len(cal_mean)), cal_mean.values, color=colors)
    ax1.axhline(0, color="black", linewidth=0.8)
    ax1.set_xticks(range(len(cal_mean)))
    ax1.set_xticklabels(cal_mean.index, rotation=90, fontsize=6.5)
    ax1.set_ylabel("Ø Tagesrendite (%)")
    ax2 = ax1.twinx()
    ax2.plot(range(len(cal_hit)), cal_hit.values, color="#e76f51", marker=".",
             linewidth=1.2, label="Trefferquote %")
    ax2.axhline(50, color="#e76f51", linestyle="--", linewidth=0.9)
    ax2.set_ylabel("Trefferquote (%)", color="#e76f51")
    ax2.set_ylim(0, 100)
    ax1.set_title(f"0029 {NAME} — Tagesrendite & Trefferquote je Kalendertag (Roll-Zonen gelb)",
                  fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Balken: Ø Tagesrendite je Datum. Gelb = vermutete Roll-Zonen (24.-30.9. / 24.-31.10.). "
        "Rote Linie: Trefferquote. Ein mechanischer Contango-Stitch wäre KONSISTENT (Trefferquote "
        "deutlich >50% auf den Roll-Tagen, kleine Streuung); eine Fat-Tail-Illusion zeigt hohe "
        "Mittel bei Trefferquote ~50% (wenige große Jahre)."))
    plotting.savefig(fig, PLOTS / "per_calendar_day.png")

    # Plot 3: per-winter decomposition — roll vs non-roll contribution.
    fig, ax = plt.subplots(figsize=(12, 5.4))
    w = 0.4
    yrs = dec_df["year"].values
    ax.bar(yrs - w/2, dec_df["nonroll_pct"], width=w, color="#2a9d8f", label="ohne Roll-Tage")
    ax.bar(yrs + w/2, dec_df["roll_pct"], width=w, color="#e9c46a", label="nur Roll-Tage")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Rendite-Beitrag pro Herbst (%)")
    ax.set_title(f"0029 {NAME} — Zerlegung je Herbst: Nicht-Roll- vs. Roll-Tage",
                 fontsize=12, fontweight="bold")
    ax.legend()
    plotting._add_caption(fig, (
        f"Pro Jahr: Beitrag der Nicht-Roll-Tage (grün) vs. der Roll-Zonen-Tage (gelb). "
        f"Sitzt der Edge überwiegend grün, ist er echte Spot-Stärke. Anteil des mittleren "
        f"Trade-Gewinns, der auf Roll-Tagen liegt: {share_on_roll:.0%}."))
    plotting.savefig(fig, PLOTS / "roll_decomposition.png")

    # === Persist ===============================================================
    summary = {
        "ticker": TICKER, "window": {"start": list(START_MD), "end": list(END_MD)},
        "roll_zones": [[list(a), list(b)] for (a, b) in ROLL_ZONES],
        "n_winters": len(winter_paths),
        "roll_vs_nonroll_days": {
            "roll_hit_rate": roll_hit, "nonroll_hit_rate": nonroll_hit,
            "roll_mean_pct": roll_mean, "nonroll_mean_pct": nonroll_mean,
            "roll_std_pct": roll_std, "nonroll_std_pct": nonroll_std,
        },
        "share_of_mean_trade_on_roll_days": share_on_roll,
        "decomposition_by_year": dec_df.to_dict(orient="records"),
        "base": {
            "expectancy_pct": base["e"]["trades"]["expectancy"] * 100,
            "win_rate": base["e"]["trades"]["win_rate"],
            "sharpe": base["e"]["metrics"]["sharpe"],
            "perm_p": base["perm"]["p_value"],
            "boot_ci": [base["boot"]["ci_low"], base["boot"]["ci_high"]],
            "t_p": base["tt"]["p_value"],
            "sharpe_is": base["sharpe_is"], "sharpe_oos": base["sharpe_oos"],
            "exp_is": base["exp_is"], "exp_oos": base["exp_oos"],
        },
        "roll_excluded": {
            "expectancy_pct": cleaned["e"]["trades"]["expectancy"] * 100,
            "win_rate": cleaned["e"]["trades"]["win_rate"],
            "sharpe": cleaned["e"]["metrics"]["sharpe"],
            "perm_p": cleaned["perm"]["p_value"],
            "boot_ci": [cleaned["boot"]["ci_low"], cleaned["boot"]["ci_high"]],
            "t_p": cleaned["tt"]["p_value"],
            "sharpe_is": cleaned["sharpe_is"], "sharpe_oos": cleaned["sharpe_oos"],
            "exp_is": cleaned["exp_is"], "exp_oos": cleaned["exp_oos"],
        },
        "sample": {"first_year": first_year, "last_year": last_year, "split_date": split_date},
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    dec_df.to_csv(RESULTS / "decomposition_by_year.csv", index=False)
    pd.DataFrame({"mean_pct": cal_mean, "hit_pct": cal_hit}).to_csv(RESULTS / "per_calendar_day.csv")

    # === Console ===============================================================
    print(f"\n  Winters: {len(winter_paths)}  ({first_year}-{last_year})")
    print(f"  Roll zones (suspected): 24.-30.09.  &  24.-31.10.\n")
    print("  Consistency (the roll-artifact discriminator):")
    print(f"    Roll-zone days:     mean {roll_mean:+.2f}%  hit {roll_hit:.0%}  std {roll_std:.2f}%")
    print(f"    Non-roll days:      mean {nonroll_mean:+.2f}%  hit {nonroll_hit:.0%}  std {nonroll_std:.2f}%")
    print(f"    -> A mechanical stitch would show roll-day hit >> 50% with small std.\n")
    print(f"  Share of mean trade PnL sitting on roll-zone days: {share_on_roll:.0%}\n")
    print("  Full vs roll-excluded strategy (net after costs):")
    print(f"    {'variant':>14} {'exp%':>7} {'win':>5} {'Sharpe':>7} {'perm_p':>7} "
          f"{'boot_lo':>8} {'expIS%':>7} {'expOOS%':>8}")
    for lbl, b in [("BASE (all days)", base), ("roll EXCLUDED", cleaned)]:
        print(f"    {lbl:>14} {b['e']['trades']['expectancy']*100:>7.2f} "
              f"{b['e']['trades']['win_rate']:>5.0%} {b['e']['metrics']['sharpe']:>7.2f} "
              f"{b['perm']['p_value']:>7.3f} {b['boot']['ci_low']:>8.2f} "
              f"{b['exp_is']:>7.2f} {b['exp_oos']:>8.2f}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
