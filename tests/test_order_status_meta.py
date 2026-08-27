from app.modules.orders.status_meta import (
    CUSTOMER_STATUS_FLOW,
    HOTEL_SETTABLE_STATUSES,
    ORDER_STATUSES,
    customer_status_meta,
)


def test_canonical_customer_statuses():
    assert ORDER_STATUSES == (
        "pending",
        "accepted",
        "ready",
        "picked_up",
        "delivered",
        "cancelled",
    )
    assert HOTEL_SETTABLE_STATUSES == ("accepted", "ready", "cancelled")
    assert CUSTOMER_STATUS_FLOW[-1] == "delivered"


def test_customer_meta_copy():
    assert "accept" in customer_status_meta("pending").lower()
    assert customer_status_meta("accepted") == "Your food is getting cooked"
    text = customer_status_meta(
        "picked_up",
        delivery_partner_name="Amit",
        bike_name="Activa",
        bike_number="UP32AB1234",
    )
    assert "Amit" in text
    assert "Activa" in text
    assert "UP32AB1234" in text
    assert "on the way" in text.lower()
