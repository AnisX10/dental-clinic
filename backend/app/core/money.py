"""Decimal-safe money helpers. Currency is DZD; values use NUMERIC(12,2).

Amounts are serialized to JSON as strings (e.g. "3000.00") to avoid any
floating-point round-tripping in clients.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")


def to_money(value) -> Decimal:
    """Coerce int/str/float input to a 2-decimal Decimal, or raise ValueError."""
    try:
        if isinstance(value, Decimal):
            d = value
        elif isinstance(value, bool):
            raise ValueError("Invalid amount")
        elif isinstance(value, int):
            d = Decimal(value)
        elif isinstance(value, str):
            cleaned = value.strip().replace("\u00a0", "").replace(" ", "")
            if not cleaned:
                raise ValueError("Invalid amount")
            d = Decimal(cleaned)
        elif isinstance(value, float):
            # Tolerate floats from JSON clients but quantize immediately.
            d = Decimal(str(value))
        else:
            raise ValueError("Invalid amount")
    except InvalidOperation:
        raise ValueError("Invalid amount") from None
    if not d.is_finite():
        raise ValueError("Invalid amount")
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def serialize_amount(value: Decimal | None) -> str:
    if value is None:
        value = Decimal("0")
    return str(value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))
