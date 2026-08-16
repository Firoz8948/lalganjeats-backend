from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.service import ensure_role_can_register
from app.modules.delivery_partner.service import (
    calculate_age,
    normalize_vehicle_number,
    serialize_public_identity,
)


def test_age_is_calculated_from_dob_without_storing_it():
    assert calculate_age(date(2000, 8, 18), today=date(2026, 8, 17)) == 25
    assert calculate_age(date(2000, 8, 17), today=date(2026, 8, 17)) == 26


def test_future_dob_is_rejected():
    with pytest.raises(ValueError, match="future"):
        calculate_age(date(2027, 1, 1), today=date(2026, 8, 17))


def test_vehicle_number_is_normalized_for_duplicate_checks():
    assert normalize_vehicle_number(" up 72 ab-1234 ") == "UP72AB1234"


def test_public_identity_exposes_only_pickup_information():
    details = SimpleNamespace(
        selfie_url="https://cdn.example/rider.jpg",
        registered_vehicle_number="UP72AB1234",
        bike_info="Black Hero Splendor",
        aadhaar_document_key="private:aadhaar.jpg",
        pan_document_key="private:pan.jpg",
        bank_account_number="1234567890",
    )
    partner = SimpleNamespace(
        full_name="Ravi Kumar",
        phone="9999999999",
        delivery_partner_details=details,
    )

    identity = serialize_public_identity(partner)

    assert identity == {
        "name": "Ravi Kumar",
        "selfie_url": "https://cdn.example/rider.jpg",
        "registered_vehicle_number": "UP72AB1234",
        "bike_info": "Black Hero Splendor",
    }
    assert "phone" not in identity
    assert "aadhaar_document_key" not in identity
    assert "bank_account_number" not in identity


def test_unknown_delivery_partner_cannot_self_register():
    with pytest.raises(HTTPException) as exc:
        ensure_role_can_register("delivery_partner", existing_user=None)
    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail.lower()


def test_unknown_restaurant_owner_cannot_self_register():
    with pytest.raises(HTTPException) as exc:
        ensure_role_can_register("restaurant_owner", existing_user=None)
    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail.lower()


def test_preprovisioned_delivery_partner_can_login():
    user = SimpleNamespace(role="delivery_partner", is_active=True)
    ensure_role_can_register("delivery_partner", existing_user=user)
