from httpx import AsyncClient

VALID_PWD = "supersecretpw"


async def test_register_creates_user(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": VALID_PWD, "name": "Alice"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Alice"
    assert "password" not in body
    assert "id" in body


async def test_register_rejects_duplicate(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": VALID_PWD}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


async def test_login_returns_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": VALID_PWD},
    )
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "carol@example.com", "password": VALID_PWD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20


async def test_login_rejects_bad_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dave@example.com", "password": VALID_PWD},
    )
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "dave@example.com", "password": "wrong-password!!"},
    )
    assert r.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_user_when_authenticated(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "eve@example.com", "password": VALID_PWD, "name": "Eve"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "eve@example.com", "password": VALID_PWD},
    )
    token = login.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "eve@example.com"
