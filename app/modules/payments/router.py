# backend/app/modules/payments/router.py
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
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
    order.status = "confirmed"
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
                    order.status = "confirmed"
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
