from datetime import UTC

import pytest
from pydantic import ValidationError

from app.auth.schemas import TokenResponse, UserCreate, UserLogin, UserRead


def test_user_create_requires_email_and_password():
    u = UserCreate(email="a@b.com", password="hunter2hunter2", name="A B")
    assert u.email == "a@b.com"
    assert u.password == "hunter2hunter2"


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="short")


def test_user_create_rejects_bad_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="hunter2hunter2")


def test_user_login_minimal_fields():
    u = UserLogin(email="a@b.com", password="hunter2hunter2")
    assert u.email == "a@b.com"


def test_user_read_excludes_password():
    import uuid
    from datetime import datetime

    payload = {
        "id": uuid.uuid4(),
        "email": "a@b.com",
        "name": "A B",
        "created_at": datetime.now(UTC),
    }
    u = UserRead(**payload)
    assert "password" not in u.model_dump()


def test_token_response_shape():
    t = TokenResponse(access_token="abc", token_type="bearer")
    d = t.model_dump()
    assert d == {"access_token": "abc", "token_type": "bearer"}
