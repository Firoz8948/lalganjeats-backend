from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.modules.otp.service import customer_visible_delivery_otp


def test_customer_sees_delivery_otp_after_partner_sends_it():
    order = SimpleNamespace(
        status="picked_up",
        delivery_otp="4821",
        delivery_otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=8),
        delivery_otp_verified_at=None,
    )
    assert customer_visible_delivery_otp(order) == "4821"


def test_customer_does_not_see_otp_before_it_is_sent():
    order = SimpleNamespace(
        status="picked_up",
        delivery_otp=None,
        delivery_otp_expires_at=None,
        delivery_otp_verified_at=None,
    )
    assert customer_visible_delivery_otp(order) is None


def test_customer_does_not_see_otp_after_handover_is_verified():
    order = SimpleNamespace(
        status="picked_up",
        delivery_otp="4821",
        delivery_otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=8),
        delivery_otp_verified_at=datetime.now(timezone.utc),
    )
    assert customer_visible_delivery_otp(order) is None


def test_customer_does_not_see_otp_after_order_is_delivered():
    order = SimpleNamespace(
        status="delivered",
        delivery_otp="4821",
        delivery_otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=8),
        delivery_otp_verified_at=None,
    )
    assert customer_visible_delivery_otp(order) is None


def test_customer_does_not_see_otp_before_pickup():
    order = SimpleNamespace(
        status="ready",
        delivery_otp="4821",
        delivery_otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=8),
        delivery_otp_verified_at=None,
    )
    assert customer_visible_delivery_otp(order) is None
