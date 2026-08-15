from decimal import Decimal, ROUND_HALF_UP


MONEY_PLACES = Decimal("0.01")


def calculate_display_price(
    seller_transfer_price: Decimal,
    markup_percent: float,
) -> Decimal:
    """Return transfer price plus configured markup, rounded as currency."""
    transfer = Decimal(str(seller_transfer_price))
    markup = Decimal(str(markup_percent))
    multiplier = Decimal("1") + (markup / Decimal("100"))
    return (transfer * multiplier).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
