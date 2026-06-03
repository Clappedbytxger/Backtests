"""Visualization helpers for backtest results.

Uses a non-interactive Matplotlib backend so plots render in scripts and
notebooks alike. Every function returns the Figure for further tweaking or
saving via :func:`savefig`.
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


def plot_equity(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    title: str = "Equity Curve",
) -> plt.Figure:
    """Plot strategy equity (log scale) vs an optional buy-and-hold benchmark."""
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(equity.index, equity.values, label="Strategy", linewidth=1.6)
    if benchmark is not None:
        ax.plot(benchmark.index, benchmark.values, label="Buy & Hold",
                linewidth=1.2, alpha=0.7)
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_ylabel("Growth of 1 (log)")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_drawdown(returns: pd.Series, title: str = "Drawdown") -> plt.Figure:
    """Plot the underwater (drawdown) curve."""
    dd = drawdown_series(returns)
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.fill_between(dd.index, dd.values * 100, 0, color="crimson", alpha=0.4)
    ax.set_title(title)
    ax.set_ylabel("Drawdown (%)")
    fig.tight_layout()
    return fig


def plot_monthly_heatmap(returns: pd.Series, title: str = "Monthly Returns (%)") -> plt.Figure:
    """Year x month heatmap of compounded monthly returns."""
    monthly = (1 + returns).resample("ME").prod() - 1
    table = monthly.to_frame("ret")
    table["year"] = table.index.year
    table["month"] = table.index.month
    pivot = table.pivot_table(index="year", columns="month", values="ret") * 100

    fig, ax = plt.subplots(figsize=(11, max(3, 0.4 * len(pivot))))
    sns.heatmap(pivot, annot=True, fmt=".1f", center=0, cmap="RdYlGn",
                cbar_kws={"label": "%"}, ax=ax)
    ax.set_title(title)
    fig.tight_layout()
    return fig


def plot_bucket_returns(
    bucket_df: pd.DataFrame,
    title: str = "Average Return by Calendar Bucket",
    significance_level: float = 0.05,
) -> plt.Figure:
    """Bar chart of mean return per bucket; significant buckets highlighted.

    Expects the output of :func:`quantlab.seasonal.bucket_return_analysis`
    (index = bucket, columns include ``mean_return`` and ``p_value``).
    """
    fig, ax = plt.subplots(figsize=(11, 4.5))
    means = bucket_df["mean_return"] * 100
    sig = bucket_df["p_value"] < significance_level
    colors = ["#2a9d8f" if s else "#b0b0b0" for s in sig]
    ax.bar(means.index.astype(str), means.values, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(f"{title}  (green = p < {significance_level})")
    ax.set_ylabel("Mean return (%)")
    fig.tight_layout()
    return fig


def savefig(fig: plt.Figure, path: str | Path, dpi: int = 130) -> Path:
    """Save a figure to disk, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
