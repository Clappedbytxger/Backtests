"""Markdown reporting helpers.

The main feature is :func:`markdown_table`, which pads every cell so the columns
line up in the *raw* Markdown source. Plain Markdown tables render fine in a
browser but are hard to read as text (the pipes don't align); aligned source
makes the `.md` files readable directly in an editor or terminal.
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd


def markdown_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    align: Sequence[str] | None = None,
) -> str:
    """Render a Markdown table with columns aligned in the raw source.

    Args:
        headers: column titles.
        rows: list of rows; each row is a list of cell values (any type).
        align: per-column alignment, one of ``"l"``, ``"r"``, ``"c"``. Defaults
            to left for the first column and right for the rest (numbers read
            best right-aligned).

    Returns:
        The Markdown table as a string (no trailing newline).
    """
    headers = [str(h) for h in headers]
    n_cols = len(headers)
    str_rows = [[("" if c is None else str(c)) for c in row] for row in rows]

    if align is None:
        align = ["l"] + ["r"] * (n_cols - 1)
    align = list(align) + ["l"] * (n_cols - len(align))

    widths = [len(headers[i]) for i in range(n_cols)]
    for row in str_rows:
        for i in range(n_cols):
            widths[i] = max(widths[i], len(row[i]))

    def pad(value: str, i: int) -> str:
        if align[i] == "r":
            return value.rjust(widths[i])
        if align[i] == "c":
            return value.center(widths[i])
        return value.ljust(widths[i])

    def render_row(cells: Sequence[str]) -> str:
        return "| " + " | ".join(pad(cells[i], i) for i in range(n_cols)) + " |"

    def sep_cell(i: int) -> str:
        dashes = "-" * widths[i]
        if align[i] == "r":
            return dashes[:-1] + ":"
        if align[i] == "c":
            return ":" + dashes[1:-1] + ":" if widths[i] >= 2 else ":-:"
        return dashes
    separator = "| " + " | ".join(sep_cell(i) for i in range(n_cols)) + " |"

    lines = [render_row(headers), separator]
    lines += [render_row(row + [""] * (n_cols - len(row))) for row in str_rows]
    return "\n".join(lines)


def df_to_markdown(
    df: pd.DataFrame,
    float_fmt: str = "{:.2f}",
    index: bool = False,
    align: Sequence[str] | None = None,
) -> str:
    """Aligned Markdown table from a DataFrame, formatting floats nicely."""
    def fmt(v: object) -> str:
        if isinstance(v, float):
            return float_fmt.format(v)
        return str(v)

    headers = ([df.index.name or ""] if index else []) + [str(c) for c in df.columns]
    rows = []
    for idx, row in df.iterrows():
        cells = ([str(idx)] if index else []) + [fmt(v) for v in row.tolist()]
        rows.append(cells)
    return markdown_table(headers, rows, align=align)
