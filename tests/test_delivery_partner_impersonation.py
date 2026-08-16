from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.admin.services import settlements


def _admin(**overrides):
    values = {
        "id": 10,
        "role": "admin",
        "tenant_id": 7,
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _partner(**overrides):
    values = {
        "id": 44,
        "role": "delivery_partner",
        "tenant_id": 7,
        "is_active": True,
        "full_name": "Delivery Partner",
        "phone": "9999999999",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_delivery_impersonation_validator_is_available():
    assert callable(getattr(settlements, "validate_delivery_impersonation_target", None))


def test_admin_can_impersonate_active_delivery_partner_in_own_tenant():
    validator = settlements.validate_delivery_impersonation_target
    partner = validator(_admin(), _partner())
    assert partner.id == 44


def test_admin_cannot_impersonate_delivery_partner_from_another_tenant():
    validator = settlements.validate_delivery_impersonation_target
    with pytest.raises(HTTPException) as exc:
        validator(_admin(tenant_id=7), _partner(tenant_id=9))
    assert exc.value.status_code == 404


def test_admin_cannot_impersonate_inactive_delivery_partner():
    validator = settlements.validate_delivery_impersonation_target
    with pytest.raises(HTTPException) as exc:
        validator(_admin(), _partner(is_active=False))
    assert exc.value.status_code == 400
