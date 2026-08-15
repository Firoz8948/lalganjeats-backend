from sqlalchemy.orm import Session

from app.modules.users.models import User


def get_all_customers(db: Session):
    customers = db.query(User).filter(
        User.role == "customer"
    ).order_by(User.created_at.desc()).all()
    return [
        {
            "id": customer.id,
            "full_name": customer.full_name,
            "phone": customer.phone,
            "email": customer.email,
            "is_active": customer.is_active,
            "created_at": (
                customer.created_at.isoformat()
                if customer.created_at
                else None
            ),
        }
        for customer in customers
    ]
