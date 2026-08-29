# backend/app/modules/payments/router.py
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.razorpay_service import (
    create_fund_account,
    create_linked_account,
    create_order,
    create_payout,
    razorpay_configured,
    transfer_to_linked_account,
    verify_payment_signature,
    verify_webhook_signature,
)
from app.core.security import (
    get_current_user,
    get_delivery_partner,
    get_restaurant_owner,
    get_admin,
)
from app.modules.orders.models import Order
from app.modules.payments.models import (
    BankAccount,
    DeliveryEarning,
    PaymentSettings,
    RestaurantEarning,
    Withdrawal,
)
from app.modules.payments.payment_split import calculate_split
from app.modules.payments.schemas import (
    BankAccountCreate,
    BankAccountResponse,
    EarningsSummary,
    PaymentSettingsResponse,
    PaymentSettingsUpdate,
    PaymentVerify,
    RazorpayOrderCreate,
    RazorpayOrderResponse,
    SplitPreview,
    WithdrawalRequest,
    WithdrawalResponse,
)
from app.modules.payments.service import (
    ensure_payment_settings,
    initial_earning_status,
    order_display_actual_totals,
)
from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payment", tags=["Payment"])


def process_payment_split(order_id: int) -> None:
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return

        pay_settings = ensure_payment_settings(db)
        display_total, actual_total = order_display_actual_totals(order)
        split = calculate_split(
            display_total,
            actual_total,
            pay_settings,
            delivery_charge=float(order.delivery_fee or 0),
        )

        order.display_total = split.display_total
        order.actual_total = split.actual_price_total
        order.platform_fee = split.platform_fee
        order.admin_earning = split.admin_earning
        order.delivery_fee = split.delivery_charge
        order.total_amount = split.customer_pays

        restaurant = order.restaurant
        if not restaurant:
            db.commit()
            return

        existing_hotel = (
            db.query(RestaurantEarning)
            .filter(RestaurantEarning.order_id == order_id)
            .first()
        )
        if not existing_hotel:
            hotel_bank = (
                db.query(BankAccount)
                .filter(
                    BankAccount.user_id == restaurant.owner_id,
                    BankAccount.is_primary == True,
                )
                .first()
            )
            transfer_id = None
            status = initial_earning_status()
            settled_at = None
            if (
                hotel_bank
                and hotel_bank.razorpay_linked_account_id
                and order.razorpay_payment_id
                and razorpay_configured()
            ):
                try:
                    transfer = transfer_to_linked_account(
                        payment_id=order.razorpay_payment_id,
                        linked_account_id=hotel_bank.razorpay_linked_account_id,
                        amount_rupees=split.hotel_earning,
                        notes={"order_id": str(order_id), "type": "hotel_earning"},
                    )
                    transfer_id = transfer["items"][0]["id"]
                    status = "settled"
                    settled_at = datetime.now(timezone.utc)
                except Exception as exc:
                    logger.exception("Hotel transfer failed: %s", exc)
                    status = "failed"

            db.add(
                RestaurantEarning(
                    restaurant_id=restaurant.id,
                    order_id=order_id,
                    display_price_total=split.display_total,
                    actual_price_total=split.actual_price_total,
                    platform_fee=split.platform_fee,
                    amount_earned=split.hotel_earning,
                    transfer_status=status,
                    razorpay_transfer_id=transfer_id,
                    settled_at=settled_at,
                )
            )

        if order.delivery_partner_id:
            existing_delivery = (
                db.query(DeliveryEarning)
                .filter(DeliveryEarning.order_id == order_id)
                .first()
            )
            if not existing_delivery:
                delivery_bank = (
                    db.query(BankAccount)
                    .filter(
                        BankAccount.user_id == order.delivery_partner_id,
                        BankAccount.is_primary == True,
                    )
                    .first()
                )
                transfer_id = None
                status = initial_earning_status()
                settled_at = None
                if (
                    delivery_bank
                    and delivery_bank.razorpay_linked_account_id
                    and order.razorpay_payment_id
                    and razorpay_configured()
                ):
                    try:
                        transfer = transfer_to_linked_account(
                            payment_id=order.razorpay_payment_id,
                            linked_account_id=delivery_bank.razorpay_linked_account_id,
                            amount_rupees=split.delivery_earning,
                            notes={"order_id": str(order_id), "type": "delivery_earning"},
                        )
                        transfer_id = transfer["items"][0]["id"]
                        status = "settled"
                        settled_at = datetime.now(timezone.utc)
                    except Exception as exc:
                        logger.exception("Delivery transfer failed: %s", exc)
                        status = "failed"

                db.add(
                    DeliveryEarning(
                        delivery_partner_id=order.delivery_partner_id,
                        order_id=order_id,
                        amount_earned=split.delivery_earning,
                        transfer_status=status,
                        razorpay_transfer_id=transfer_id,
                        settled_at=settled_at,
                    )
                )

        db.commit()
    finally:
        db.close()


