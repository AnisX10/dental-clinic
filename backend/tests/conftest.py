"""Shared pytest fixtures: isolated PostgreSQL database per session, FastAPI client."""
import os
import pathlib
import sys

import pytest

# Ensure the backend package resolves before app imports.
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_test_db_env = os.environ.get("CLINIC_TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
_server = None

if not _test_db_env:
    try:
        import pgserver  # pyright: ignore[reportMissingImports] — E402 deliberately after sys.path bootstrap

        _test_pgdata = BACKEND_DIR.parent / "data" / "pgdata-test"
        _test_pgdata.parent.mkdir(parents=True, exist_ok=True)
        _server = pgserver.get_server(str(_test_pgdata), cleanup_mode=None)
    except Exception:
        # ImportError is a subclass of Exception; keep the fallback for
        # Python 3.12+ where pgserver is unsupported or absent.
        _test_db_env = "postgresql+psycopg://postgres@127.0.0.1:5432/clinic_test"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Tests share one process: clear the login limiter between tests."""
    from app.core.auth_api import _login_limiter

    _login_limiter._hits.clear()
    yield
    _login_limiter._hits.clear()


@pytest.fixture(autouse=True)
def _license_unlocked():
    """Every API test runs with an active stub license (the real machinery is
    exercised in test_licensing.py, which swaps the stub out per-test)."""
    from types import SimpleNamespace

    from app.licensing import service

    stub = SimpleNamespace()
    stub.state = service.LicenseState(
        active=True,
        reason="ok",
        payload={"clinic": "Test Clinique", "dentist": "Dr Test", "issued_at": "2026-01-01"},
        installation_id="stub-install-0001",
    )
    stub.load = lambda: stub.state
    if service._original_get_manager is None:
        service._original_get_manager = service.get_manager
    original = service.get_manager
    try:
        service.get_manager = lambda: stub
        yield
    finally:
        service.get_manager = original


@pytest.fixture(scope="session")
def db_url():
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    if _test_db_env:
        target_url = make_url(_test_db_env)
        admin_url = target_url.set(database="postgres")
        admin = create_admin_engine(str(admin_url))
        with admin.connect() as conn:
            exists = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{target_url.database}'")
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target_url.database}"'))
        admin.dispose()
        return str(target_url)

    # This branch only runs when the pgserver import above succeeded.
    assert _server is not None
    uri = _server.get_uri()
    url = make_url(uri).set(database="clinic_test")
    admin = create_admin_engine(uri)
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'clinic_test'")
        ).scalar()
        if not exists:
            conn.execute(text('CREATE DATABASE "clinic_test"'))
    admin.dispose()
    return str(url)


def create_admin_engine(uri: str):
    from sqlalchemy import create_engine

    return create_engine(uri, isolation_level="AUTOCOMMIT")


@pytest.fixture()
def client(db_url, monkeypatch):
    """FastAPI TestClient against a freshly-migrated, per-test database."""
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient

    from app.core import db as db_mod
    from app.core.config import get_settings

    monkeypatch.setenv("CLINIC_DATABASE_URL", db_url)
    get_settings.cache_clear()
    db_mod.dispose_engine()

    ini = BACKEND_DIR / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "migrations"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")

    # Isolated storage directories for the test run.
    settings = get_settings()
    settings.attachments_dir = BACKEND_DIR.parent / "data" / "test-attachments"
    settings.backups_dir = BACKEND_DIR.parent / "data" / "test-backups"

    # Wipe business tables between tests (fast TRUNCATE).
    engine = db_mod.get_engine()
    from sqlalchemy import text

    tables = [
        "audit_log", "appointment_events", "appointments", "attachments",
        "backup_records", "clinical_notes", "documents", "medical_profiles",
        "patient_treatments", "payments", "sessions", "tooth_states",
        "tooth_state_history", "treatment_catalog", "clinic_settings", "patients",
        "users", "dsp_acts", "dsp_registry", "devis_items", "devis",
        "sterilization_cycle_items", "sterilization_cycles",
        "lab_invoice_payments", "lab_invoices", "lab_orders", "labs",
        "stock_movements", "stock_items", "treatment_consumables",
    ]
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    db_mod.dispose_engine()


@pytest.fixture()
def owner_client(client, users):
    """Authenticated as owner-level dentiste (independent cookie jar)."""
    from fastapi.testclient import TestClient

    with TestClient(app=client.app) as c:
        resp = c.post(
            "/api/auth/login", json={"username": "owner", "password": "password-123"}
        )
        assert resp.status_code == 200, resp.text
        yield c


@pytest.fixture()
def reception_client(client, users):
    """Authenticated as non-owner reception (independent cookie jar)."""
    from fastapi.testclient import TestClient

    with TestClient(app=client.app) as c:
        resp = c.post(
            "/api/auth/login", json={"username": "reception", "password": "password-123"}
        )
        assert resp.status_code == 200, resp.text
        yield c


@pytest.fixture()
def users(client):
    """Create the standard two users (owner=dentiste, reception)."""
    from app.core.db import get_session_factory
    from app.core.services import create_user

    db = get_session_factory()()
    try:
        owner = create_user(
            db, username="owner", password="password-123",
            full_name="Dr Owner", role="dentiste", is_owner=True,
        )
        create_user(
            db, username="reception", password="password-123",
            full_name="Reception", role="reception", is_owner=False,
        )
        db.commit()
        return {"owner": owner.id}
    finally:
        db.close()
