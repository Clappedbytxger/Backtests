"""Guards for the JKX chart-image builder (geometry, scaling, no look-ahead)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.price_images import HEIGHT, PRICE_ROWS, build_image_dataset, draw_image

RNG = np.random.default_rng(7)


def _synthetic_panels(n_days: int = 120, pairs: tuple[str, ...] = ("AAA", "BBB")) -> dict:
    idx = pd.date_range("2021-01-01", periods=n_days, freq="D")
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(RNG.normal(0, 0.03, size=(n_days, len(pairs))), axis=0)),
        index=idx, columns=list(pairs),
    )
    spread = close * RNG.uniform(0.0, 0.02, size=close.shape)
    return {
        "close": close,
        "open": close.shift(1).fillna(close),
        "high": close + spread,
        "low": close - spread,
        "dollar_volume": pd.DataFrame(
            RNG.uniform(1e6, 5e7, size=close.shape), index=idx, columns=list(pairs)
        ),
    }


def test_image_geometry_and_binary():
    w = 20
    o = np.linspace(100, 110, w); c = o + 1
    h = c + 2; l = o - 2
    v = np.linspace(1, 10, w); ma = np.full(w, 105.0)
    img = draw_image(o, h, l, c, v, ma)
    assert img.shape == (HEIGHT, w * 3)
    assert set(np.unique(img)) <= {0, 1}
    # every day has a high-low bar in its middle column
    for d in range(w):
        assert img[:PRICE_ROWS, d * 3 + 1].sum() >= 1
    # volume bars live below the price area
    assert img[PRICE_ROWS + 1:, :].sum() > 0


def test_scale_invariance():
    """JKX core property: the image depends on shape, not level — a coin at
    $0.001 and one at $50k with identical relative paths give identical images."""
    w = 20
    base = 1 + 0.01 * np.sin(np.linspace(0, 6, w))
    v = np.linspace(5, 1, w)
    args1 = (base * 0.001, base * 0.001 * 1.02, base * 0.001 * 0.98, base * 0.001, v, base * 0.001)
    args2 = (base * 5e4, base * 5e4 * 1.02, base * 5e4 * 0.98, base * 5e4, v, base * 5e4)
    assert np.array_equal(draw_image(*args1), draw_image(*args2))


def test_no_lookahead_in_dataset():
    """The image at date t must not change when data AFTER t changes."""
    panels1 = _synthetic_panels()
    panels2 = {k: v.copy() for k, v in panels1.items()}
    t = panels1["close"].index[60]
    for k in ("close", "open", "high", "low", "dollar_volume"):
        panels2[k].iloc[61:] = panels2[k].iloc[61:] * 7.7  # mangle the future

    sample = pd.MultiIndex.from_tuples([(t, "AAA"), (t, "BBB")], names=["date", "pair"])
    x1, i1 = build_image_dataset(panels1, sample, window=20)
    x2, i2 = build_image_dataset(panels2, sample, window=20)
    assert len(i1) == 2 and i1.equals(i2)
    assert np.array_equal(x1, x2)


def test_incomplete_window_dropped():
    panels = _synthetic_panels()
    early = panels["close"].index[5]  # only 6 bars of history
    sample = pd.MultiIndex.from_tuples([(early, "AAA")], names=["date", "pair"])
    x, idx = build_image_dataset(panels, sample, window=20)
    assert len(idx) == 0 and x.shape[0] == 0