@router.get("/settings", response_model=PaymentSettingsResponse)
def get_payment_settings(
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return ensure_payment_settings(db)


@router.put("/settings", response_model=PaymentSettingsResponse)
def update_payment_settings(
    body: PaymentSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    s = ensure_payment_settings(db)
    s.platform_fee_percent = body.platform_fee_percent
    s.platform_charge_rupees = body.platform_charge_rupees
    s.display_price_markup_percent = body.display_price_markup_percent
    s.allow_prepaid_orders = body.allow_prepaid_orders
    s.allow_cod_orders = body.allow_cod_orders
    s.cod_max_order_amount = body.cod_max_order_amount
    db.commit()
    db.refresh(s)
    return s


@router.get("/settings/public", response_model=PaymentSettingsResponse)
def get_public_payment_settings(db: Session = Depends(get_db)):
    return ensure_payment_settings(db)


@router.post("/split-preview", response_model=SplitPreview)
def preview_split(
    display_total: float = Query(..., ge=0),
    actual_total: float = Query(..., ge=0),
    delivery_charge: float = Query(..., ge=0),
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    s = ensure_payment_settings(db)
    result = calculate_split(
        display_total,
        actual_total,
        s,
        delivery_charge=delivery_charge,
    )
    return SplitPreview(**result.__dict__)


@router.post("/create-order", response_model=RazorpayOrderResponse)
def create_razorpay_order(
    body: RazorpayOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not razorpay_configured():
        raise HTTPException(status_code=503, detail="Payment gateway not configured")

    order = db.query(Order).filter(Order.id == body.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")

    pay_settings = ensure_payment_settings(db)
    display_total, actual_total = order_display_actual_totals(order)
    split = calculate_split(
        display_total,
        actual_total,
        pay_settings,
        delivery_charge=float(order.delivery_fee or 0),
    )

    rz_order = create_order(
        amount_rupees=split.customer_pays,
        receipt=f"order_{order.id}",
        notes={"order_id": str(order.id)},
    )

    order.razorpay_order_id = rz_order["id"]
    order.display_total = split.display_total
    order.actual_total = split.actual_price_total
    order.platform_fee = split.platform_fee
    order.admin_earning = split.admin_earning
    order.delivery_fee = split.delivery_charge
    order.total_amount = split.customer_pays
    db.commit()

    return {
        "razorpay_order_id": rz_order["id"],
        "amount": split.customer_pays,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
    }


class PayUInitiateBody(BaseModel):
    order_id: int


@router.post("/payu/initiate")
def payu_initiate(
    body: PayUInitiateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return PayU hosted-checkout form fields for an unpaid prepaid order."""
    from uuid import uuid4

    from app.core.payu_service import (
        build_checkout_payload,
        payu_configured,
        payu_payment_url,
    )

    if not payu_configured():
        raise HTTPException(503, "PayU is not configured")

    order = db.query(Order).filter(Order.id == body.order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.customer_id != current_user.id:
        raise HTTPException(403, "Not your order")
    if order.payment_method != "online":
        raise HTTPException(400, "Order is not a prepaid online order")
    if (order.payment_status or "").lower() == "paid":
        raise HTTPException(400, "Order is already paid")

    # Charge what the customer owes (food + delivery + platform − discount).
    # Do NOT use display_total — that is food subtotal only.
    amount = float(order.total_amount or 0)
    if amount <= 0:
        raise HTTPException(400, "Invalid order amount")

    txnid = (order.payu_txnid or "").strip()
    if not txnid:
        txnid = f"LE{order.id}{uuid4().hex[:10]}".upper()[:40]
        order.payu_txnid = txnid
        db.commit()

    api_base = (settings.API_PUBLIC_URL or "").rstrip("/")
    if not api_base:
        raise HTTPException(503, "API_PUBLIC_URL is not configured")

    customer = order.customer
    firstname = (customer.full_name if customer else None) or "Customer"
    email = (customer.email if customer else None) or "noreply@lalganjeats.com"
    phone = (customer.phone if customer else None) or ""

    fields = build_checkout_payload(
        txnid=txnid,
        amount=amount,
        productinfo=f"LalganjEats order {order.order_number}",
        firstname=firstname,
        email=email,
        phone=phone,
        surl=f"{api_base}/api/v1/payment/payu/success",
        furl=f"{api_base}/api/v1/payment/payu/failure",
        udf1=str(order.id),
        udf2=order.order_number,
    )
    return {
        "payment_url": payu_payment_url(),
        "fields": fields,
        "order_id": order.id,
        "order_number": order.order_number,
        "amount": amount,
    }


def _payu_form_dict(form) -> dict:
    return {k: str(v) for k, v in form.items()}


def _mark_order_paid_from_payu(db: Session, params: dict) -> Order | None:
    from app.core import sms as sms_mod
    from app.core.payu_service import verify_response_hash

    if str(params.get("udf3") or "") == "cash_remit":
        return None
    if str(params.get("udf3") or "") == "collect_at_door":
        # Doorstep collection is handled by _mark_collection_paid_from_payu.
        return None

    if not verify_response_hash(params):
        logger.warning("PayU hash mismatch txnid=%s", params.get("txnid"))
        return None

    status = str(params.get("status") or "").lower()
    if status not in ("success", "captured"):
        return None

    txnid = str(params.get("txnid") or "")
    order_id = None
    try:
        order_id = int(params.get("udf1") or 0) or None
    except (TypeError, ValueError):
        order_id = None

    order = None
    if order_id:
        order = db.query(Order).filter(Order.id == order_id).first()
    if not order and txnid:
        order = db.query(Order).filter(Order.payu_txnid == txnid).first()
    if not order:
        return None

    if (order.payment_status or "").lower() == "paid":
        return order

    order.payment_status = "paid"
    order.payment_method = "online"
    order.payu_txnid = txnid or order.payu_txnid
    order.payu_mihpayid = str(params.get("mihpayid") or "") or order.payu_mihpayid
    db.commit()

    restaurant = order.restaurant
    if restaurant:
        hotel_phone = restaurant.phone or (
            restaurant.owner.phone if getattr(restaurant, "owner", None) else None
        )
        if hotel_phone:
            sms_mod.send_order_alert(hotel_phone, order.order_number)

    return order


def _mark_collection_paid_from_payu(db: Session, params: dict) -> Order | None:
    """
    Confirm a PayU-hosted doorstep online collection.
    Called from surl when udf3 == 'collect_at_door'.  We verify the hash,
    stamp `collection_online_paid_at` on the order, and leave the order in
    picked_up status — the DP still needs to hit "Confirm Delivered".
    """
    from datetime import datetime

    from app.core.payu_service import verify_response_hash

    if not verify_response_hash(params):
        logger.warning("PayU collection hash mismatch txnid=%s", params.get("txnid"))
        return None

    status = str(params.get("status") or "").lower()
    if status not in ("success", "captured"):
        return None

    txnid = str(params.get("txnid") or "")
    if not txnid:
        return None

    order = db.query(Order).filter(Order.collection_txnid == txnid).first()
    if not order:
        logger.warning("PayU collection: no order for txnid=%s", txnid)
        return None

    if order.collection_online_paid_at:
        return order  # idempotent

    # Sanity check amount matches what we recorded when initiating.
    try:
        paid_amount = round(float(params.get("amount") or 0), 2)
    except (TypeError, ValueError):
        paid_amount = 0.0
    expected = round(float(order.collection_amount or 0), 2)
    if expected and abs(paid_amount - expected) > 0.05:
        logger.warning(
            "PayU collection amount mismatch txnid=%s expected=%s got=%s",
            txnid, expected, paid_amount,
        )
        return None

    order.collection_online_paid_at = datetime.utcnow()
    order.online_collected = expected or paid_amount
    order.payu_mihpayid = str(params.get("mihpayid") or "") or order.payu_mihpayid
    db.commit()
    return order


@router.post("/payu/success")
async def payu_success(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    from fastapi.responses import HTMLResponse, RedirectResponse

    from app.modules.payments.cash_remittance import mark_remittance_paid

    params = _payu_form_dict(await request.form())
    front = (settings.FRONTEND_URL or "").rstrip("/") or "https://lalganjeats.com"

    if str(params.get("udf3") or "") == "cash_remit":
        remit = mark_remittance_paid(db, params)
        if remit:
            return RedirectResponse(
                f"{front}/deliverypartner/earnings?remit=success&id={remit.id}",
                status_code=303,
            )
        return RedirectResponse(
            f"{front}/deliverypartner/earnings?remit=failed",
            status_code=303,
        )

    if str(params.get("udf3") or "") == "collect_at_door":
        order = _mark_collection_paid_from_payu(db, params)
        # Show a plain HTML confirmation page to the customer's browser.
        if order:
            return HTMLResponse(_collection_result_html(True, order.order_number))
        return HTMLResponse(_collection_result_html(False, params.get("udf2") or ""))

    order = _mark_order_paid_from_payu(db, params)
    if order:
        background_tasks.add_task(process_payment_split, order.id)
        return RedirectResponse(
            f"{front}/checkout/payment-result?status=success"
            f"&order={order.order_number}&id={order.id}",
            status_code=303,
        )
    return RedirectResponse(
        f"{front}/checkout/payment-result?status=failed&reason=verify",
        status_code=303,
    )


@router.post("/payu/failure")
async def payu_failure(
    request: Request,
    db: Session = Depends(get_db),
):
    from fastapi.responses import HTMLResponse, RedirectResponse

    from app.modules.payments.cash_remittance import release_pending_remittance_orders
    from app.modules.payments.models import CashRemittance

    params = _payu_form_dict(await request.form())
    front = (settings.FRONTEND_URL or "").rstrip("/") or "https://lalganjeats.com"

    if str(params.get("udf3") or "") == "cash_remit":
        remit_id = None
        try:
            remit_id = int(params.get("udf1") or 0) or None
        except (TypeError, ValueError):
            remit_id = None
        if remit_id:
            remit = db.query(CashRemittance).filter(CashRemittance.id == remit_id).first()
            if remit:
                release_pending_remittance_orders(db, remit)
        return RedirectResponse(
            f"{front}/deliverypartner/earnings?remit=failed",
            status_code=303,
        )

    if str(params.get("udf3") or "") == "collect_at_door":
        return HTMLResponse(_collection_result_html(False, params.get("udf2") or ""))

    txnid = str(params.get("txnid") or "")
    order_number = str(params.get("udf2") or "")
    q = "status=failed"
    if order_number:
        q += f"&order={order_number}"
    if txnid:
        q += f"&txnid={txnid}"
    return RedirectResponse(f"{front}/checkout/payment-result?{q}", status_code=303)


def _collection_page_html(
    *, order_number: str, amount_str: str, payment_url: str, fields: dict,
) -> str:
    """Auto-submit form to PayU — customer sees a brief 'Redirecting…' page then PayU checkout."""
    hidden = "\n".join(
        f'      <input type="hidden" name="{k}" value="{(v or "").replace(chr(34), "&quot;")}">'
        for k, v in fields.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>LalganjEats · Pay ₹{amount_str}</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; }}
    .wrap {{ min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; text-align: center; }}
    .brand {{ font-weight: 800; color: #dc2626; letter-spacing: 0.02em; margin-bottom: 8px; }}
    h1 {{ font-size: 20px; margin: 8px 0 4px; }}
    p {{ margin: 4px 0; color: #475569; font-size: 14px; }}
    .amount {{ font-size: 32px; font-weight: 800; color: #16a34a; margin: 12px 0; }}
    .spinner {{ width: 36px; height: 36px; border: 4px solid rgba(220,38,38,0.15); border-top-color: #dc2626; border-radius: 50%; animation: spin .9s linear infinite; margin: 12px auto; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    button {{ background: #dc2626; color: #fff; border: none; padding: 12px 22px; border-radius: 10px; font-weight: 700; font-size: 15px; cursor: pointer; margin-top: 16px; }}
    .note {{ font-size: 12px; color: #94a3b8; margin-top: 16px; max-width: 320px; line-height: 1.4; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">LalganjEats</div>
    <h1>Order #{order_number}</h1>
    <p>Pay this amount to the delivery partner</p>
    <div class="amount">₹{amount_str}</div>
    <div class="spinner" aria-hidden="true"></div>
    <p>Redirecting to secure UPI payment…</p>
    <form id="payuForm" method="post" action="{payment_url}">
{hidden}
    </form>
    <button type="button" onclick="document.getElementById('payuForm').submit()">Pay now via UPI / Card</button>
    <div class="note">Powered by PayU. You can pay using Google Pay, PhonePe, Paytm, or any UPI app.</div>
  </div>
  <script>
    setTimeout(function() {{
      try {{ document.getElementById('payuForm').submit(); }} catch(e) {{}}
    }}, 700);
  </script>
</body>
</html>"""


def _collection_result_html(success: bool, order_number: str) -> str:
    color = "#16a34a" if success else "#dc2626"
    icon = "✓" if success else "✕"
    title = "Payment successful" if success else "Payment failed"
    body = (
        "Please show this screen to the delivery partner. Your order is being marked as paid."
        if success
        else "The payment did not go through. Please ask the delivery partner to try again or pay in cash."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>LalganjEats · {title}</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; }}
    .wrap {{ min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px; text-align: center; }}
    .badge {{ width: 84px; height: 84px; border-radius: 50%; background: {color}; color: #fff; font-size: 44px; display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }}
    h1 {{ margin: 8px 0 6px; font-size: 22px; }}
    p {{ margin: 4px 0; color: #475569; font-size: 14px; max-width: 320px; line-height: 1.45; }}
    .ord {{ font-size: 12px; color: #94a3b8; margin-top: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="badge">{icon}</div>
    <h1>{title}</h1>
    <p>{body}</p>
    <div class="ord">{'Order #' + order_number if order_number else ''}</div>
  </div>
</body>
</html>"""


@router.get("/collect/{txnid}")
def render_collection_page(txnid: str, db: Session = Depends(get_db)):
    """
    Public page the customer lands on after scanning the DP's UPI QR.
    Renders an auto-submit form that POSTs the correct PayU payload.
    No auth — the txnid is generated server-side per attempt.
    """
    from fastapi.responses import HTMLResponse

    from app.core.payu_service import (
        build_checkout_payload,
        format_amount,
        payu_configured,
        payu_payment_url,
    )

    if not payu_configured():
        return HTMLResponse(
            "<h1>Online payments are currently unavailable.</h1>",
            status_code=503,
        )

    order = db.query(Order).filter(Order.collection_txnid == txnid).first()
    if not order:
        return HTMLResponse(_collection_result_html(False, ""), status_code=404)
    if order.collection_online_paid_at:
        return HTMLResponse(_collection_result_html(True, order.order_number))

    amount = round(float(order.collection_amount or 0), 2)
    if amount <= 0:
        return HTMLResponse(_collection_result_html(False, order.order_number))

    api_base = (settings.API_PUBLIC_URL or "").rstrip("/")
    if not api_base:
        return HTMLResponse(
            "<h1>API_PUBLIC_URL is not configured.</h1>",
            status_code=503,
        )

    customer = order.customer
    firstname = (customer.full_name if customer else None) or "Customer"
    email = (customer.email if customer else None) or "noreply@lalganjeats.com"
    phone = (customer.phone if customer else None) or ""

    fields = build_checkout_payload(
        txnid=txnid,
        amount=amount,
        productinfo=f"LalganjEats order {order.order_number}",
        firstname=firstname,
        email=email,
        phone=phone,
        surl=f"{api_base}/api/v1/payment/payu/success",
        furl=f"{api_base}/api/v1/payment/payu/failure",
        udf1=str(order.id),
        udf2=order.order_number,
        udf3="collect_at_door",
    )
    html = _collection_page_html(
        order_number=order.order_number,
        amount_str=format_amount(amount),
        payment_url=payu_payment_url(),
        fields=fields,
    )
    return HTMLResponse(html)


@router.get("/payu/success")
@router.get("/payu/failure")
def payu_browser_get():
    """PayU sometimes hits GET; send users to the result page."""
    from fastapi.responses import RedirectResponse

    front = (settings.FRONTEND_URL or "").rstrip("/") or "https://lalganjeats.com"
    return RedirectResponse(f"{front}/checkout/payment-result?status=unknown", status_code=303)


@router.post("/verify")
def verify_payment(
    body: PaymentVerify,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_payment_signature(
        body.razorpay_order_id,
        body.razorpay_payment_id,
        body.razorpay_signature,
    ):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    order = db.query(Order).filter(Order.id == body.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")

    order.payment_status = "paid"
    order.razorpay_payment_id = body.razorpay_payment_id
    # Stay pending until hotel accepts (customer POV).
    db.commit()

    background_tasks.add_task(process_payment_split, order.id)
    return {"message": "Payment verified", "order_id": order.id}


@router.post("/webhook")
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if settings.RAZORPAY_WEBHOOK_SECRET and not verify_webhook_signature(
        payload, signature
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    data = json.loads(payload)
    event = data.get("event")

    if event == "payment.captured":
        payment = data["payload"]["payment"]["entity"]
        order_id = int(payment.get("notes", {}).get("order_id", 0) or 0)
        if order_id:
            db = SessionLocal()
            try:
                order = db.query(Order).filter(Order.id == order_id).first()
                if order and order.payment_status != "paid":
                    order.payment_status = "paid"
                    order.razorpay_payment_id = payment["id"]
                    db.commit()
                    background_tasks.add_task(process_payment_split, order_id)
            finally:
                db.close()

    return {"status": "ok"}


@router.post("/bank-account", response_model=BankAccountResponse)
def add_bank_account(
    body: BankAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("restaurant_owner", "delivery_partner"):
        raise HTTPException(status_code=403, detail="Not allowed")

    linked_account_id = None
    fund_account_id = None
    is_verified = False

    if razorpay_configured():
        try:
            linked = create_linked_account(
                name=body.account_holder_name,
                email=current_user.email or f"{current_user.phone}@lalganj.eats",
                phone=current_user.phone,
                account_number=body.account_number,
                ifsc=body.ifsc_code,
            )
            linked_account_id = linked.get("id")
            fund = create_fund_account(
                linked_account_id=linked_account_id,
                account_holder_name=body.account_holder_name,
                account_number=body.account_number,
                ifsc=body.ifsc_code,
            )
            fund_account_id = fund.get("id")
            is_verified = True
        except Exception as exc:
            logger.warning("Razorpay bank linking failed: %s", exc)

    db.query(BankAccount).filter(
        BankAccount.user_id == current_user.id
    ).update({"is_primary": False})

    bank = BankAccount(
        user_id=current_user.id,
        role=current_user.role,
        account_holder_name=body.account_holder_name,
        account_number=body.account_number,
        ifsc_code=body.ifsc_code.upper(),
        razorpay_linked_account_id=linked_account_id,
        razorpay_fund_account_id=fund_account_id,
        is_verified=is_verified,
        is_primary=True,
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


@router.get("/bank-account", response_model=list[BankAccountResponse])
def get_my_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(BankAccount)
        .filter(BankAccount.user_id == current_user.id)
        .order_by(BankAccount.is_primary.desc(), BankAccount.id.desc())
        .all()
    )


@router.post("/bank-account/admin/{user_id}", response_model=BankAccountResponse)
def admin_add_bank_account(
    user_id: int,
    body: BankAccountCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(BankAccount).filter(
        BankAccount.user_id == user_id
    ).update({"is_primary": False})

    bank = BankAccount(
        user_id=user_id,
        role=user.role,
        account_holder_name=body.account_holder_name,
        account_number=body.account_number,
        ifsc_code=body.ifsc_code.upper(),
        is_primary=True,
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


@router.get("/earnings/restaurant", response_model=EarningsSummary)
def get_restaurant_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_restaurant_owner),
):
    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.owner_id == current_user.id)
        .first()
    )
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    total_earned = (
        db.query(func.sum(RestaurantEarning.amount_earned))
        .filter(
            RestaurantEarning.restaurant_id == restaurant.id,
            RestaurantEarning.transfer_status.in_(
                ["unsettled", "settled", "completed"]
            ),
        )
        .scalar()
        or 0.0
    )
    unsettled_amount = (
        db.query(func.sum(RestaurantEarning.amount_earned))
        .filter(
            RestaurantEarning.restaurant_id == restaurant.id,
            RestaurantEarning.transfer_status == "unsettled",
        )
        .scalar()
        or 0.0
    )
    settled_amount = (
        db.query(func.sum(RestaurantEarning.amount_earned))
        .filter(
            RestaurantEarning.restaurant_id == restaurant.id,
            RestaurantEarning.transfer_status.in_(["settled", "completed"]),
        )
        .scalar()
        or 0.0
    )
    legacy_withdrawable = (
        db.query(func.sum(RestaurantEarning.amount_earned))
        .filter(
            RestaurantEarning.restaurant_id == restaurant.id,
            RestaurantEarning.transfer_status == "completed",
        )
        .scalar()
        or 0.0
    )
    total_withdrawn = (
        db.query(func.sum(Withdrawal.amount))
        .filter(
            Withdrawal.user_id == current_user.id,
            Withdrawal.status == "completed",
        )
        .scalar()
        or 0.0
    )
    return {
        "total_earned": float(total_earned),
        "total_withdrawn": float(total_withdrawn),
        "available_balance": max(
            0.0,
            float(legacy_withdrawable) - float(total_withdrawn),
        ),
        "unsettled_amount": float(unsettled_amount),
        "settled_amount": float(settled_amount),
    }


@router.get("/earnings/delivery", response_model=EarningsSummary)
def get_delivery_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_delivery_partner),
):
    total_earned = (
        db.query(func.sum(DeliveryEarning.amount_earned))
        .filter(
            DeliveryEarning.delivery_partner_id == current_user.id,
            DeliveryEarning.transfer_status.in_(
                ["unsettled", "settled", "completed"]
            ),
        )
        .scalar()
        or 0.0
    )
    unsettled_amount = (
        db.query(func.sum(DeliveryEarning.amount_earned))
        .filter(
            DeliveryEarning.delivery_partner_id == current_user.id,
            DeliveryEarning.transfer_status == "unsettled",
        )
        .scalar()
        or 0.0
    )
    settled_amount = (
        db.query(func.sum(DeliveryEarning.amount_earned))
        .filter(
            DeliveryEarning.delivery_partner_id == current_user.id,
            DeliveryEarning.transfer_status.in_(["settled", "completed"]),
        )
        .scalar()
        or 0.0
    )
    legacy_withdrawable = (
        db.query(func.sum(DeliveryEarning.amount_earned))
        .filter(
            DeliveryEarning.delivery_partner_id == current_user.id,
            DeliveryEarning.transfer_status == "completed",
        )
        .scalar()
        or 0.0
    )
    total_withdrawn = (
        db.query(func.sum(Withdrawal.amount))
        .filter(
            Withdrawal.user_id == current_user.id,
            Withdrawal.status == "completed",
        )
        .scalar()
        or 0.0
    )
    return {
        "total_earned": float(total_earned),
        "total_withdrawn": float(total_withdrawn),
        "available_balance": max(
            0.0,
            float(legacy_withdrawable) - float(total_withdrawn),
        ),
        "unsettled_amount": float(unsettled_amount),
        "settled_amount": float(settled_amount),
    }


@router.post("/withdraw", response_model=WithdrawalResponse)
def request_withdrawal(
    body: WithdrawalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("restaurant_owner", "delivery_partner"):
        raise HTTPException(status_code=403, detail="Not allowed")

    if current_user.role == "restaurant_owner":
        restaurant = (
            db.query(Restaurant)
            .filter(Restaurant.owner_id == current_user.id)
            .first()
        )
        if not restaurant:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        total_earned = (
            db.query(func.sum(RestaurantEarning.amount_earned))
            .filter(
                RestaurantEarning.restaurant_id == restaurant.id,
                RestaurantEarning.transfer_status == "completed",
            )
            .scalar()
            or 0.0
        )
    else:
        total_earned = (
            db.query(func.sum(DeliveryEarning.amount_earned))
            .filter(
                DeliveryEarning.delivery_partner_id == current_user.id,
                DeliveryEarning.transfer_status == "completed",
            )
            .scalar()
            or 0.0
        )

    total_withdrawn = (
        db.query(func.sum(Withdrawal.amount))
        .filter(
            Withdrawal.user_id == current_user.id,
            Withdrawal.status == "completed",
        )
        .scalar()
        or 0.0
    )
    available = float(total_earned) - float(total_withdrawn)

    if body.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: ?{available:.2f}",
        )

    bank = (
        db.query(BankAccount)
        .filter(
            BankAccount.user_id == current_user.id,
            BankAccount.is_primary == True,
        )
        .first()
    )
    if not bank:
        raise HTTPException(status_code=400, detail="No bank account added")

    payout_id = None
    status = "pending"

    if bank.razorpay_fund_account_id and razorpay_configured():
        try:
            payout = create_payout(
                fund_account_id=bank.razorpay_fund_account_id,
                amount_rupees=body.amount,
            )
            payout_id = payout.get("id")
            status = "processing"
        except Exception as exc:
            logger.warning("Payout failed: %s", exc)

    withdrawal = Withdrawal(
        user_id=current_user.id,
        role=current_user.role,
        amount=body.amount,
        status=status,
        razorpay_payout_id=payout_id,
        bank_account_id=str(bank.id),
    )
    db.add(withdrawal)
    db.commit()
    db.refresh(withdrawal)
    return withdrawal


@router.get("/withdraw/history", response_model=list[WithdrawalResponse])
def withdrawal_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Withdrawal)
        .filter(Withdrawal.user_id == current_user.id)
        .order_by(Withdrawal.created_at.desc())
        .all()
    )
