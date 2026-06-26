"""Decision-time causality probe — the programmatic look-ahead guard.

A *causal* trading signal uses only information available up to bar ``t``; its
value at ``t`` therefore must NOT change when future bars are appended. This
module recomputes a signal on truncated prefixes of the price history and checks
that the boundary values are unchanged. Any mismatch means the signal peeks into
the future (``Close.shift(-1)``, a full-sample normalisation, ``diff(-1)``, …) —
its backtest metrics are fiction.

It is the enforcement backstop behind the agent harness's "never shift(-n)"
instruction: a model can ignore a prompt, but it cannot fake an unchanged
boundary. Lives in ``quantlab`` (not ``agent``) so the sandboxed backtest
subprocess — which only has ``quantlab`` on its path — can import it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd


def assess_causality(
    make_signal: Callable[[pd.DataFrame], pd.Series],
    prices: pd.DataFrame,
    *,
    fracs: tuple[float, ...] = (0.5, 0.65, 0.8, 0.92),
    tail: int = 6,
    tol: float = 1e-6,
) -> dict:
    """Probe ``make_signal`` for look-ahead by truncating the price history.

    ``make_signal(px)`` must return a position Series aligned to ``px.index``.
    For each cut point we recompute the signal on ``prices.iloc[:cut]`` and
    compare its last ``tail`` values to the full-sample signal at the same
    timestamps. A causal signal matches exactly; a future-peeking one differs.

    Returns ``{causal, boundary_bars_checked, violations, examples}``. ``causal``
    is True only if at least one cut was checked and zero boundary bars changed.
    """
    full = make_signal(prices)
    full = pd.Series(full, index=prices.index)
    n = len(prices)
    checks = violations = 0
    examples: list[str] = []
    for frac in fracs:
        cut = int(n * frac)
        if cut < 40 or cut >= n:
            continue
        try:
            sub = make_signal(prices.iloc[:cut])
            sub = pd.Series(sub, index=prices.index[:cut])
        except Exception as exc:  # a signal that cannot run on a prefix is itself suspect
            violations += 1
            checks += 1
            if len(examples) < 3:
                examples.append(f"prefix@{frac:.2f}: raised {type(exc).__name__}")
            continue
        t = sub.iloc[-tail:]
        ref = full.reindex(t.index)
        diff = np.abs(np.asarray(t.values, dtype=float) - np.asarray(ref.values, dtype=float))
        diff = np.nan_to_num(diff, nan=1.0)  # NaN at the boundary (future-dependent) counts as change
        checks += int(len(t))
        bad = int((diff > tol).sum())
        violations += bad
        if bad and len(examples) < 3:
            examples.append(f"@{frac:.2f}: {bad}/{len(t)} boundary bars changed when future appended")
    return {
        "causal": bool(checks > 0 and violations == 0),
        "boundary_bars_checked": int(checks),
        "violations": int(violations),
        "examples": examples,
    }
