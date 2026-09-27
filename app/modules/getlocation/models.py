# backend/app/modules/getlocation/models.py
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func

from app.core.database import Base


class DeliveryLocationLog(Base):
    """
    Every GPS fix a delivery partner's device sends us.

    Written on: order accept (one-shot fix) and the periodic pings while an
    order is picked up. Free — no Google call is made for any of these.
    """
    __tablename__ = "delivery_location_logs"

    id = Column(Integer, primary_key=True)
    delivery_partner_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id = Column(
        Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)
    accuracy_m = Column(Float, nullable=True)
    source = Column(String(20), nullable=False, default="ping")  # accept | pickup_ping | ping
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
