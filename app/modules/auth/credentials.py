# backend/app/modules/auth/credentials.py
"""Set hashed partner login credentials (restaurant owner / delivery partner)."""
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.users.models import User

_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,80}$")


def normalize_username(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def apply_partner_credentials(
    db: Session,
    user: User,
    *,
    username: str | None = None,
    password: str | None = None,
) -> None:
    """Update username and/or password_hash. Empty password is ignored (keep existing)."""
    if username is not None:
        uname = normalize_username(username)
        if uname is None:
            user.username = None
        else:
            if not _USERNAME_RE.match(uname):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Username must be 3–80 chars: lowercase letters, "
                        "numbers, dot, underscore or hyphen"
                    ),
                )
            conflict = (
                db.query(User.id)
                .filter(User.username == uname, User.id != user.id)
                .first()
            )
            if conflict:
                raise HTTPException(status_code=400, detail="Username already taken")
            user.username = uname

    if password is not None and str(password).strip():
        plain = str(password).strip()
        if len(plain) < 4:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 4 characters",
            )
        user.password_hash = hash_password(plain)
