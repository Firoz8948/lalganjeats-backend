# backend/app/core/razorpay_service.py
import hashlib
import hmac
from typing import Optional

from app.core.config import settings

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    import razorpay

    _client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    return _client


def razorpay_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_order(amount_rupees: float, receipt: str, notes: dict | None = None) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("Razorpay is not configured")
    return client.order.create({
        "amount": int(round(amount_rupees * 100)),
        "currency": "INR",
        "receipt": receipt,
        "notes": notes or {},
    })


def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    if not settings.RAZORPAY_KEY_SECRET:
        return False
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_linked_account(
    name: str,
    email: str,
    phone: str,
    account_number: str,
    ifsc: str,
    business_type: str = "individual",
) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("Razorpay is not configured")
    return client.account.create({
        "email": email,
        "profile": {
            "category": "food",
            "subcategory": "food_court",
            "addresses": {
                "registered": {
                    "street1": "Lalganj",
                    "city": "Lalganj",
                    "state": "Uttar Pradesh",
                    "postal_code": "229001",
                    "country": "IN",
                }
            },
        },
        "legal_business_name": name,
        "business_type": business_type,
        "legal_info": {"pan": "AAAPL1234C"},
        "contact_name": name,
        "phone": phone,
        "type": "route",
    })


def create_fund_account(
    linked_account_id: str,
    account_holder_name: str,
    account_number: str,
    ifsc: str,
) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("Razorpay is not configured")
    return client.fund_account.create({
        "account_type": "bank_account",
        "bank_account": {
            "name": account_holder_name,
            "ifsc": ifsc,
            "account_number": account_number,
        },
        "contact_id": linked_account_id,
    })


def transfer_to_linked_account(
    payment_id: str,
    linked_account_id: str,
    amount_rupees: float,
    notes: dict | None = None,
) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("Razorpay is not configured")
    return client.payment.transfer(payment_id, {
        "transfers": [{
            "account": linked_account_id,
            "amount": int(round(amount_rupees * 100)),
            "currency": "INR",
            "notes": notes or {},
            "on_hold": 0,
        }]
    })


def create_payout(
    fund_account_id: str,
    amount_rupees: float,
    purpose: str = "payout",
    narration: str = "LalganjEats Withdrawal",
) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("Razorpay is not configured")
    return client.payout.create({
        "account_number": settings.RAZORPAY_ACCOUNT_NUMBER,
        "fund_account_id": fund_account_id,
        "amount": int(round(amount_rupees * 100)),
        "currency": "INR",
        "mode": "IMPS",
        "purpose": purpose,
        "queue_if_low_balance": True,
        "narration": narration,
    })
