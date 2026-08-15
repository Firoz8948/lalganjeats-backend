from app.modules.restaurants.service_area import (
    customer_within_service_area,
    max_active_zone_radius_km,
)


class _Zone:
    def __init__(self, radius_km, is_active=True):
        self.radius_km = radius_km
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
