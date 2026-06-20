"""Tests for the paper-mode OMS (fills, confirm gate, bracket OCO)."""

from __future__ import annotations

from live.oms import OMS, Order, OrderStatus, OrderType, PaperBroker, Side


def test_market_order_fills_at_mark():
    b = PaperBroker()
    b.mark("ES", 5000)
    o = OMS(b).submit(Order("ES", Side.BUY, 1, OrderType.MARKET))
    assert o.status == OrderStatus.FILLED and o.fill_price == 5000
    assert b.positions() == {"ES": 1}


def test_confirm_gate_rejects_and_does_not_send():
    b = PaperBroker()
    b.mark("ES", 5000)
    oms = OMS(b, confirm=lambda order: False)  # human declines
    o = oms.submit(Order("ES", Side.BUY, 1, OrderType.MARKET))
    assert o.status == OrderStatus.REJECTED
    assert b.positions() == {}


def test_limit_rests_then_fills_on_cross():
    b = PaperBroker()
    b.mark("ES", 5000)
    o = OMS(b).submit(Order("ES", Side.BUY, 1, OrderType.LIMIT, limit_price=4990))
    assert o.status == OrderStatus.PENDING
    b.mark("ES", 4985)  # crosses the limit
    assert o.status == OrderStatus.FILLED and o.fill_price == 4990


def test_bracket_stop_fills_and_cancels_tp():
    b = PaperBroker()
    b.mark("ES", 5000)
    br = OMS(b).submit_bracket("ES", Side.BUY, 1, stop_loss=4950, take_profit=5100)
    assert br["parent"].status == OrderStatus.FILLED  # market entry at 5000
    b.mark("ES", 4940)  # hits the stop
    stop = next(c for c in br["children"] if c.type == OrderType.STOP)
    tp = next(c for c in br["children"] if c.type == OrderType.LIMIT)
    assert stop.status == OrderStatus.FILLED
    assert tp.status == OrderStatus.CANCELLED          # OCO
    assert b.positions().get("ES", 0) == 0             # flat after stop


def test_bracket_take_profit_fills_and_cancels_stop():
    b = PaperBroker()
    b.mark("ES", 5000)
    br = OMS(b).submit_bracket("ES", Side.BUY, 1, stop_loss=4950, take_profit=5100)
    b.mark("ES", 5120)  # hits the take-profit
    tp = next(c for c in br["children"] if c.type == OrderType.LIMIT)
    stop = next(c for c in br["children"] if c.type == OrderType.STOP)
    assert tp.status == OrderStatus.FILLED
    assert stop.status == OrderStatus.CANCELLED
    assert b.positions().get("ES", 0) == 0
