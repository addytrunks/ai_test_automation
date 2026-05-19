import time
import uuid

import pytest
from jose import jwt

from app.auth.service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("hunter2hunter2")
    assert h != "hunter2hunter2"
    assert verify_password("hunter2hunter2", h) is True
    assert verify_password("wrong-password", h) is False


def test_jwt_round_trip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "60")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.config import get_settings

    get_settings.cache_clear()

    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id))
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["exp"] > time.time()


def test_jwt_decode_rejects_garbage(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(jwt.JWTError):
        decode_access_token("not.a.jwt")
