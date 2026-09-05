from types import SimpleNamespace

from app.modules.delivery.dispatch import (
    is_broadcast_recipient,
    is_open_unassigned_order,
)


def test_offline_delivery_partner_still_receives_broadcast():
    user = SimpleNamespace(role="delivery_partner", is_active=True)
    profile = SimpleNamespace(is_online=False)
    assert is_broadcast_recipient(user, profile) is True


def test_deactivated_delivery_partner_is_not_a_broadcast_recipient():
    user = SimpleNamespace(role="delivery_partner", is_active=False)
    profile = SimpleNamespace(is_online=True)
    assert is_broadcast_recipient(user, profile) is False


def test_unassigned_accepted_order_stays_open_for_late_online_partners():
    order = SimpleNamespace(delivery_partner_id=None, status="accepted")
    assert is_open_unassigned_order(order) is True


def test_assigned_or_delivered_order_is_not_open_for_new_offers():
    taken = SimpleNamespace(delivery_partner_id=28, status="accepted")
    delivered = SimpleNamespace(delivery_partner_id=None, status="delivered")
    assert is_open_unassigned_order(taken) is False
    assert is_open_unassigned_order(delivered) is False
