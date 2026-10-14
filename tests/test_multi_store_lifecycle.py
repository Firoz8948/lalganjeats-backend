from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.core.razorpay_service as razorpay_service
from app.modules.delivery.dispatch import is_open_unassigned_order
from app.modules.orders import multi_store_lifecycle as life
from app.modules.orders.payment_state import mark_prepaid_failed, sync_sub_order_payment


class _FakeQuery:
    def filter(self, *args):
        return self

    def delete(self, **kw):
        return 0

    def update(self, *args, **kw):
        return 0


class _FakeDb:
    def __init__(self):
        self.commits = 0

    def query(self, *args):
        return _FakeQuery()

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        pass


def _sub(oid, suffix, display, actual, packing=0, status="pending", name=None):
    return SimpleNamespace(
        id=oid,
        order_number=f"LE-2026-00412({suffix})",
        status=status,
        display_total=Decimal(str(display)),
        actual_total=Decimal(str(actual)),
        packing_charge=Decimal(str(packing)),
        subtotal=Decimal(str(display)),
        notes=None,
        items=[SimpleNamespace(name=f"{name or suffix} item", quantity=1)],
        restaurant=SimpleNamespace(name=name or f"Store {suffix}", phone=None),
        payment_method="online",
        payment_status="pending",
        razorpay_order_id=None,
        razorpay_payment_id=None,
    )


def _parent(*, payment_method="online", payment_status="paid", percent_off=None):
    a = _sub(11, "a", 100, 80, name="Shiv Bakers")
    b = _sub(12, "b", 50, 45, packing=10, name="Fresh Mart")
    discount = Decimal("0")
    if percent_off:
        discount = (Decimal("150") * Decimal(str(percent_off)) / 100).quantize(Decimal("0.01"))
    parent = SimpleNamespace(
        id=10,
        order_number="LE-2026-00412",
        is_multi_store=True,
        parent_order_id=None,
        status="pending",
        payment_method=payment_method,
        payment_status=payment_status,
        razorpay_order_id="order_x",
        razorpay_payment_id="pay_x" if payment_status == "paid" else None,
        subtotal=Decimal("150"),
        display_total=Decimal("150"),
        actual_total=Decimal("125"),
        packing_charge=Decimal("10"),
        platform_fee=Decimal("5"),
        delivery_fee=Decimal("30"),
        delivery_partner_earning=Decimal("25"),
        discount=discount,
        promo_code_id=7 if percent_off else None,
        promo_code="SAVE" if percent_off else None,
        promo_discount_type="percent" if percent_off else None,
        promo_percent_off=Decimal(str(percent_off)) if percent_off else None,
        promo_flat_off=None,
        total_amount=Decimal("195") - discount,
        admin_earning=Decimal("0"),
        refunded_amount=None,
        notes=None,
        sub_orders=[a, b],
        items=[],
    )
    for sub in parent.sub_orders:
        sub.parent_order = parent
    return parent


@pytest.fixture
def refunds(monkeypatch):
    calls = []

    def fake_refund(payment_id, amount, notes=None):
        calls.append((payment_id, amount))
        return {"id": f"rfnd_{len(calls)}"}

    monkeypatch.setattr(razorpay_service, "refund_payment", fake_refund)
    return calls


def test_parent_waits_for_first_store_to_accept():
    parent = _parent()
    assert life.derived_parent_status(parent) == "pending"
    parent.sub_orders[0].status = "accepted"
    assert life.derived_parent_status(parent) == "accepted"


def test_parent_is_ready_only_when_every_live_store_is_ready():
    parent = _parent()
    parent.sub_orders[0].status = "ready"
    parent.sub_orders[1].status = "accepted"
    assert life.derived_parent_status(parent) == "accepted"
    parent.sub_orders[1].status = "cancelled"
    assert life.derived_parent_status(parent) == "ready"


def test_rider_owned_status_is_not_overridden():
    parent = _parent()
    parent.status = "picked_up"
    assert life.derived_parent_status(parent) == "picked_up"


def test_labels_and_lines_come_from_live_stores():
    parent = _parent()
    assert life.restaurant_label(parent) == "Shiv Bakers + Fresh Mart"
    assert [i.name for i in life.order_lines(parent)] == ["Shiv Bakers item", "Fresh Mart item"]
    parent.sub_orders[1].status = "cancelled"
    assert life.restaurant_label(parent) == "Shiv Bakers"


