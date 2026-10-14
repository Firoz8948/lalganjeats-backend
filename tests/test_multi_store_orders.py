from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.admin.services.dashboard import sequence_from_order_number
from app.modules.orders import multi_store
from app.modules.orders.numbering import order_sequence, sub_order_number
from app.modules.orders.schemas import PlaceMultiStoreOrderRequest

GROCERY = 2
RESTAURANT_CATEGORY = 1


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def options(self, *args):
        return self

    def filter(self, *args):
        return self

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args):
        return _FakeQuery(self._rows)


def _store(rid, *, category=GROCERY, tenant_id=1, is_open=True, name=None):
    return SimpleNamespace(
        id=rid,
        name=name or f"Store {rid}",
        business_category_id=category,
        tenant_id=tenant_id,
        is_open=is_open,
        tenant=SimpleNamespace(id=tenant_id, zones=[], delivery_exceptions=[]),
        show_packing_charge=False,
        packing_charge=0,
    )


def _payload(*ids, **extra):
    return PlaceMultiStoreOrderRequest(
        stores=[
            {"restaurant_id": rid, "items": [{"menu_item_id": rid * 10, "quantity": 1}]}
            for rid in ids
        ],
        delivery_address="Main road",
        delivery_latitude=26.1,
        delivery_longitude=82.1,
        **extra,
    )


def test_sub_order_numbers_use_letter_suffix():
    assert sub_order_number("LE-2026-00412", 0) == "LE-2026-00412(a)"
    assert sub_order_number("LE-2026-00412", 2) == "LE-2026-00412(c)"


def test_order_sequence_ignores_sub_order_suffix():
    assert order_sequence("LE-2026-00412") == 412
    assert order_sequence("LE-2026-00412(b)") == 412
    assert order_sequence("garbage") == 0
    assert order_sequence(None) == 0
    assert sequence_from_order_number("LE-2026-00099(a)") == 99


def test_request_needs_at_least_two_stores():
    with pytest.raises(ValueError):
        _payload(1)


def test_disabled_flag_hides_endpoint(monkeypatch):
    monkeypatch.setattr(multi_store.settings, "MULTI_STORE_ORDERS_ENABLED", False)
    with pytest.raises(HTTPException) as exc:
        multi_store.ensure_enabled()
    assert exc.value.status_code == 404


def test_only_grocery_stores_can_be_combined():
    db = _FakeDb([_store(1), _store(2, category=RESTAURANT_CATEGORY, name="Biryani House")])
    with pytest.raises(HTTPException) as exc:
        multi_store._load_stores(db, _payload(1, 2), GROCERY)
    assert exc.value.status_code == 400
    assert "Biryani House is not a grocery store" in exc.value.detail


def test_store_without_category_is_rejected():
    db = _FakeDb([_store(1), _store(2, category=None)])
    with pytest.raises(HTTPException):
        multi_store._load_stores(db, _payload(1, 2), GROCERY)


def test_closed_store_is_rejected():
    db = _FakeDb([_store(1), _store(2, is_open=False, name="Fresh Mart")])
    with pytest.raises(HTTPException) as exc:
        multi_store._load_stores(db, _payload(1, 2), GROCERY)
    assert "Fresh Mart is closed" in exc.value.detail


def test_stores_from_different_tenants_are_rejected():
    db = _FakeDb([_store(1, tenant_id=1), _store(2, tenant_id=2)])
    with pytest.raises(HTTPException):
        multi_store._load_stores(db, _payload(1, 2), GROCERY)


def test_missing_store_is_rejected():
    db = _FakeDb([_store(1)])
    with pytest.raises(HTTPException) as exc:
        multi_store._load_stores(db, _payload(1, 2), GROCERY)
    assert exc.value.status_code == 404


def test_duplicate_store_is_rejected():
    db = _FakeDb([_store(1)])
    with pytest.raises(HTTPException):
        multi_store._load_stores(db, _payload(1, 1), GROCERY)


