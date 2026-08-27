from types import SimpleNamespace

from app.modules.payments.breakdown import (
    admin_price_view,
    build_order_price_breakdown,
    customer_price_view,
)
from app.modules.payments.payment_split import calculate_split
from app.modules.payments.service import initial_earning_status


def _settings(**overrides) -> SimpleNamespace:
    values = dict(
        delivery_charge=20,
        free_delivery_above=30,
        delivery_boy_per_order_earning=33,
        platform_fee_percent=10,
        platform_charge_rupees=0,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_customer_view_formula():
    c = customer_price_view(
        display_price=91,
        platform_fee=2,
        delivery_charge=24.72,
        discount=0,
    )
    assert c.customer_total == 117.72


def test_admin_view_cash_profit():
    a = admin_price_view(
        customer_total=117.72,
        hotel_payout=70,
        delivery_payout=24.72,
    )
    assert a.admin_profit == 23.0
    assert a.is_loss is False


def test_build_breakdown_matches_user_example():
    bd = build_order_price_breakdown(
        display_price=91,
        hotel_payout=70,
        platform_fee=2,
        delivery_charge=24.72,
    )
    assert bd.customer.customer_total == 117.72
    assert bd.admin.admin_profit == 23.0
    assert bd.admin.is_loss is False


def test_admin_pl_does_not_subtract_delivery_from_food_twice():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(delivery_boy_per_order_earning=999),
        delivery_charge=20,
    )

    assert split.hotel_earning == 70
    assert split.delivery_earning == 20
    # Cash profit: (100+20) - 70 - 20 = 30  (or 100 - 70 with platform 0)
    assert split.admin_earning == 30
    assert split.customer_pays == 120


def test_platform_fee_percent_does_not_change_admin_pl():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(
            platform_fee_percent=99,
            delivery_boy_per_order_earning=33,
        ),
        delivery_charge=20,
    )

    assert split.admin_earning == 30


def test_split_uses_only_display_and_transfer_prices():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(),
        delivery_charge=20,
    )

    assert split.display_total == 100
    assert split.actual_price_total == 70


def test_split_uses_zone_delivery_charge_not_fixed_payment_setting():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(
            delivery_charge=999,
            free_delivery_above=0,
            platform_charge_rupees=2,
        ),
        delivery_charge=40,
    )

    assert split.delivery_charge == 40
    assert split.platform_charge == 2
    assert split.customer_pays == 142
    # 142 - 70 - 40 = 32
    assert split.admin_earning == 32


def test_platform_charge_is_added_to_customer_total_and_admin_pl():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(
            delivery_boy_per_order_earning=999,
            platform_charge_rupees=2,
        ),
        delivery_charge=20,
    )

    assert split.customer_pays == 122
    assert split.delivery_earning == 20
    # 122 - 70 - 20 = 32
    assert split.admin_earning == 32


def test_discount_reduces_customer_total_and_admin_profit():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(platform_charge_rupees=2),
        delivery_charge=20,
        discount=10,
    )
    assert split.customer_pays == 112
    assert split.admin_earning == 22


def test_new_manual_earning_is_unsettled():
    assert initial_earning_status() == "unsettled"
