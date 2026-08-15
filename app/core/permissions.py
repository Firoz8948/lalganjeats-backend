from fastapi import Depends, HTTPException, status
from app.core.security import get_current_user
from app.shared.enums import UserRole

def require_role(*roles: UserRole):
    """
    Use on any endpoint to restrict access
    
    @router.get("/delivery/dashboard")
    async def dashboard(user = Depends(require_role(UserRole.DELIVERY_PARTNER))):
        ...
    """
    def role_checker(current_user = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(r.value for r in roles)}"
            )
        return current_user
    return role_checker


# Shortcuts
require_customer  = require_role(UserRole.CUSTOMER)
require_delivery  = require_role(UserRole.DELIVERY_PARTNER)
require_hotel     = require_role(UserRole.HOTEL_PARTNER)
require_admin     = require_role(UserRole.ADMIN)
