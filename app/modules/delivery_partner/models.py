from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DeliveryPartnerDetails(Base):
    """Admin-managed identity and vehicle details for a delivery partner."""

    __tablename__ = "delivery_partner_details"
    __table_args__ = (
        UniqueConstraint(
            "registered_vehicle_number",
            name="uq_delivery_partner_vehicle_number",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    bank_account_id = Column(
        Integer,
        ForeignKey("bank_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    date_of_birth = Column(Date, nullable=False)
    address = Column(Text, nullable=False)
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)
    joining_date = Column(Date, nullable=False)

    registered_vehicle_number = Column(String(24), nullable=False)
    bike_info = Column(Text, nullable=False)
    selfie_url = Column(Text, nullable=False)

    rc_document_key = Column(Text, nullable=True)
    aadhaar_document_key = Column(Text, nullable=True)
    pan_document_key = Column(Text, nullable=True)
    bank_passbook_document_key = Column(Text, nullable=True)
    bank_name = Column(String(150), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="delivery_partner_details")
    bank_account = relationship("BankAccount", foreign_keys=[bank_account_id])
