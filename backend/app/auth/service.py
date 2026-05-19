from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any,cast

import bcrypt
from jose import jwt

from app.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expires_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return cast(str, jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return cast(dict[str, Any], jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]))
