# backend/app/modules/hotel_portal/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from app.core.database import get_db
from app.core.security import get_restaurant_owner
from app.modules.restaurants.models import Restaurant, MenuItem, MenuCategory
from app.modules.orders.models import Order
from app.modules.orders.status_meta import (
    HOTEL_SETTABLE_STATUSES,
    customer_status_meta,
)

router = APIRouter(prefix="/api/v1/hotel-portal", tags=["Hotel Portal"])


# ─── Helpers ───────────────────────────────────────────────
def _serialize_order(o: Order) -> dict:
    from app.modules.delivery_partner.service import serialize_public_identity

    partner = o.delivery_partner
    partner_public = serialize_public_identity(partner)
    bike = None
    bike_name = None
    if partner_public:
        bike = partner_public.get("registered_vehicle_number")
        bike_name = partner_public.get("bike_info")
    restaurant_name = o.restaurant.name if o.restaurant else None

    # Hotel sees ONLY seller transfer prices
    items_list = []
    items_seller_sum = 0.0
    for i in o.items:
        p = float(i.actual_price) if i.actual_price is not None else float(i.price)
        items_seller_sum += p * i.quantity
        items_list.append({
            "name":     i.name,
            "quantity": i.quantity,
            "price":    p,
        })

    seller_total = items_seller_sum if items_seller_sum > 0 else (
        float(o.actual_total) if o.actual_total is not None else float(o.total_amount)
    )

    return {
        "id":               o.id,
        "order_number":     o.order_number,
        "status":           o.status,
        "status_meta":      customer_status_meta(
            o.status,
            restaurant_name=restaurant_name,
            delivery_partner_name=partner.full_name if partner else None,
            bike_number=bike,
            bike_name=bike_name,
        ),
        "total_amount":     seller_total,
        "payment_method":   o.payment_method,
        "payment_status":   o.payment_status,
        "customer":         o.customer.full_name if o.customer else None,
        "delivery_address": o.delivery_address,
        "delivery_partner": partner_public,
        "created_at":       o.created_at.isoformat(),
        "items":            items_list,
    }


def _get_restaurant(db: Session, owner) -> Restaurant:
    from app.modules.admin.services.restaurants import assert_live_impersonation_session

    assert_live_impersonation_session(db, owner)
    selected_id = getattr(owner, "impersonated_restaurant_id", None)
    if selected_id is not None:
        r = db.query(Restaurant).filter(Restaurant.id == int(selected_id)).first()
        if r:
            return r

    r = db.query(Restaurant).filter(Restaurant.owner_id == owner.id).first()
    if not r and getattr(owner, "role", "") in ("admin", "super_admin"):
        tenant_id = getattr(owner, "tenant_id", 1) or 1
        r = db.query(Restaurant).filter(Restaurant.tenant_id == tenant_id, Restaurant.is_active == True).first()
        if not r:
            r = db.query(Restaurant).first()

    if not r:
        raise HTTPException(404, "Restaurant not found")
    return r


# ── Dashboard ──────────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)

    total_orders   = db.query(Order).filter(
                        Order.restaurant_id == restaurant.id).count()
    pending_orders = db.query(Order).filter(
                        Order.restaurant_id == restaurant.id,
                        Order.status == "pending",
                        or_(
                            Order.payment_method != "online",
                            Order.payment_status == "paid",
                        ),
                    ).count()
    active_orders  = db.query(Order).filter(
                        Order.restaurant_id == restaurant.id,
                        Order.status.in_(["accepted", "ready"])).count()

    picked_up_or_delivered_orders = db.query(Order).filter(
        Order.restaurant_id == restaurant.id,
        Order.status.in_(["picked_up", "delivered"])
    ).all()
    def _seller_order_total(o: Order) -> float:
        items_sum = sum(
            (float(i.actual_price) if i.actual_price is not None else float(i.price)) * i.quantity
            for i in o.items
        )
        if items_sum > 0:
            return items_sum
        return float(o.actual_total) if o.actual_total is not None else float(o.total_amount or 0)

    total_revenue = sum(_seller_order_total(o) for o in picked_up_or_delivered_orders)

    recent_orders = db.query(Order).filter(
        Order.restaurant_id == restaurant.id
    ).order_by(Order.created_at.desc()).limit(10).all()

    return {
        "restaurant": {
            "id":          restaurant.id,
            "name":        restaurant.name,
            "is_open":     restaurant.is_open,
            "is_approved": restaurant.is_approved,
            "phone":       restaurant.phone or "",
            "address":     restaurant.address or "",
        },
        "stats": {
            "total_orders":   total_orders,
            "pending_orders": pending_orders,
            "active_orders":  active_orders,
            "total_revenue":  total_revenue,
        },
        "recent_orders": [_serialize_order(o) for o in recent_orders],
    }


