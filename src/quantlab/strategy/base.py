"""``IStrategy`` — the production contract shared by backtest and live.

A strategy implements :meth:`generate_signals` (decision-time target weights).
The **same object** is consumed by the vectorized backtest engine
(:func:`quantlab.backtest.run_backtest`) and by the live engine — research-to-
production parity by construction. :meth:`manage_risk` and :meth:`size_position`
are optional hooks (default = passthrough); :meth:`target_weights` runs the full
pipeline.

No look-ahead: the backtest engine shifts the signal one bar (held T+1), so a
strategy must only use data up to and including each timestamp. A strategy whose
past signal values change when future bars are appended is leaking the future —
guard it with a truncation-invariance test (see ``tests/test_strategy_interface.py``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class IStrategy(ABC):
    """Base class for a tradable strategy.

    Class attributes carry metadata; subclasses set them (or pass via ``__init__``).
    """

    id: str = "unnamed"
    name: str = "Unnamed Strategy"
    instruments: tuple[str, ...] = ()
    status: str = "research"  # research | testing | confirmed | live

    @abstractmethod
    def generate_signals(self, prices: pd.DataFrame) -> pd.Series:
        """Return the decision-time target weight per timestamp.

        Indexed like ``prices``; ``+1`` fully long, ``-1`` short, ``0`` flat. The
        engine applies the ``T+1`` shift, so only information available up to and
        including each timestamp may be used.
        """

    def manage_risk(self, signal: pd.Series, prices: pd.DataFrame) -> pd.Series:
        """Apply gates / stops / exposure caps. Default: passthrough."""
        return signal

    def size_position(self, signal: pd.Series, prices: pd.DataFrame) -> pd.Series:
        """Scale the raw signal into target weights (e.g. vol-target). Default: passthrough."""
        return signal

    def target_weights(self, prices: pd.DataFrame) -> pd.Series:
        """Full pipeline: ``generate_signals -> manage_risk -> size_position``."""
        s = self.generate_signals(prices)
        s = self.manage_risk(s, prices)
        s = self.size_position(s, prices)
        return s.reindex(prices.index).fillna(0.0)

    def on_data(self, bar) -> float:
        """Event-driven hook for live / event-simulation: target weight given the
        latest bar. Optional — override for streaming strategies."""
        raise NotImplementedError(f"{self.id} has no event-driven on_data()")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r} status={self.status!r}>"
