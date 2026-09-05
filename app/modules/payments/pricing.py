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


def resolve_display_price(
    seller_transfer_price: Decimal,
    markup_percent: float,
    explicit_display: float | Decimal | None = None,
) -> Decimal:
    """Keep an edited display price; otherwise apply the configured markup."""
    if explicit_display is not None:
        return Decimal(str(explicit_display)).quantize(
            MONEY_PLACES, rounding=ROUND_HALF_UP
        )
    return calculate_display_price(seller_transfer_price, markup_percent)