# ── Toggle Open/Closed ─────────────────────────────────────
@router.patch("/toggle-status")
def toggle_open_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    restaurant.is_open = not restaurant.is_open
    db.commit()
    return {"is_open": restaurant.is_open}


# ── Categories ─────────────────────────────────────────────
class CategoryReorderPayload(BaseModel):
    category_ids: List[int]


@router.get("/categories")
def get_categories(
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    cats = db.query(MenuCategory).filter(
        MenuCategory.restaurant_id == restaurant.id,
        MenuCategory.is_active == True
    ).order_by(MenuCategory.sort_order, MenuCategory.id).all()
    return [{"id": c.id, "name": c.name, "sort_order": c.sort_order} for c in cats]


@router.put("/categories/reorder")
def reorder_categories(
    payload: CategoryReorderPayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    for index, cat_id in enumerate(payload.category_ids):
        db.query(MenuCategory).filter(
            MenuCategory.id == cat_id,
            MenuCategory.restaurant_id == restaurant.id
        ).update({"sort_order": index})
    db.commit()
    return {"message": "Category order updated successfully"}


# ── Menu Items ─────────────────────────────────────────────
class MenuItemCreate(BaseModel):
    name:           str
    description:    Optional[str] = None
    price:          float
    original_price: Optional[float] = None
    is_veg:         bool = True
    is_available:   bool = True
    is_bestseller:  bool = False
    category_id:    Optional[int] = None


class MenuItemUpdate(BaseModel):
    name:           Optional[str] = None
    description:    Optional[str] = None
    price:          Optional[float] = None
    original_price: Optional[float] = None
    is_veg:         Optional[bool] = None
    is_available:   Optional[bool] = None
    is_bestseller:  Optional[bool] = None
    category_id:    Optional[int] = None


@router.get("/menu")
def get_menu(
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    items = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant.id,
        MenuItem.is_deleted == False
    ).order_by(MenuItem.sort_order).all()

    return [
        {
            "id":             i.id,
            "name":           i.name,
            "description":    i.description,
            "price":          float(i.price),
            "actual_price":   float(i.actual_price) if i.actual_price is not None else None,
            "original_price": float(i.original_price) if i.original_price else None,
            "is_veg":         i.is_veg,
            "is_available":   i.is_available,
            "is_bestseller":  i.is_bestseller,
            "category_id":    i.category_id,
            "image_url":      i.image_url,
        }
        for i in items
    ]


@router.post("/menu")
def add_menu_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)

    item = MenuItem(
        restaurant_id  = restaurant.id,
        category_id    = payload.category_id,
        name           = payload.name,
        description    = payload.description,
        price          = Decimal(str(payload.price)),
        original_price = Decimal(str(payload.original_price))
                         if payload.original_price else None,
        is_veg         = payload.is_veg,
        is_available   = payload.is_available,
        is_bestseller  = payload.is_bestseller,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"message": "Menu item added", "id": item.id}


@router.put("/menu/{item_id}")
def update_menu_item(
    item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant.id,
        MenuItem.is_deleted == False
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")

    if payload.name           is not None: item.name           = payload.name
    if payload.description    is not None: item.description    = payload.description
    if payload.is_veg         is not None: item.is_veg         = payload.is_veg
    if payload.is_available   is not None: item.is_available   = payload.is_available
    if payload.is_bestseller  is not None: item.is_bestseller  = payload.is_bestseller
    if payload.category_id    is not None: item.category_id    = payload.category_id
    if payload.price          is not None:
        item.price = Decimal(str(payload.price))
    if payload.original_price is not None:
        item.original_price = Decimal(str(payload.original_price))

    db.commit()
    return {"message": "Updated"}


@router.delete("/menu/{item_id}")
def delete_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    item.is_deleted = True
    db.commit()
    return {"message": "Deleted"}


@router.patch("/menu/{item_id}/toggle-availability")
def toggle_availability(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    item.is_available = not item.is_available
    db.commit()
    return {"is_available": item.is_available}


# ── Orders ─────────────────────────────────────────────────
@router.get("/orders")
def get_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)

    query = db.query(Order).filter(Order.restaurant_id == restaurant.id)

    if status == "active":
        query = query.filter(
            Order.status.in_(["accepted", "ready", "picked_up"])
        )
    elif status == "history":
        query = query.filter(Order.status == "delivered")
    elif status == "delivered":
        query = query.filter(Order.status == "delivered")
    elif status == "cancelled":
        query = query.filter(Order.status == "cancelled")
    elif status == "pending":
        query = query.filter(
            Order.status == "pending",
            or_(
                Order.payment_method != "online",
                Order.payment_status == "paid",
            ),
        )

    orders = query.order_by(Order.created_at.desc()).all()
    return [_serialize_order(o) for o in orders]


class StatusUpdate(BaseModel):
    status: str


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == restaurant.id
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")

    if payload.status not in HOTEL_SETTABLE_STATUSES:
        raise HTTPException(
            400,
            f"Invalid status. Restaurant can set: {list(HOTEL_SETTABLE_STATUSES)}",
        )

    prev = order.status

    if payload.status == "accepted" and prev != "pending":
        raise HTTPException(400, "Only pending orders can be accepted")
    if payload.status == "ready" and prev not in ("accepted", "ready"):
        raise HTTPException(400, "Order must be accepted before marking ready")

    order.status = payload.status
    db.commit()

    # Broadcast updated tracking to customer WebSocket
    from app.modules.tracking.service import broadcast_order_tracking
    broadcast_order_tracking(db, order.id)

    # Hotel accept → start nearest delivery-partner broadcast dispatch
    if payload.status == "accepted" and prev == "pending":
        from app.modules.delivery.dispatch import start_dispatch
        start_dispatch(order.id)

    return {"status": order.status}


# ── Earnings ───────────────────────────────────────────────
@router.get("/earnings")
def get_earnings(
    filter: str = "today",
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)

    query = db.query(Order).filter(
        Order.restaurant_id == restaurant.id,
        Order.status.in_(["picked_up", "delivered"])
    )

    now = datetime.now(timezone.utc)

    if filter == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Order.created_at >= start)
    elif filter == "week":
        start = now - timedelta(days=7)
        query = query.filter(Order.created_at >= start)
    elif filter == "month":
        start = now - timedelta(days=30)
        query = query.filter(Order.created_at >= start)
    # "all" — no date filter

    orders = query.order_by(Order.created_at.desc()).all()

    def _order_seller_amount(o: Order) -> float:
        items_sum = sum(
            (float(i.actual_price) if i.actual_price is not None else float(i.price)) * i.quantity
            for i in o.items
        )
        if items_sum > 0:
            return items_sum
        return float(o.actual_total) if o.actual_total is not None else float(o.total_amount or 0)

    total_earned = sum(_order_seller_amount(o) for o in orders)
    unsettled_amount = sum(
        _order_seller_amount(o) for o in orders
        if not (o.restaurant_earning and o.restaurant_earning.transfer_status in ("completed", "settled"))
    )
    settled_amount = sum(
        _order_seller_amount(o) for o in orders
        if (o.restaurant_earning and o.restaurant_earning.transfer_status in ("completed", "settled"))
    )

    return {
        "filter":           filter,
        "total_orders":     len(orders),
        "total_earned":     total_earned,
        "unsettled_amount": unsettled_amount,
        "settled_amount":   settled_amount,
        "orders": [
            {
                "id":           o.id,
                "order_number": o.order_number,
                "customer":     o.customer.full_name if o.customer else "—",
                "total_amount": _order_seller_amount(o),
                "is_settled":   bool(o.restaurant_earning and o.restaurant_earning.transfer_status in ("completed", "settled")),
                "delivered_at": o.updated_at.isoformat()
                                if o.updated_at else o.created_at.isoformat(),
            }
            for o in orders
        ],
    }


# ── Settings ───────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    restaurant_name:     Optional[str]   = None
    phone:               Optional[str]   = None
    address:             Optional[str]   = None
    min_order_amount:    Optional[float] = None
    delivery_fee:        Optional[float] = None
    free_delivery_above: Optional[float] = None
    notif_new_order:     Optional[bool]  = None


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)
    return {
        "restaurant_name":     restaurant.name,
        "phone":               restaurant.phone or "",
        "address":             restaurant.address or "",
        "min_order_amount":    0,
        "delivery_fee":        0,
        "free_delivery_above": 0,
        "notif_new_order":     True,
    }


@router.put("/settings")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    restaurant = _get_restaurant(db, current_user)

    if payload.restaurant_name is not None:
        restaurant.name = payload.restaurant_name
        from app.modules.restaurants.service import assign_restaurant_slug

        assign_restaurant_slug(
            db, restaurant, name=payload.restaurant_name, force=True
        )
    if payload.phone is not None:
        restaurant.phone = payload.phone
    if payload.address is not None:
        restaurant.address = payload.address

    db.commit()
    return {"message": "Settings saved"}


class FcmTokenUpdate(BaseModel):
    fcm_token: str


@router.post("/fcm-token")
def update_fcm_token(
    payload: FcmTokenUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_restaurant_owner)
):
    current_user.fcm_token = payload.fcm_token.strip()
    db.commit()
    return {"status": "ok"}
