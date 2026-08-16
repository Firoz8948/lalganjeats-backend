from types import SimpleNamespace

from app.modules.payments.payment_split import calculate_split
from app.modules.payments.service import initial_earning_status


def _settings(**overrides) -> SimpleNamespace:
    values = dict(
        delivery_charge=20,
        free_delivery_above=30,
        delivery_boy_per_order_earning=33,
        platform_fee_percent=10,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_admin_pl_uses_zone_charge_as_delivery_partner_earning():
    split = calculate_split(
        display_total=100,
        actual_price_total=70,
        settings=_settings(delivery_boy_per_order_earning=999),
        delivery_charge=20,
    )

    assert split.hotel_earning == 70
    assert split.delivery_earning == 20
    assert split.admin_earning == 10


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

    assert split.admin_earning == 100 - 70 - 20


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
    assert split.admin_earning == 100 - 70 - 20 + 2


def test_new_manual_earning_is_unsettled():
    assert initial_earning_status() == "unsettled"
