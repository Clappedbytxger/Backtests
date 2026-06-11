"""Strategy 0053 — Monetary Momentum (Neuhierl & Weber).

Paper-edge #4. Claim: equity returns drift in the direction of the monetary-policy
SURPRISE for ~15 trading days after the FOMC decision — a dovish surprise is
followed by a positive drift, a hawkish surprise by a negative one. Cause: slow
diffusion of macro information; investors under-react to the Fed surprise.

Surprise proxy: the change in the 2-year Treasury yield (FRED DGS2) ON the
announcement day (yield[A] - yield[A-1]). Yields fall on a dovish surprise. The
canonical Kuttner (2001) measure uses fed-funds futures intraday; the 2y-yield
daily change is the standard free daily proxy for the rate-path surprise.

Signal = -sign(yield change): go LONG after a dovish surprise (yield down), SHORT
after a hawkish one (yield up); hold h days from the announcement close. Decision-
time clean: the surprise is observed at the announcement-day close, the trade is
entered at that close and held forward.

Data: SPY daily, DGS2 (cached CSV from FRED). 210 FOMC events 2000-2026.

Run:
    .venv/Scripts/python.exe strategies/0053_monetary_momentum/run.py
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

from quantlab.data import get_prices  # noqa: E402
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, t_test_mean_return  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)

# Same verified FOMC announcement dates as 0052 (2000-2026, scheduled meetings).
FOMC = [
    "2000-02-02", "2000-03-21", "2000-05-16", "2000-06-28", "2000-08-22", "2000-10-03", "2000-11-15", "2000-12-19",
    "2001-01-31", "2001-03-20", "2001-05-15", "2001-06-27", "2001-08-21", "2001-10-02", "2001-11-06", "2001-12-11",
    "2002-01-30", "2002-03-19", "2002-05-07", "2002-06-26", "2002-08-13", "2002-09-24", "2002-11-06", "2002-12-10",
    "2003-01-29", "2003-03-18", "2003-05-06", "2003-06-25", "2003-08-12", "2003-09-16", "2003-10-28", "2003-12-09",
    "2004-01-28", "2004-03-16", "2004-05-04", "2004-06-30", "2004-08-10", "2004-09-21", "2004-11-10", "2004-12-14",
    "2005-02-02", "2005-03-22", "2005-05-03", "2005-06-30", "2005-08-09", "2005-09-20", "2005-11-01", "2005-12-13",
    "2006-01-31", "2006-03-28", "2006-05-10", "2006-06-29", "2006-08-08", "2006-09-20", "2006-10-25", "2006-12-12",
    "2007-01-31", "2007-03-21", "2007-05-09", "2007-06-28", "2007-08-07", "2007-09-18", "2007-10-31", "2007-12-11",
    "2008-01-30", "2008-03-18", "2008-04-30", "2008-06-25", "2008-08-05", "2008-09-16", "2008-10-29", "2008-12-16",
    "2009-01-28", "2009-03-18", "2009-04-29", "2009-06-24", "2009-08-12", "2009-09-23", "2009-11-04", "2009-12-16",
    "2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23", "2010-08-10", "2010-09-21", "2010-11-03", "2010-12-14",
    "2011-01-26", "2011-03-15", "2011-04-27", "2011-06-22", "2011-08-09", "2011-09-21", "2011-11-02", "2011-12-13",
    "2012-01-25", "2012-03-13", "2012-04-25", "2012-06-20", "2012-08-01", "2012-09-13", "2012-10-24", "2012-12-12",
    "2013-01-30", "2013-03-20", "2013-05-01", "2013-06-19", "2013-07-31", "2013-09-18", "2013-10-30", "2013-12-18",
    "2014-01-29", "2014-03-19", "2014-04-30", "2014-06-18", "2014-07-30", "2014-09-17", "2014-10-29", "2014-12-17",
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17", "2015-07-29", "2015-09-17", "2015-10-28", "2015-12-16",
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29",
]


def main() -> None:
    out: dict = {}
    spy = get_prices("SPY", start="1999-06-01")
    close = spy["Close"]
    idx = close.index
    dgs2 = pd.read_csv(HERE / "dgs2.csv", parse_dates=["date"]).set_index("date")["DGS2"]
    dgs2 = dgs2.reindex(idx).ffill()  # align to trading days

    fomc = pd.to_datetime(FOMC)
    horizons = [5, 10, 15, 20]
    rec = []
    for d in fomc:
        a = idx.searchsorted(d)
        if a < 1 or a >= len(idx):
            continue
        surprise = float(dgs2.iloc[a] - dgs2.iloc[a - 1])  # 2y-yield change on announcement day (pp)
        row = {"ann": idx[a], "surprise_bp": surprise * 100}
        for h in horizons:
            if a + h < len(idx):
                row[f"fwd{h}"] = float(close.iloc[a + h] / close.iloc[a] - 1)
        rec.append(row)
    ev = pd.DataFrame(rec).set_index("ann").dropna()
    print(f"Events with surprise + forward returns: {len(ev)}")
    print(f"surprise (2y yield chg) bp: mean {ev['surprise_bp'].mean():+.2f}, "
          f"std {ev['surprise_bp'].std():.1f}, dovish(<0) {int((ev['surprise_bp']<0).sum())} / "
          f"hawkish(>0) {int((ev['surprise_bp']>0).sum())}")

    # signal = -sign(surprise): long after dovish (yield down), short after hawkish
    sig = -np.sign(ev["surprise_bp"])
    print(f"\n{'horizon':>8}{'beta(fwd~-surp)':>17}{'corr':>8}{'signMean%':>11}{'t':>7}{'p':>9}{'win%':>7}")
    out["horizons"] = {}
    for h in horizons:
        fwd = ev[f"fwd{h}"]
        strat = sig * fwd                         # signed forward return
        # regression of forward return on -surprise (monetary-momentum slope)
        x = -ev["surprise_bp"]
        beta = float(np.polyfit(x, fwd, 1)[0])
        corr = float(x.corr(fwd))
        tt = t_test_mean_return(strat)
        out["horizons"][h] = {"beta": beta, "corr": corr, "sign_mean_pct": float(strat.mean() * 100),
                              "t": tt["t_stat"], "p": tt["p_value"], "win": float((strat > 0).mean())}
        print(f"{h:8d}{beta:17.4f}{corr:8.3f}{strat.mean()*100:11.3f}{tt['t_stat']:7.2f}"
              f"{tt['p_value']:9.4f}{(strat>0).mean()*100:7.1f}")

    # headline horizon = 15d (paper)
    h = 15
    fwd = ev[f"fwd{h}"]
    strat = (sig * fwd).dropna()
    # dovish vs hawkish forward returns
    dov = ev.loc[ev["surprise_bp"] < 0, f"fwd{h}"]
    haw = ev.loc[ev["surprise_bp"] > 0, f"fwd{h}"]
    print(f"\nHeadline h=15: dovish fwd {dov.mean()*100:+.2f}% (n={len(dov)}) vs "
          f"hawkish fwd {haw.mean()*100:+.2f}% (n={len(haw)}); spread {(dov.mean()-haw.mean())*100:+.2f}pp")

    # permutation: shuffle the surprise sign vs forward returns
    rng = np.random.default_rng(42)
    obs = float(strat.mean())
    signs = sig.values
    fwdv = fwd.values
    null = np.array([(rng.permutation(signs) * fwdv).mean() for _ in range(5000)])
    p_perm = float((np.sum(null >= obs) + 1) / 5001)
    boot = bootstrap_ci(strat, statistic="mean", n_boot=5000)
    pp_sharpe = float(strat.mean() / strat.std()) if strat.std() else float("nan")
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=len(strat), n_trials=4, returns=strat)
    print(f"permutation (shuffle surprise sign), h=15: p = {p_perm:.4f}")
    print(f"bootstrap signed-return mean 95% CI: [{boot['ci_low']*100:+.3f}%, {boot['ci_high']*100:+.3f}%]")
    print(f"deflated Sharpe (n_trials=4 horizons): PSR = {dsr['psr_deflated']:.3f}")
    out["headline_h15"] = {"dovish_fwd_pct": float(dov.mean() * 100), "hawkish_fwd_pct": float(haw.mean() * 100),
                           "spread_pp": float((dov.mean() - haw.mean()) * 100), "permutation_p": p_perm,
                           "bootstrap_mean": boot, "deflated_sharpe": dsr,
                           "sign_mean_pct": float(obs * 100)}

    # plot
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].scatter(-ev["surprise_bp"], ev["fwd15"] * 100, s=14, alpha=0.5, color="slategrey")
    xs = np.linspace(-ev["surprise_bp"].min(), -ev["surprise_bp"].max(), 10)
    b1, b0 = np.polyfit(-ev["surprise_bp"], ev["fwd15"], 1)
    ax[0].plot(xs, (b0 + b1 * xs) * 100, color="crimson", lw=2, label=f"beta={b1:.4f}")
    ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", lw=0.6)
    ax[0].set_xlabel("-surprise (dovish = positive, bp)"); ax[0].set_ylabel("SPY fwd 15d return (%)")
    ax[0].set_title("Monetary momentum: 15d drift vs policy surprise"); ax[0].legend(fontsize=9); ax[0].grid(alpha=0.3)
    ax[1].bar(["dovish\n(yield down)", "hawkish\n(yield up)"], [dov.mean() * 100, haw.mean() * 100],
              color=["seagreen", "indianred"], edgecolor="k")
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_ylabel("SPY fwd 15d return (%)")
    ax[1].set_title("Forward 15d return after dovish vs hawkish surprise"); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "monetary_momentum.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSUMMARY: h=15 signed mean {obs*100:+.3f}%, permutation p={p_perm:.3f}, "
          f"dovish-hawkish spread {(dov.mean()-haw.mean())*100:+.2f}pp.")


if __name__ == "__main__":
    main()
