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
