"""Unit tests: money helpers and rate limiter."""
from decimal import Decimal

import pytest

from app.core.money import serialize_amount, to_money
from app.core.rate_limit import RateLimiter


def test_money_parsing():
    assert to_money("3000") == Decimal("3000.00")
    assert to_money("1500.5") == Decimal("1500.50")
    assert to_money("2 500") == Decimal("2500.00")
    assert to_money(1200) == Decimal("1200.00")
    assert to_money(0) == Decimal("0.00")


def test_money_rejects_garbage():
    for bad in ("abc", "", "  ", "1.2.3", "NaN", "Infinity"):
        with pytest.raises(ValueError):
            to_money(bad)


def test_money_serialization():
    assert serialize_amount(Decimal("3000")) == "3000.00"
    assert serialize_amount(None) == "0.00"
    assert serialize_amount(Decimal("0.1")) == "0.10"


def test_rate_limiter_blocks_after_threshold():
    limiter = RateLimiter(max_attempts=3, window_seconds=60)
    assert not limiter.is_blocked("u|ip")
    for _ in range(3):
        limiter.record("u|ip")
    assert limiter.is_blocked("u|ip")
    assert not limiter.is_blocked("other|ip")
    limiter.reset("u|ip")
    assert not limiter.is_blocked("u|ip")
