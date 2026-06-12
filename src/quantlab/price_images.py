"""OHLC chart images for CNN models — (Re-)Imag(in)ing Price Trends (JKX 2023).

One sample = one coin/date: the trailing ``window`` daily bars drawn as a
binary image, 3 pixel columns per day (open tick | high-low bar | close
tick), a moving-average polyline across the price area and volume bars at
the bottom. Each image is rescaled to its own min-low/max-high — JKX argue
this implicit per-image normalization is a key source of the CNN's
predictive power (the model sees *shape*, not level).

Geometry (window=20, JKX layout): 60 px wide (20 days x 3), 64 px high =
48 price rows + 1 gap row + 15 volume rows. Pixels are {0,1} uint8.

Look-ahead contract: the image at date ``t`` uses bars ``t-window+1 .. t``
and the MA over the same trailing data — decision-time information only
(guarded by a unit test).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PRICE_ROWS = 48
GAP_ROWS = 1
VOL_ROWS = 15
HEIGHT = PRICE_ROWS + GAP_ROWS + VOL_ROWS  # 64


def draw_image(
    o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray,
    v: np.ndarray, ma: np.ndarray,
) -> np.ndarray:
    """One binary chart image from trailing arrays (length = window)."""
    w = len(c)
    img = np.zeros((HEIGHT, w * 3), dtype=np.uint8)

    lo = np.nanmin(l)
    hi = np.nanmax(np.concatenate([h, ma[~np.isnan(ma)]])) if np.isfinite(ma).any() else np.nanmax(h)
    hi = max(hi, np.nanmax(h))
    rng = hi - lo
    if not np.isfinite(rng) or rng <= 0:
        rng = max(abs(hi), 1e-12)

    def to_row(price: np.ndarray) -> np.ndarray:
        # high price -> small row index (top of image)
        scaled = (price - lo) / rng
        return (PRICE_ROWS - 1 - np.round(scaled * (PRICE_ROWS - 1))).astype(int)

    ro, rh, rl, rc = to_row(o), to_row(h), to_row(l), to_row(c)
    vmax = np.nanmax(v)
    rv = np.zeros(w, dtype=int) if not np.isfinite(vmax) or vmax <= 0 else (
        np.round((v / vmax) * (VOL_ROWS - 1)).astype(int)
    )

    for d in range(w):
        x = d * 3
        img[ro[d], x] = 1                       # open tick (left)
        img[rh[d]: rl[d] + 1, x + 1] = 1        # high-low bar (middle)
        img[rc[d], x + 2] = 1                   # close tick (right)
        if np.isfinite(ma[d]):
            r = int(np.clip(to_row(np.array([ma[d]]))[0], 0, PRICE_ROWS - 1))
            img[r, x: x + 3] = 1                # MA segment across the day
        if np.isfinite(v[d]):
            base = HEIGHT - 1
            img[base - rv[d]: base + 1, x + 1] = 1  # volume bar
    return img


def build_image_dataset(
    panels: dict,
    sample_index: pd.MultiIndex,
    window: int = 20,
) -> tuple[np.ndarray, pd.MultiIndex]:
    """Images for every (date, pair) row of ``sample_index`` with full data.

    Args:
        panels: :func:`crypto_xsection.get_price_panels` output (needs the
            ``open/high/low/close/dollar_volume`` panels).
        sample_index: MultiIndex (date, pair) — typically the design-matrix
            rows, so CNN and Track A share an identical sample set.
        window: trailing days per image (20 = JKX core spec).

    Returns:
        (X, idx): X uint8 array [n, 1, 64, window*3]; idx the subset of
        ``sample_index`` that had ``window`` complete bars.
    """
    o_p, h_p, l_p, c_p = panels["open"], panels["high"], panels["low"], panels["close"]
    v_p = panels["dollar_volume"]
    ma_p = c_p.rolling(window, min_periods=window).mean()
    dates_all = c_p.index

    pos = {d: i for i, d in enumerate(dates_all)}
    imgs, keep = [], []
    by_pair: dict[str, dict[str, np.ndarray]] = {}

    for date, pair in sample_index:
        i = pos.get(date)
        if i is None or i < window - 1 or pair not in c_p.columns:
            continue
        if pair not in by_pair:
            by_pair[pair] = {
                "o": o_p[pair].values, "h": h_p[pair].values,
                "l": l_p[pair].values, "c": c_p[pair].values,
                "v": v_p[pair].values, "ma": ma_p[pair].values,
            }
        a = by_pair[pair]
        sl = slice(i - window + 1, i + 1)
        c_win = a["c"][sl]
        if np.isnan(c_win).any() or np.isnan(a["h"][sl]).any() or np.isnan(a["l"][sl]).any():
            continue
        ma_win = a["ma"][sl]  # NaN during the pair's first window-1 days — drawn where finite
        imgs.append(draw_image(a["o"][sl], a["h"][sl], a["l"][sl], c_win, a["v"][sl], ma_win))
        keep.append((date, pair))

    X = np.stack(imgs)[:, None, :, :] if imgs else np.empty((0, 1, HEIGHT, window * 3), dtype=np.uint8)
    return X, pd.MultiIndex.from_tuples(keep, names=["date", "pair"])
