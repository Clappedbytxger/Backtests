"""Order Management System (OMS) — broker-agnostic, paper-mode, human-in-the-loop.

Formalizes order handling for the live path: parent/child **bracket** orders
(entry + stop-loss + take-profit with OCO), a pluggable :class:`BrokerAdapter`
(with a built-in :class:`PaperBroker` simulator) and a mandatory **confirm gate**
so every order passes a human check before it reaches a broker.

This is deliberately deterministic and contains **no LLM** — the autonomous agent
has no access to it (research and execution are separated). Real brokers (IBKR via
``ib_async``, CTI via MT5) plug in by implementing :class:`BrokerAdapter`; the
existing 0108 adapters are the reference implementations.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    symbol: str
    side: Side
    qty: float
    type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    parent_id: int | None = None
    id: int | None = None
    status: OrderStatus = OrderStatus.PENDING
    fill_price: float | None = None


class BrokerAdapter:
    """Interface a concrete broker (IBKR/CTI/paper) implements."""

    def place(self, order: Order) -> Order: ...
    def cancel(self, order_id: int) -> None: ...
    def positions(self) -> dict[str, float]: ...
    def mark(self, symbol: str, price: float) -> None: ...


class PaperBroker(BrokerAdapter):
    """In-memory fill simulator. Resting orders fill when ``mark`` crosses them."""

    def __init__(self) -> None:
        self.orders: dict[int, Order] = {}
        self._pos: dict[str, float] = {}
        self._marks: dict[str, float] = {}
        self._ids = itertools.count(1)

    def place(self, order: Order) -> Order:
        if order.id is None:
            order.id = next(self._ids)
        self.orders[order.id] = order
        self._maybe_fill(order)
        return order

    def cancel(self, order_id: int) -> None:
        o = self.orders.get(order_id)
        if o and o.status == OrderStatus.PENDING:
            o.status = OrderStatus.CANCELLED

    def positions(self) -> dict[str, float]:
        return {s: q for s, q in self._pos.items() if q != 0}

    def mark(self, symbol: str, price: float) -> None:
        self._marks[symbol] = price
        for o in list(self.orders.values()):
            if o.status == OrderStatus.PENDING:
                self._maybe_fill(o)

    # -- fill engine --
    def _active(self, o: Order) -> bool:
        if o.parent_id is None:
            return True
        parent = self.orders.get(o.parent_id)
        return parent is not None and parent.status == OrderStatus.FILLED

    def _crosses(self, o: Order, px: float) -> float | None:
        if o.type == OrderType.MARKET:
            return px
        if o.type == OrderType.LIMIT:
            if (o.side == Side.BUY and px <= o.limit_price) or \
               (o.side == Side.SELL and px >= o.limit_price):
                return o.limit_price
        elif o.type == OrderType.STOP:
            if (o.side == Side.BUY and px >= o.stop_price) or \
               (o.side == Side.SELL and px <= o.stop_price):
                return o.stop_price
        return None

    def _maybe_fill(self, o: Order) -> None:
        if o.status != OrderStatus.PENDING or not self._active(o):
            return
        px = self._marks.get(o.symbol)
        if px is None:
            return
        fill = self._crosses(o, px)
        if fill is None:
            return
        o.status = OrderStatus.FILLED
        o.fill_price = fill
        self._pos[o.symbol] = self._pos.get(o.symbol, 0.0) + (o.qty if o.side == Side.BUY else -o.qty)
        # OCO: cancel pending siblings sharing the same parent
        if o.parent_id is not None:
            for s in self.orders.values():
                if s.id != o.id and s.parent_id == o.parent_id and s.status == OrderStatus.PENDING:
                    s.status = OrderStatus.CANCELLED
        # activate children of a just-filled parent
        for c in self.orders.values():
            if c.parent_id == o.id and c.status == OrderStatus.PENDING:
                self._maybe_fill(c)


@dataclass
class OMS:
    """Order manager enforcing a human-in-the-loop confirm gate before every order."""

    broker: BrokerAdapter
    confirm: Callable[[Order], bool] = field(default=lambda order: True)
    mode: str = "paper"

    def submit(self, order: Order) -> Order:
        """Confirm, then route to the broker. A declined order is REJECTED, not sent."""
        if not self.confirm(order):
            order.status = OrderStatus.REJECTED
            return order
        return self.broker.place(order)

    def submit_bracket(
        self, symbol: str, side: Side, qty: float,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        entry_type: OrderType = OrderType.MARKET,
    ) -> dict:
        """Submit an entry order plus OCO stop-loss / take-profit children."""
        parent = self.submit(Order(symbol, side, qty, entry_type, limit_price=entry_price))
        children: list[Order] = []
        if parent.status == OrderStatus.REJECTED:
            return {"parent": parent, "children": children}
        opp = Side.SELL if side == Side.BUY else Side.BUY
        if stop_loss is not None:
            children.append(self.broker.place(
                Order(symbol, opp, qty, OrderType.STOP, stop_price=stop_loss, parent_id=parent.id)))
        if take_profit is not None:
            children.append(self.broker.place(
                Order(symbol, opp, qty, OrderType.LIMIT, limit_price=take_profit, parent_id=parent.id)))
        return {"parent": parent, "children": children}

    def positions(self) -> dict[str, float]:
        return self.broker.positions()

    def cancel(self, order_id: int) -> None:
        self.broker.cancel(order_id)
