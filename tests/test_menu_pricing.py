from decimal import Decimal

from app.modules.payments.pricing import calculate_display_price


def test_display_price_adds_configured_markup_to_seller_transfer_price():
    assert calculate_display_price(Decimal("100"), 30) == Decimal("130.00")


def test_display_price_rounds_to_two_decimal_places():
    assert calculate_display_price(Decimal("99.99"), 12.5) == Decimal("112.49")


def test_zero_markup_keeps_seller_transfer_price():
    assert calculate_display_price(Decimal("75.50"), 0) == Decimal("75.50")
