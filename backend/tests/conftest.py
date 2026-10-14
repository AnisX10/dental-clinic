"""Shared pytest fixtures: isolated PostgreSQL database per session, FastAPI client."""
import pathlib
import sys

# Ensure the backend package resolves before app imports.
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pgserver  # noqa: E402
import pytest  # noqa: E402

# Dedicated test pgdata so tests never touch clinic data.
_test_pgdata = BACKEND_DIR.parent / "data" / "pgdata-test"
_test_pgdata.parent.mkdir(parents=True, exist_ok=True)
_server = pgserver.get_server(str(_test_pgdata), cleanup_mode=None)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Tests share one process: clear the login limiter between tests."""
    from app.core.auth_api import _login_limiter

    _login_limiter._hits.clear()
    yield
    _login_limiter._hits.clear()


@pytest.fixture(scope="session")
def db_url():
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

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
