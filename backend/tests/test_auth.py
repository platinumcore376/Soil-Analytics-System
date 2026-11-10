"""Authentication: register, login, token handling."""


def test_register_returns_token_and_user(client):
    r = client.post(
        "/auth/register",
        json={"phone": "9111111111", "name": "Asha", "password": "goodpassword1"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"]
    assert body["user"]["phone"] == "9111111111"
    assert body["user"]["name"] == "Asha"


def test_register_duplicate_phone_conflicts(client):
    payload = {"phone": "9222222222", "name": "A", "password": "goodpassword1"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_register_with_email_only(client):
    r = client.post(
        "/auth/register",
        json={"email": "farmer@example.com", "name": "E", "password": "goodpassword1"},
    )
    assert r.status_code == 201, r.text
    login = client.post(
        "/auth/login",
        json={"identifier": "farmer@example.com", "password": "goodpassword1"},
    )
    assert login.status_code == 200, login.text


def test_login_roundtrip_and_me(client, make_user):
    u = make_user()
    login = client.post(
        "/auth/login", json={"identifier": u["phone"], "password": u["password"]}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["phone"] == u["phone"]


def test_login_wrong_password_rejected(client, make_user):
    u = make_user()
    r = client.post(
        "/auth/login", json={"identifier": u["phone"], "password": "wrong-password"}
    )
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/farms").status_code == 401
    garbage = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/farms", headers=garbage).status_code == 401


def test_health_endpoints_are_public(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["status"] == "ok"
