"""One-year uptime guards: health, DB password, restore, drill, retention, sessions."""
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


# --------------------------------------------------------------- health ---
def test_health_is_503_when_database_down(client, monkeypatch):
    from app.core import db as db_mod

    monkeypatch.setattr(db_mod, "check_database", lambda: False)
    monkeypatch.setattr(db_mod, "recover_local_postgres", lambda: False)
    resp = client.get("/api/health")
    assert resp.status_code == 503
    assert resp.json() == {"ok": False, "database": False}


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200 and resp.json()["ok"] is True


# ------------------------------------------------ database password -------
@pytest.fixture()
def scratch_cluster(tmp_path_factory):
    pgserver = pytest.importorskip("pgserver")
    # pgserver/initdb need an ASCII path without spaces issues: use a short temp dir.
    pgdata = tmp_path_factory.mktemp("pgsec") / "pgdata"
    srv = pgserver.get_server(str(pgdata), cleanup_mode="delete")
    yield pgdata, srv.get_uri()
    srv.cleanup()


def _connects(uri):
    eng = create_engine(uri, connect_args={"connect_timeout": 5})
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        eng.dispose()


def test_local_postgres_gets_password_and_self_heals(scratch_cluster, tmp_path):
    from sqlalchemy.engine import make_url

    from app.core.pg_security import MARKER, secure_local_postgres

    pgdata, trust_uri = scratch_cluster
    secret_file = tmp_path / "pg_secret"

    uri = secure_local_postgres(pgdata, trust_uri, secret_file)
    password = make_url(uri).password
    assert password and secret_file.read_text().strip() == password
    assert MARKER in (pgdata / "pg_hba.conf").read_text()
    assert _connects(uri)
    assert not _connects(trust_uri)  # no password -> refused

    # Second start: same password reused.
    assert secure_local_postgres(pgdata, trust_uri, secret_file) == uri

    # Secret file lost: a new password is set automatically, no lock-out.
    secret_file.unlink()
    healed = secure_local_postgres(pgdata, trust_uri, secret_file)
    assert make_url(healed).password and make_url(healed).password != password
    assert _connects(healed)
    assert not _connects(uri)  # old password no longer valid


# -------------------------------------------------------------- restore ---
def _make_patient(c, nom):
    r = c.post("/api/patients", json={"nom": nom, "prenom": "Test", "telephone": f"0550 {len(nom):02d} 00 00"})
    assert r.status_code == 201, r.text


def test_safe_restore_swaps_databases(owner_client, users, monkeypatch):
    from app import cli
    from app.core.db import get_engine

    _make_patient(owner_client, "Avant")
    dump = Path(owner_client.post("/api/backup/run").json()["backup"]["file_path"])
    _make_patient(owner_client, "Apres")

    monkeypatch.setattr(cli, "_app_is_running", lambda: False)
    live = get_engine().url
    assert cli._restore(dump, assume_yes=True) == 0

    names = [p["nom"] for p in owner_client.get("/api/patients").json()["patients"]]
    assert "Avant" in names and "Apres" not in names
    # The pre-restore data is kept aside, and a safety dump was taken.
    admin = create_engine(live.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        kept = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"),
                            {"d": f"{live.database}_before_restore"}).scalar()
        conn.execute(text(f'DROP DATABASE IF EXISTS "{live.database}_before_restore" WITH (FORCE)'))
    admin.dispose()
    assert kept == 1


def test_restore_refuses_while_running_or_bad_file(owner_client, users, monkeypatch, tmp_path):
    from app import cli

    _make_patient(owner_client, "Garde")
    monkeypatch.setattr(cli, "_app_is_running", lambda: True)
    dump = Path(owner_client.post("/api/backup/run").json()["backup"]["file_path"])
    assert cli._restore(dump, assume_yes=True) == 1

    monkeypatch.setattr(cli, "_app_is_running", lambda: False)
    junk = tmp_path / "junk.dump"
    junk.write_bytes(b"not a backup")
    assert cli._restore(junk, assume_yes=True) == 1
    names = [p["nom"] for p in owner_client.get("/api/patients").json()["patients"]]
    assert "Garde" in names  # data untouched


# ---------------------------------------------------------------- drill ---
def test_weekly_drill_passes_and_checks_attachment_files(owner_client, users):
    from app.backup import service

    patient = owner_client.post("/api/patients", json={"nom": "Radio", "prenom": "X", "telephone": "0661 00 00 01"}).json()["patient"]
    up = owner_client.post(
        f"/api/patients/{patient['id']}/attachments",
        files={"file": ("pano.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert up.status_code in (200, 201), up.text
    assert owner_client.post("/api/backup/run").status_code == 201

    result = service.run_restore_drill()
    assert result["ok"], result
    assert result["counts"]["attachments"] == 1 and result["missing_files"] == 0
    assert owner_client.get("/api/backup/status").json()["drill"]["ok"] is True
    assert service.drill_due(service.now_tz()) is False


def test_drill_flags_missing_attachment_file(owner_client, users):
    import shutil

    from app.backup import service
    from app.core.config import get_settings

    patient = owner_client.post("/api/patients", json={"nom": "Perdu", "prenom": "X", "telephone": "0661 00 00 02"}).json()["patient"]
    owner_client.post(
        f"/api/patients/{patient['id']}/attachments",
        files={"file": ("scan.png", b"\x89PNG\r\n\x1a\nfake2", "image/png")},
    )
    assert owner_client.post("/api/backup/run").status_code == 201
    shutil.rmtree(Path(get_settings().backups_dir) / "attachments" / str(patient["id"]))
    result = service.run_restore_drill()
    assert not result["ok"] and result["missing_files"] == 1


# ------------------------------------------------------------ retention ---
def test_orphan_dumps_pruned_by_filename(tmp_path):
    from app.backup.service import prune_orphan_dumps

    for day in range(1, 21):
        (tmp_path / f"clinic_auto_202603{day:02d}_130000.dump").write_bytes(b"x")
    for n in range(1, 8):
        (tmp_path / f"clinic_manual_2026030{n}_090000.dump").write_bytes(b"x")
    removed = prune_orphan_dumps(tmp_path, keep_daily=14, keep_manual=5)
    assert removed == 6 + 2
    autos = sorted(p.name for p in tmp_path.glob("clinic_auto_*"))
    assert autos[0] == "clinic_auto_20260307_130000.dump"  # newest 14 kept


# ------------------------------------------------------------- sessions ---
def test_session_slides_when_in_use(owner_client):
    from sqlalchemy import select

    from app.core.dates import now_tz
    from app.core.db import get_session_factory
    from app.core.models import Session as DbSession

    with get_session_factory()() as db:
        row = db.execute(select(DbSession)).scalars().first()
        row.expires_at = now_tz() + timedelta(hours=1)  # nearly expired
        db.commit()
    resp = owner_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert "clinic_session" in resp.headers.get("set-cookie", "")  # cookie refreshed
    with get_session_factory()() as db:
        row = db.execute(select(DbSession)).scalars().first()
        assert row.expires_at > now_tz() + timedelta(hours=11)


def test_ensure_database_keeps_password(db_url):
    """Regression: str(URL) masks the password as '***', which broke every
    connection once the bundled database became password-protected."""
    from sqlalchemy.engine import make_url

    from app.core.db import _ensure_database

    with_pw = make_url(db_url).set(database="postgres", password="s3cret-xyz").render_as_string(hide_password=False)
    out = _ensure_database(with_pw, "clinic_test")
    assert make_url(out).password == "s3cret-xyz" and "***" not in out
