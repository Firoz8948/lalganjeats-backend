# backend/app/modules/admin/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ImpersonationSession(Base):
    """Audited short-lived admin impersonation session."""

    __tablename__ = "impersonation_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    admin_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    restaurant_id = Column(
        Integer,
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purpose = Column(String(40), nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
