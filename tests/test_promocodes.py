"""Promo code discount math: percent, flat, and min cart."""
from decimal import Decimal
from types import SimpleNamespace

from app.modules.promocodes.schemas import PromoValidateRequest
from app.modules.promocodes.service import (
    _compute_discount,
    _format_rupees,
    validate_promo,
)


def _promo(**kwargs):
    defaults = dict(
        id=1,
        code="FLAT50",
        channel="all",
        discount_type="percent",
        percent_off=Decimal("10"),
        flat_off=None,
        min_cart_value=None,
        free_delivery=False,
        is_active=True,
        max_uses=0,
        remaining_uses=0,
        expires_at=None,
        audience="all",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_compute_percent_discount():
    promo = _promo(discount_type="percent", percent_off=Decimal("10"))
    assert _compute_discount(promo, Decimal("200")) == Decimal("20.00")


def test_compute_flat_discount_clamped_to_subtotal():
    promo = _promo(
        discount_type="flat",
        percent_off=None,
        flat_off=Decimal("50"),
    )
    assert _compute_discount(promo, Decimal("200")) == Decimal("50.00")
    assert _compute_discount(promo, Decimal("30")) == Decimal("30.00")


def test_format_rupees():
    assert _format_rupees(129) == "129"
    assert _format_rupees(Decimal("129.50")) == "129.50"


class _FakeRepo:
    def __init__(self, promo):
        self.promo = promo

    def get_by_code(self, db, code, tenant_id):
        if self.promo and self.promo.code == code:
            return self.promo
        return None


def test_validate_min_cart_rejects(monkeypatch):
    from app.modules.promocodes import service as promo_service

    promo = _promo(
        discount_type="flat",
        flat_off=Decimal("50"),
        percent_off=None,
        min_cart_value=Decimal("129"),
    )
    monkeypatch.setattr(promo_service.repo, "get_by_code", _FakeRepo(promo).get_by_code)
    monkeypatch.setattr(promo_service, "_maybe_auto_deactivate", lambda db, p: None)

    result = validate_promo(
        db=SimpleNamespace(commit=lambda: None),
        payload=PromoValidateRequest(
            code="FLAT50",
            client_channel="web",
            subtotal=Decimal("100"),
            delivery_fee=Decimal("20"),
        ),
    )
    assert result.valid is False
    assert result.reason == "min_cart"
    assert "129" in result.message
    assert "above" in result.message.lower()


def test_validate_flat_applies_when_cart_ok(monkeypatch):
    from app.modules.promocodes import service as promo_service

    promo = _promo(
        discount_type="flat",
        flat_off=Decimal("50"),
        percent_off=None,
        min_cart_value=Decimal("129"),
    )
    monkeypatch.setattr(promo_service.repo, "get_by_code", _FakeRepo(promo).get_by_code)
    monkeypatch.setattr(promo_service, "_maybe_auto_deactivate", lambda db, p: None)

    result = validate_promo(
        db=SimpleNamespace(commit=lambda: None),
        payload=PromoValidateRequest(
            code="FLAT50",
            client_channel="web",
            subtotal=Decimal("200"),
            delivery_fee=Decimal("20"),
        ),
    )
    assert result.valid is True
    assert result.discount_amount == Decimal("50.00")
    assert result.discount_type == "flat"


def test_validate_rejects_repeat_use_same_mobile(monkeypatch):
    from app.modules.promocodes import service as promo_service

    promo = _promo(code="LALGANJ39", audience="all")
    monkeypatch.setattr(promo_service.repo, "get_by_code", _FakeRepo(promo).get_by_code)
    monkeypatch.setattr(promo_service, "_maybe_auto_deactivate", lambda db, p: None)
    monkeypatch.setattr(promo_service, "_has_used_promo", lambda *a, **k: True)

    user = SimpleNamespace(id=54, phone="9876543210")
    result = validate_promo(
        db=SimpleNamespace(commit=lambda: None),
        payload=PromoValidateRequest(code="LALGANJ39", client_channel="web"),
        current_user=user,
    )
    assert result.valid is False
    assert result.reason == "one_time"
    assert result.message == "APPLICABLE FOR ONE TIME ONLY"


def test_validate_rejects_existing_customer_for_new_users(monkeypatch):
    from app.modules.promocodes import service as promo_service

    promo = _promo(code="WELCOME", audience="new_users")
    monkeypatch.setattr(promo_service.repo, "get_by_code", _FakeRepo(promo).get_by_code)
    monkeypatch.setattr(promo_service, "_maybe_auto_deactivate", lambda db, p: None)
    monkeypatch.setattr(promo_service, "_has_used_promo", lambda *a, **k: False)
    monkeypatch.setattr(promo_service, "_is_new_customer", lambda *a, **k: False)
    monkeypatch.setattr(promo_service, "_device_used_new_user_coupon", lambda *a, **k: False)

    user = SimpleNamespace(id=54, phone="9876543210")
    result = validate_promo(
        db=SimpleNamespace(commit=lambda: None),
        payload=PromoValidateRequest(code="WELCOME", client_channel="web"),
        current_user=user,
    )
    assert result.valid is False
    assert result.reason == "new_users"
    assert result.message == "APPLICABLE FOR NEW USERS"


def test_list_public_hides_new_user_coupon_when_not_eligible(monkeypatch):
    from app.modules.promocodes import service as promo_service

    welcome = _promo(
        code="100LALGANJ",
        audience="new_users",
        is_public=True,
        description="New users",
    )
    everyday = _promo(
        code="SAVE10",
        audience="all",
        is_public=True,
        description="Everyone",
    )
    monkeypatch.setattr(
        promo_service.repo,
        "list_public_active",
        lambda db, tenant_id=None: [welcome, everyday],
    )
    monkeypatch.setattr(promo_service, "_maybe_auto_deactivate", lambda db, p: None)
    monkeypatch.setattr(promo_service, "_is_expired", lambda p: False)
    monkeypatch.setattr(
        promo_service,
        "_eligibility_error",
        lambda db, promo, user, exclude_order_id=None, device_id=None: (
            SimpleNamespace(reason="new_users")
            if promo.code == "100LALGANJ"
            else None
        ),
    )

    rows = promo_service.list_public_active_promos(
        db=SimpleNamespace(commit=lambda: None),
        current_user=SimpleNamespace(id=9, phone="9999999999"),
    )
    assert [row["code"] for row in rows] == ["SAVE10"]


def test_validate_rejects_new_user_coupon_on_same_device(monkeypatch):
    from app.modules.promocodes import service as promo_service
    from app.modules.promocodes.schemas import PromoValidateRequest as Req

    promo = _promo(code="100LALGANJ", audience="new_users")
    monkeypatch.setattr(promo_service.repo, "get_by_code", _FakeRepo(promo).get_by_code)
    monkeypatch.setattr(promo_service, "_maybe_auto_deactivate", lambda db, p: None)
    monkeypatch.setattr(promo_service, "_has_used_promo", lambda *a, **k: False)
    monkeypatch.setattr(promo_service, "_is_new_customer", lambda *a, **k: True)
    monkeypatch.setattr(promo_service, "_device_used_new_user_coupon", lambda *a, **k: True)

    result = validate_promo(
        db=SimpleNamespace(commit=lambda: None),
        payload=Req(
            code="100LALGANJ",
            client_channel="web",
            device_id="device-abc-123",
        ),
        current_user=SimpleNamespace(id=88, phone="1111111111"),
    )
    assert result.valid is False
    assert result.reason == "device_used"
    assert result.message.lower() == "this mobile has already used this coupon code"
