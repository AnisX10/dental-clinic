"""Forced password change: bootstrap accounts, change-password endpoint, launcher bootstrap."""
import pytest

from app.core.db import get_session_factory
from app.core.models import User
from app.core.services import create_user

STRONG = "Nouveau#Pass-2026"


def _make_pending(username="pending", password="Temp-pass-1234!"):
    db = get_session_factory()()
    try:
        user = create_user(db, username=username, password=password, full_name="Pending",
                           role="dentiste", is_owner=True)
        user.must_change_password = True
        db.commit()
    finally:
        db.close()
    return username, password


def test_pending_user_is_blocked_until_change(client):
    username, password = _make_pending()
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    assert resp.json()["user"]["must_change_password"] is True

    # /me works (the SPA needs it to route to the change screen)...
    assert client.get("/api/auth/me").status_code == 200
    # ...but every business endpoint is refused.
    blocked = client.get("/api/patients")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    ok = client.post("/api/auth/change-password",
                     json={"current_password": password, "new_password": STRONG})
    assert ok.status_code == 200, ok.text
    assert ok.json()["user"]["must_change_password"] is False
    assert client.get("/api/patients").status_code == 200

    # Old password no longer works, new one does.
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": username, "password": password}).status_code == 401
    assert client.post("/api/auth/login", json={"username": username, "password": STRONG}).status_code == 200


@pytest.mark.parametrize("new_password,code", [
    ("short1!", "weak_password"),
    ("Cabinet2026!", "weak_password"),
    ("nosymbols12345", "weak_password"),
    ("Temp-pass-1234!", "password_same"),
])
def test_change_password_rejects_weak_or_same(client, new_password, code):
    username, password = _make_pending()
    client.post("/api/auth/login", json={"username": username, "password": password})
    resp = client.post("/api/auth/change-password",
                       json={"current_password": password, "new_password": new_password})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == code


def test_change_password_requires_current_password(owner_client):
    resp = owner_client.post("/api/auth/change-password",
                             json={"current_password": "wrong-one", "new_password": STRONG})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_current_password"


def test_change_password_requires_login(client):
    resp = client.post("/api/auth/change-password",
                       json={"current_password": "x", "new_password": STRONG})
    assert resp.status_code == 401


def test_change_password_revokes_other_sessions(client, users):
    from fastapi.testclient import TestClient

    with TestClient(app=client.app) as a, TestClient(app=client.app) as b:
        for c in (a, b):
            assert c.post("/api/auth/login", json={"username": "owner", "password": "password-123"}).status_code == 200
        resp = a.post("/api/auth/change-password",
                      json={"current_password": "password-123", "new_password": STRONG})
        assert resp.status_code == 200
        assert a.get("/api/auth/me").status_code == 200
        assert b.get("/api/auth/me").status_code == 401


def test_launcher_cold_start_creates_owner_without_default_password(client, tmp_path, monkeypatch):
    """No users: the launcher creates 'dentiste' with a random one-time password
    (written to data/), never the old public default, and forces a change."""
    from app import launcher
    from app.core.config import get_settings
    from app.core.security import DEFAULT_PASSWORDS, verify_password

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    launcher.ensure_database_bootstrapped()

    db = get_session_factory()()
    try:
        user = db.query(User).filter_by(username="dentiste").one()
        assert user.must_change_password is True
        assert not any(verify_password(pw, user.password_hash) for pw in DEFAULT_PASSWORDS)
    finally:
        db.close()

    note = (tmp_path / launcher.FIRST_ACCESS_FILENAME).read_text(encoding="utf-8")
    password = note.split("Mot de passe provisoire : ")[1].splitlines()[0].strip()
    resp = client.post("/api/auth/login", json={"username": "dentiste", "password": password})
    assert resp.status_code == 200
    assert resp.json()["user"]["must_change_password"] is True


def test_launcher_flags_existing_default_password(client, tmp_path, monkeypatch):
    """Installs created before this fix with the public default get a forced change."""
    from app import launcher
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    db = get_session_factory()()
    try:
        create_user(db, username="dentiste", password="Cabinet2026!", full_name="Dr",
                    role="dentiste", is_owner=True)
        create_user(db, username="accueil", password="Reception#2026", full_name="R",
                    role="reception")
        db.commit()
    finally:
        db.close()

    launcher.ensure_database_bootstrapped()

    db = get_session_factory()()
    try:
        flags = {u.username: u.must_change_password for u in db.query(User).all()}
    finally:
        db.close()
    assert flags == {"dentiste": True, "accueil": False}
    assert not (tmp_path / launcher.FIRST_ACCESS_FILENAME).exists()
