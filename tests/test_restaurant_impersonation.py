from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.modules.admin.services.restaurants import (
    assert_live_impersonation_session,
    end_impersonation_session,
    validate_impersonation_target,
)


def _user(**overrides):
    values = {
        "id": 10,
        "role": "admin",
        "tenant_id": 7,
        "is_active": True,
        "full_name": "City Admin",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _restaurant(**overrides):
    owner = _user(
        id=44,
        role="restaurant_owner",
        tenant_id=7,
        full_name="Hotel Owner",
    )
    values = {
        "id": 22,
        "name": "Hotel A",
        "tenant_id": 7,
        "is_active": True,
        "is_approved": True,
        "owner": owner,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_admin_can_impersonate_active_restaurant_in_own_tenant():
    owner = validate_impersonation_target(_user(), _restaurant())

    assert owner.id == 44
    assert owner.role == "restaurant_owner"


def test_admin_cannot_impersonate_restaurant_from_another_tenant():
    with pytest.raises(HTTPException) as exc:
        validate_impersonation_target(_user(tenant_id=7), _restaurant(tenant_id=9))

    assert exc.value.status_code == 404


def test_admin_cannot_impersonate_inactive_owner():
    restaurant = _restaurant()
    restaurant.owner.is_active = False

    with pytest.raises(HTTPException) as exc:
        validate_impersonation_target(_user(), restaurant)

    assert exc.value.status_code == 400


def test_admin_cannot_impersonate_unapproved_restaurant():
    with pytest.raises(HTTPException) as exc:
        validate_impersonation_target(_user(), _restaurant(is_approved=False))

    assert exc.value.status_code == 400
    assert "not approved" in exc.value.detail.lower()


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeDb:
    def __init__(self, row):
        self._row = row
        self.committed = False

    def query(self, model):
        return _FakeQuery(self._row)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        return obj


def test_assert_live_impersonation_rejects_ended_session():
    now = datetime.now(timezone.utc)
    session = SimpleNamespace(
        jti="abc",
        ended_at=now,
        expires_at=now + timedelta(minutes=20),
        owner_user_id=44,
        restaurant_id=22,
    )
    owner = _user(
        id=44,
        role="restaurant_owner",
        impersonated_by=10,
        impersonation_type="restaurant",
        impersonation_session_id="abc",
        impersonated_restaurant_id=22,
    )
    with pytest.raises(HTTPException) as exc:
        assert_live_impersonation_session(_FakeDb(session), owner)
    assert exc.value.status_code == 401


def test_end_impersonation_session_marks_ended():
    now = datetime.now(timezone.utc)
    session = SimpleNamespace(
        jti="abc",
        ended_at=None,
        expires_at=now + timedelta(minutes=20),
        owner_user_id=44,
        restaurant_id=22,
    )
    owner = _user(
        id=44,
        role="restaurant_owner",
        impersonated_by=10,
        impersonation_type="restaurant",
        impersonation_session_id="abc",
        impersonated_restaurant_id=22,
    )
    db = _FakeDb(session)
    result = end_impersonation_session(db, owner)
    assert result["ok"] is True
    assert session.ended_at is not None
    assert db.committed is True
