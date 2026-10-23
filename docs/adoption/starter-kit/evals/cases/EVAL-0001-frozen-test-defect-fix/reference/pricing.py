"""Refund calculations for partial returns. Money is integer cents."""
from decimal import ROUND_HALF_UP, Decimal


def refund_amount(price_cents: int, percent: float) -> int:
    """Refund for returning `percent` of an item that cost `price_cents`, in cents.

    Rounds half up to the nearest cent.
    """
    exact = Decimal(price_cents) * Decimal(str(percent)) / Decimal(100)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))