def test_store_cancel_refunds_only_that_store(refunds):
    parent = _parent()
    db = _FakeDb()
    life.cancel_store_share(db, parent.sub_orders[1], "Cancelled by store")

    assert parent.sub_orders[1].status == "cancelled"
    assert parent.status == "pending"
    assert parent.display_total == Decimal("100")
    assert parent.packing_charge == Decimal("0")
    # 100 goods + 30 delivery + 5 platform; delivery and platform stay.
    assert parent.total_amount == Decimal("135")
    assert refunds == [("pay_x", 60.0)]
    assert parent.refunded_amount == Decimal("60.0")


def test_store_cancel_reapplies_percent_promo(refunds):
    parent = _parent(percent_off=10)
    assert parent.total_amount == Decimal("180")
    life.cancel_store_share(_FakeDb(), parent.sub_orders[1], "Cancelled by store")
    assert parent.discount == Decimal("10.00")
    assert parent.total_amount == Decimal("125")
    assert refunds == [("pay_x", 55.0)]


def test_cash_order_cancel_only_lowers_amount_to_collect(refunds):
    parent = _parent(payment_method="cash", payment_status="pending")
    life.cancel_store_share(_FakeDb(), parent.sub_orders[1], "Cancelled by store")
    assert parent.total_amount == Decimal("135")
    assert refunds == []


def test_last_store_cancel_cancels_parent_and_refunds_rest(refunds):
    parent = _parent()
    db = _FakeDb()
    life.cancel_store_share(db, parent.sub_orders[1], "Cancelled by store")
    life.cancel_store_share(db, parent.sub_orders[0], "Cancelled by store")
    assert parent.status == "cancelled"
    assert refunds == [("pay_x", 60.0), ("pay_x", 135.0)]


def test_cancelling_twice_never_refunds_twice(refunds):
    parent = _parent()
    db = _FakeDb()
    life.cancel_store_share(db, parent.sub_orders[1], "Cancelled by store")
    life.cancel_store_share(db, parent.sub_orders[1], "Cancelled by store")
    assert refunds == [("pay_x", 60.0)]


def test_failed_refund_is_flagged_for_admin(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("razorpay down")

    monkeypatch.setattr(razorpay_service, "refund_payment", boom)
    parent = _parent()
    life.cancel_store_share(_FakeDb(), parent.sub_orders[1], "Cancelled by store")
    assert "REFUND PENDING" in parent.notes
    assert parent.refunded_amount is None


def test_store_cannot_cancel_after_pickup(refunds):
    parent = _parent()
    parent.status = "picked_up"
    with pytest.raises(HTTPException):
        life.cancel_store_share(_FakeDb(), parent.sub_orders[0], "Cancelled by store")
    assert refunds == []


def test_rider_status_and_payment_copy_to_live_stores():
    parent = _parent(payment_method="cash", payment_status="pending")
    parent.sub_orders[1].status = "cancelled"
    parent.status = "delivered"
    parent.payment_status = "paid"
    life.propagate_rider_status(parent)
    assert parent.sub_orders[0].status == "delivered"
    assert parent.sub_orders[0].payment_status == "paid"
    assert parent.sub_orders[1].status == "cancelled"


def test_online_payment_is_mirrored_on_sub_orders():
    parent = _parent()
    sync_sub_order_payment(parent)
    assert {s.payment_status for s in parent.sub_orders} == {"paid"}
    assert {s.razorpay_payment_id for s in parent.sub_orders} == {"pay_x"}


def test_failed_prepaid_cancels_every_store_part():
    parent = _parent(payment_status="pending")
    assert mark_prepaid_failed(parent)
    assert parent.status == "cancelled"
    assert {s.status for s in parent.sub_orders} == {"cancelled"}


def test_sub_orders_are_never_offered_to_riders():
    parent = _parent()
    sub = parent.sub_orders[0]
    sub.status = "accepted"
    sub.parent_order_id = parent.id
    sub.delivery_partner_id = None
    assert not is_open_unassigned_order(sub)
    parent.status = "accepted"
    parent.delivery_partner_id = None
    assert is_open_unassigned_order(parent)


def test_settlement_pays_each_store_and_rider_once(monkeypatch):
    from app.modules.payments import router as pay_router

    hotel, rider = [], []
    monkeypatch.setattr(pay_router, "_record_restaurant_earning", lambda db, **kw: hotel.append(kw))
    monkeypatch.setattr(pay_router, "_record_delivery_earning", lambda db, **kw: rider.append(kw))

    parent = _parent()
    parent.sub_orders[1].status = "cancelled"
    parent.delivery_partner_id = 99
    pay_router._settle_multi_store(None, parent)

    assert [(h["order_id"], h["amount"], h["platform_fee"]) for h in hotel] == [(11, 80.0, 0.0)]
    assert [(r["order_id"], r["partner_id"], r["amount"]) for r in rider] == [(10, 99, 25.0)]
