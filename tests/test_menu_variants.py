from decimal import Decimal

from app.modules.payments.pricing import calculate_display_price


def test_half_and_full_variants_get_independent_display_prices():
    half_display = calculate_display_price(Decimal("80"), 30)
    full_display = calculate_display_price(Decimal("140"), 30)
    assert half_display == Decimal("104.00")
    assert full_display == Decimal("182.00")
    assert full_display > half_display


def test_variant_label_normalize_keeps_half_full_casing_friendly():
    from app.modules.admin.services.restaurants import normalize_variant_label

    assert normalize_variant_label("  half ") == "Half"
    assert normalize_variant_label("FULL") == "Full"
    assert normalize_variant_label("Regular") == "Regular"
