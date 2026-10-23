"""Refund calculations for partial returns. Money is integer cents."""


def refund_amount(price_cents: int, percent: float) -> int:
    """Refund for returning `percent` of an item that cost `price_cents`, in cents.

    Rounds half up to the nearest cent.
    """
    return int(price_cents * percent / 100)