def test_store_limit(monkeypatch):
    monkeypatch.setattr(multi_store.settings, "MULTI_STORE_MAX_STORES", 2)
    db = _FakeDb([_store(1), _store(2), _store(3)])
    with pytest.raises(HTTPException) as exc:
        multi_store._load_stores(db, _payload(1, 2, 3), GROCERY)
    assert "at most 2 stores" in exc.value.detail


def test_grocery_stores_in_one_tenant_pass():
    db = _FakeDb([_store(2), _store(1)])
    stores = multi_store._load_stores(db, _payload(1, 2), GROCERY)
    assert [s.id for s in stores] == [1, 2]


def _patch_plan(monkeypatch, *, centre_km=3.0, exception=None):
    stores = [_store(1), _store(2)]
    stores[1].show_packing_charge = True
    stores[1].packing_charge = 10
    calls = {}

    monkeypatch.setattr(multi_store, "grocery_category_id", lambda db: GROCERY)
    monkeypatch.setattr(multi_store, "_load_stores", lambda db, payload, cat: stores)
    monkeypatch.setattr(
        multi_store,
        "resolve_delivery_point",
        lambda db, customer, **kw: ("Main road", 26.1, 82.1),
    )
    monkeypatch.setattr(multi_store, "_restaurant_visible_for_customer", lambda r, lat, lng: True)
    totals = {1: ([("row",)], 100.0, 80.0), 2: ([("row",)], 50.0, 45.0)}
    monkeypatch.setattr(
        multi_store, "build_line_rows", lambda db, r, items: totals[r.id]
    )
    monkeypatch.setattr(
        multi_store,
        "ensure_payment_settings",
        lambda db: SimpleNamespace(platform_charge_rupees=5),
    )

    def fake_centre_km(tenant, lat, lng):
        calls["centre"] = calls.get("centre", 0) + 1
        return centre_km

    def fake_rates(zones, km):
        calls["rates_km"] = km
        return (30.0, 25.0, None)

    monkeypatch.setattr(multi_store, "tenant_road_km_to_customer", fake_centre_km)
    monkeypatch.setattr(multi_store, "matching_delivery_exception", lambda *a: exception)
    monkeypatch.setattr(multi_store, "delivery_rates_for_distance", fake_rates)
    return calls


def test_plan_charges_delivery_and_platform_once(monkeypatch):
    calls = _patch_plan(monkeypatch, centre_km=3.0)
    plan = multi_store.build_plan(None, SimpleNamespace(id=9), _payload(1, 2))

    assert calls["centre"] == 1
    assert calls["rates_km"] == 3.0
    assert plan.display_total == 150.0
    assert plan.actual_total == 125.0
    assert plan.packing_total == 10.0
    assert plan.split.delivery_charge == 30.0
    assert plan.split.delivery_earning == 25.0
    assert plan.split.platform_charge == 5.0
    # 150 goods + 10 packing + 30 delivery + 5 platform
    assert plan.split.customer_pays == 195.0
    assert plan.distance_km == 3.0
    assert [s.display_total for s in plan.stores] == [100.0, 50.0]


def test_plan_uses_delivery_exception_when_matched(monkeypatch):
    _patch_plan(monkeypatch, exception=SimpleNamespace(delivery_charge=15))
    plan = multi_store.build_plan(None, SimpleNamespace(id=9), _payload(1, 2))
    assert plan.split.delivery_charge == 15.0
    assert plan.split.delivery_earning == 15.0


def test_plan_rejects_location_outside_zones(monkeypatch):
    _patch_plan(monkeypatch)
    monkeypatch.setattr(multi_store, "delivery_rates_for_distance", lambda zones, km: None)
    with pytest.raises(HTTPException) as exc:
        multi_store.build_plan(None, SimpleNamespace(id=9), _payload(1, 2))
    assert exc.value.status_code == 400
