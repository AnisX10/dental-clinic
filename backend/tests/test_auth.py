"""Auth + authorization tests."""
from tests.conftest import BACKEND_DIR  # noqa: F401


def test_login_success(client, users):
    resp = client.post("/api/auth/login", json={"username": "owner", "password": "password-123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "dentiste"
    assert body["user"]["is_owner"] is True
    assert "clinic_session" in resp.cookies


def test_login_wrong_password(client, users):
    resp = client.post("/api/auth/login", json={"username": "owner", "password": "nope-nope"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_credentials"


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_logout(client, users):
    client.post("/api/auth/login", json={"username": "owner", "password": "password-123"})
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limiting(client, users):
    for _ in range(8):
        client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
    resp = client.post("/api/auth/login", json={"username": "owner", "password": "password-123"})
    assert resp.status_code == 429


def test_owner_only_endpoint_forbidden_for_reception(reception_client, users):
    resp = reception_client.post("/api/backup/run")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden_owner"


def test_owner_only_catalog_price(reception_client, owner_client, users):
    item = owner_client.post(
        "/api/clinical/catalog",
        json={"name": "Test price item", "category": "Soins", "default_price": "1234"},
    ).json()["item"]
    # Non-owner cannot change the price...
    resp = reception_client.put(
        f"/api/clinical/catalog/{item['id']}", json={"default_price": "999"}
    )
    assert resp.status_code == 403
    # ...but the owner can.
    resp = owner_client.put(f"/api/clinical/catalog/{item['id']}", json={"default_price": "999"})
    assert resp.status_code == 200
    assert resp.json()["item"]["default_price"] == "999.00"


def test_protected_routes_require_auth(client):
    paths = [
        ("get", "/api/patients"),
        ("post", "/api/patients"),
        ("get", "/api/agenda/today"),
        ("post", "/api/agenda/appointments"),
        ("get", "/api/clinical/catalog"),
        ("get", "/api/payments/patients/1/ledger"),
        ("get", "/api/settings"),
        ("get", "/api/backup/status"),
    ]
    for method, path in paths:
        resp = getattr(client, method)(path)
        assert resp.status_code == 401, f"{method} {path} should require auth"
