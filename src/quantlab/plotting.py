"""Visualization helpers for backtest results.

Uses a non-interactive Matplotlib backend so plots render in scripts and
notebooks alike. Every function accepts a ``caption`` string that is printed
as an italic explanation under the chart, so a reader understands precisely
what the plot shows without external context. Each function returns the Figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # safe default for headless/script use
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .metrics import drawdown_series

sns.set_theme(style="whitegrid")


def _add_caption(fig: plt.Figure, caption: str | None) -> None:
    """Render an explanatory caption beneath the figure and make room for it."""
    if not caption:
        return
    fig.subplots_adjust(bottom=0.26)
    fig.text(
        0.5, 0.015, caption, ha="center", va="bottom", fontsize=8.5,
        style="italic", color="#444444", wrap=True,
    )


def plot_equity(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    title: str = "Kapitalkurve (Equity Curve)",
    caption: str | None = None,
    strategy_label: str = "Strategie",
    benchmark_label: str = "Buy & Hold",
) -> plt.Figure:
    """Strategy equity (log scale) vs an optional buy-and-hold benchmark."""
    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.plot(equity.index, equity.values, label=strategy_label, linewidth=1.7)
    if benchmark is not None:
        ax.plot(benchmark.index, benchmark.values, label=benchmark_label,
                linewidth=1.2, alpha=0.7)
    ax.set_yscale("log")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Wachstum von 1 € (log-Skala)")
    ax.legend()
    _add_caption(fig, caption)
    return fig


def plot_drawdown(
    returns: pd.Series,
    title: str = "Drawdown (Rückgang vom Höchststand)",
    caption: str | None = None,
) -> plt.Figure:
    """Underwater (drawdown) curve."""
    dd = drawdown_series(returns)
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.fill_between(dd.index, dd.values * 100, 0, color="crimson", alpha=0.4)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Drawdown (%)")
    _add_caption(fig, caption)
    return fig


def plot_monthly_heatmap(
    returns: pd.Series,
    title: str = "Monatsrenditen (%) pro Jahr",
    caption: str | None = None,
) -> plt.Figure:
    """Year x month heatmap of compounded monthly returns."""
    monthly = (1 + returns).resample("ME").prod() - 1
    table = monthly.to_frame("ret")
    table["year"] = table.index.year
    table["month"] = table.index.month
    pivot = table.pivot_table(index="year", columns="month", values="ret") * 100

    fig, ax = plt.subplots(figsize=(11, max(3.2, 0.45 * len(pivot))))
    sns.heatmap(pivot, annot=True, fmt=".1f", center=0, cmap="RdYlGn",
                cbar_kws={"label": "Rendite (%)"}, ax=ax)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Monat")
    ax.set_ylabel("Jahr")
    _add_caption(fig, caption)
    return fig


def plot_bucket_returns(
    bucket_df: pd.DataFrame,
    title: str = "Durchschnittsrendite je Kalender-Bucket",
    caption: str | None = None,
    significance_level: float = 0.05,
) -> plt.Figure:
    """Bar chart of mean return per bucket; significant buckets highlighted."""
    fig, ax = plt.subplots(figsize=(11, 5.0))
    means = bucket_df["mean_return"] * 100
    sig = bucket_df["p_value"] < significance_level
    colors = ["#2a9d8f" if s else "#b0b0b0" for s in sig]
    ax.bar(means.index.astype(str), means.values, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Mittlere Tagesrendite (%)")
    _add_caption(fig, caption)
    return fig


def plot_strategy_comparison(
    equities: dict[str, pd.Series],
    title: str = "Strategien im Vergleich — Kapitalkurven",
    caption: str | None = None,
) -> plt.Figure:
    """Overlay several strategies' equity curves, each rebased to 1.0.

    Args:
        equities: mapping of label -> equity Series (own date index each).
    """
    fig, ax = plt.subplots(figsize=(11.5, 6))
    for label, eq in equities.items():
        eq = eq.dropna()
        if eq.empty:
            continue
        rebased = eq / eq.iloc[0]
        ax.plot(rebased.index, rebased.values, label=label, linewidth=1.6)
    ax.set_yscale("log")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Wachstum von 1 € (log, alle bei 1 gestartet)")
    ax.legend(fontsize=9)
    _add_caption(fig, caption)
    return fig


def plot_risk_return(
    cards: list[dict],
    title: str = "Risiko-Rendite-Profil der Strategien",
    caption: str | None = None,
) -> plt.Figure:
    """Scatter of annualized volatility (x) vs CAGR (y); bubble per strategy.

    Each ``card`` needs keys: ``label``, ``cagr``, ``annual_volatility``,
    ``sharpe``. A higher/left point (more return, less risk) is better.
    """
    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    for c in cards:
        x = c["annual_volatility"] * 100
        y = c["cagr"] * 100
        sharpe = c.get("sharpe", 0.0)
        size = 120 + max(sharpe, 0) * 320
        color = "#2a9d8f" if c.get("is_strategy", True) else "#888888"
        ax.scatter(x, y, s=size, alpha=0.65, color=color, edgecolors="black", linewidths=0.6)
        ax.annotate(f"{c['label']}\n(Sharpe {sharpe:.2f})", (x, y),
                    textcoords="offset points", xytext=(8, 6), fontsize=8.5)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Annualisierte Volatilität (%) — Risiko")
    ax.set_ylabel("CAGR (%) — jährliche Rendite")
    _add_caption(fig, caption)
    return fig


def savefig(fig: plt.Figure, path: str | Path, dpi: int = 130) -> Path:
    """Save a figure to disk, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
