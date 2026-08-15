# backend/app/modules/websocket/auth.py
"""Authenticate WebSocket clients via JWT query param."""
from __future__ import annotations

from fastapi import WebSocket, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.users.models import User


def user_from_token(db: Session, token: str) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return (
            db.query(User)
            .filter(User.id == int(user_id), User.is_active == True)
            .first()
        )
    except (JWTError, ValueError, TypeError):
        return None


async def reject(websocket: WebSocket, code: int = status.WS_1008_POLICY_VIOLATION) -> None:
    await websocket.close(code=code)
