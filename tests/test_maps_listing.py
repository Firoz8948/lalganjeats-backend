"""Restaurant list must pay Google at most once per tenant, not once per restaurant."""
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.restaurants.service import (
    _restaurant_visible_for_customer,
    tenant_road_km_to_customer,
)


def _zone(initial=0, final=10, rate=30):
    return SimpleNamespace(
        is_active=True,
        initial_km=initial,
        final_km=final,
        radius_km=None,
        rate=rate,
        delivery_partner_rate=20,
        pricing_type="flat",
    )


def _tenant(tid=1):
    return SimpleNamespace(
        id=tid,
        center_latitude=25.86,
        center_longitude=85.18,
        zones=[_zone()],
        delivery_exceptions=[],
    )


def _restaurant(rid, tenant):
    return SimpleNamespace(
        id=rid,
        tenant=tenant,
        latitude=25.86 + rid * 0.001,
        longitude=85.18,
    )


def test_tenant_road_km_uses_in_request_cache():
    tenant = _tenant()
    calls = {"n": 0}

    def fake_distance(*_a, **_k):
        calls["n"] += 1
        return 3.2, 12

    cache = {}
    with patch(
        "app.modules.restaurants.service.distance_and_drive_minutes",
        side_effect=fake_distance,
    ):
        a = tenant_road_km_to_customer(tenant, 25.90, 85.20, cache)
        b = tenant_road_km_to_customer(tenant, 25.90, 85.20, cache)
    assert a == 3.2 and b == 3.2
    assert calls["n"] == 1


def test_visibility_is_shared_across_restaurants_of_same_tenant():
    tenant = _tenant()
    r1 = _restaurant(1, tenant)
    r2 = _restaurant(2, tenant)
    cache = {}
    calls = {"n": 0}

    def fake_distance(*_a, **_k):
        calls["n"] += 1
        return 2.0, 8

    with patch(
        "app.modules.restaurants.service.distance_and_drive_minutes",
        side_effect=fake_distance,
    ):
        assert _restaurant_visible_for_customer(r1, 25.90, 85.20, cache) is True
        assert _restaurant_visible_for_customer(r2, 25.90, 85.20, cache) is True
    assert calls["n"] == 1


