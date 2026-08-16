from app.modules.restaurants.service_area import (
    customer_within_service_area,
    delivery_charge_for_distance,
    matching_delivery_exception,
    max_active_zone_radius_km,
)
from app.modules.restaurants.service import _restaurant_visible_for_customer


class _Zone:
    def __init__(
        self,
        radius_km,
        is_active=True,
        rate=0,
        pricing_type="flat",
    ):
        self.radius_km = radius_km
        self.is_active = is_active
        self.rate = rate
        self.pricing_type = pricing_type


class _Exception:
    def __init__(
        self,
        latitude=26.1600,
        longitude=80.9000,
        radius_meters=500,
        delivery_charge=75,
        is_active=True,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.radius_meters = radius_meters
        self.delivery_charge = delivery_charge
        self.is_active = is_active


def test_max_active_zone_radius_uses_largest_active_zone_only():
    zones = [
        _Zone(2),
        _Zone(6),
        _Zone(4),
        _Zone(10, is_active=False),
    ]
    assert max_active_zone_radius_km(zones) == 6.0


def test_max_active_zone_radius_returns_none_when_no_active_zones():
    assert max_active_zone_radius_km([_Zone(5, is_active=False)]) is None
    assert max_active_zone_radius_km([]) is None


def test_customer_inside_max_zone_is_in_service_area():
    # ~3.1 km from center when radius is 6
    assert customer_within_service_area(
        customer_lat=26.1600,
        customer_lng=80.9000,
        center_lat=26.1400,
        center_lng=80.9000,
        max_radius_km=6.0,
    ) is True


def test_customer_outside_max_zone_is_out_of_service_area():
    # ~11+ km from center when radius is 6
    assert customer_within_service_area(
        customer_lat=26.2500,
        customer_lng=80.9000,
        center_lat=26.1400,
        center_lng=80.9000,
        max_radius_km=6.0,
    ) is False


def test_missing_coords_or_radius_means_not_in_service_area():
    assert customer_within_service_area(None, 80.9, 26.14, 80.9, 6.0) is False
    assert customer_within_service_area(26.16, None, 26.14, 80.9, 6.0) is False
    assert customer_within_service_area(26.16, 80.9, None, 80.9, 6.0) is False
    assert customer_within_service_area(26.16, 80.9, 26.14, 80.9, None) is False


def test_distance_uses_first_active_zone_that_contains_customer():
    zones = [
        _Zone(2, rate=20),
        _Zone(4, rate=40),
    ]

    assert delivery_charge_for_distance(zones, 3) == 40


def test_per_km_zone_multiplies_rate_by_actual_distance():
    zones = [_Zone(4, rate=12, pricing_type="per_km")]

    assert delivery_charge_for_distance(zones, 3) == 36


def test_customer_inside_exception_radius_gets_exception_charge():
    exception = _Exception()
    match = matching_delivery_exception(
        [exception],
        customer_lat=26.1620,
        customer_lng=80.9000,
    )
    assert match is exception
    assert float(match.delivery_charge) == 75


def test_exception_radius_is_configurable_and_inactive_points_are_ignored():
    far_customer = (26.1670, 80.9000)  # roughly 780 m away
    assert matching_delivery_exception(
        [_Exception(radius_meters=500)],
        *far_customer,
    ) is None
    assert matching_delivery_exception(
        [_Exception(radius_meters=1000)],
        *far_customer,
    ) is not None
    assert matching_delivery_exception(
        [_Exception(radius_meters=1000, is_active=False)],
        *far_customer,
    ) is None


def test_exception_makes_every_restaurant_in_its_tenant_visible():
    class _Tenant:
        center_latitude = 25.0
        center_longitude = 80.0
        zones = [_Zone(1)]
        delivery_exceptions = [_Exception(radius_meters=500)]

    class _Restaurant:
        tenant = _Tenant()

    # Far outside the tenant's normal 1 km ring, but inside its exception island.
    assert _restaurant_visible_for_customer(
        _Restaurant(),
        customer_lat=26.1620,
        customer_lng=80.9000,
    ) is True
