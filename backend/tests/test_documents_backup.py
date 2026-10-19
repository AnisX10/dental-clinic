"""Document, backup and migration tests."""
import pathlib

from tests.conftest import BACKEND_DIR  # noqa: F401


def _patient(client):
    return client.post(
        "/api/patients", json={"nom": "Belkacem", "prenom": "Lina", "telephone": "0771 55 66 77"}
    ).json()["patient"]


def test_ordonnance_creation(owner_client, users):
    patient = _patient(owner_client)
    resp = owner_client.post(
        "/api/documents",
        json={
            "patient_id": patient["id"],
            "doc_type": "ordonnance",
            "title": "Ordonnance",
            "content": {
                "lines": ["Amoxicilline 1g - 1 cp matin et soir - 6 jours", "Ibuprofène 400mg - si douleur"],
                "note": "À prendre après les repas",
            },
        },
    )
    assert resp.status_code == 201
    doc = resp.json()["document"]
    assert doc["doc_type"] == "ordonnance"
    assert len(doc["content"]["lines"]) == 2


def test_certificat_and_attestation(owner_client, users):
    patient = _patient(owner_client)
    resp = owner_client.post(
        "/api/documents",
        json={
            "patient_id": patient["id"],
            "doc_type": "certificat",
            "content": {"text": "Le patient a bénéficié de soins dentaires.", "duration_days": 2},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["document"]["content"]["duration_days"] == 2

    resp = owner_client.post(
        "/api/documents",
        json={
            "patient_id": patient["id"],
            "doc_type": "attestation",
            "content": {"text": "Attestation de prise en charge des soins."},
        },
    )
    assert resp.status_code == 201


def test_document_invalid_type_rejected(owner_client, users):
    patient = _patient(owner_client)
    resp = owner_client.post(
        "/api/documents",
        json={"patient_id": patient["id"], "doc_type": "facture", "content": {}},
    )
    assert resp.status_code == 400


def test_document_includes_clinic_template(owner_client, users):
    patient = _patient(owner_client)
    owner_client.put(
        "/api/settings",
        json={"clinic_name": "Cabinet Dentaire Test", "doctor_name": "Dr Owner", "phone": "021 55 66 77"},
    )
    doc = owner_client.post(
        "/api/documents",
        json={"patient_id": patient["id"], "doc_type": "ordonnance", "content": {"lines": ["Test"]}},
    ).json()["document"]
    detail = owner_client.get(f"/api/documents/{doc['id']}").json()
    assert detail["clinic"]["clinic_name"] == "Cabinet Dentaire Test"
    assert detail["clinic"]["doctor_name"] == "Dr Owner"


def test_manual_backup_runs(owner_client, users):
    resp = owner_client.post("/api/backup/run")
    assert resp.status_code == 201, resp.text
    backup = resp.json()["backup"]
    assert backup["status"] == "success"
    assert backup["size_bytes"] > 0
    import pathlib

    assert pathlib.Path(backup["file_path"]).is_file()
    status = owner_client.get("/api/backup/status").json()
    assert status["last_success"] is not None


def test_backup_retention(owner_client, users):
    """Run several manual backups; retention keeps only the configured count."""
    for _ in range(7):
        resp = owner_client.post("/api/backup/run")
        assert resp.status_code == 201
    status = owner_client.get("/api/backup/status")
    assert status.status_code == 200
    from sqlalchemy import select

    from app.core.db import get_session_factory
    from app.core.models import BackupRecord

    db = get_session_factory()()
    try:
        rows = list(db.execute(select(BackupRecord).order_by(BackupRecord.id)).scalars().all())
        successes = [r for r in rows if r.status == "success"]
        # Only the 5 most recent manual successes keep their files.
        kept_files = [r.file_path for r in successes if pathlib.Path(r.file_path).is_file()]
        assert len(kept_files) == 5, f"expected 5 kept files, got {len(kept_files)}"
    finally:
        db.close()


def test_backup_restore_round_trip(owner_client):
    """A full backup restores cleanly: the restored DB returns its data.

    Runs pg_restore into a fresh scratch database and asserts patients and
    documents survive the trip. Never touches the live clinic DB.
    """
    import subprocess

    # Arrange: patient + ordonnance + settings in the (test) clinic DB.
    patient = _patient(owner_client)
    doc = owner_client.post(
        "/api/documents",
        json={
            "patient_id": patient["id"],
            "doc_type": "ordonnance",
            "title": "Ordonnance",
            "content": {"lines": ["Amoxicilline 1g", "Ibuprofène 400mg"], "age": "31", "sexe": "F"},
        },
    ).json()["document"]
    owner_client.put("/api/settings", json={"clinic_name": "Cabinet RoundTrip"})

    # Backup via the API.
    resp = owner_client.post("/api/backup/run")
    assert resp.status_code == 201, resp.text
    backup = resp.json()["backup"]
    assert backup["status"] == "success"
    dump_path = pathlib.Path(backup["file_path"])
    assert dump_path.is_file() and dump_path.stat().st_size > 0

    # Restore into a scratch database (fresh + empty) using the same mechanism
    # the CLI uses, then verify every critical row made it through.
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from app.backup.service import _pg_dump_path
    from app.core.db import get_engine

    url = make_url(get_engine().url).set(drivername="postgresql")
    scratch_db = "clinic_restore_test"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
        conn.execute(text(f'CREATE DATABASE "{scratch_db}"'))
    admin.dispose()

    bin_dir = _pg_dump_path()
    pg_restore = str(pathlib.Path(bin_dir) / "pg_restore") if bin_dir else "pg_restore"
    env = {
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
        "PGHOST": url.host or "127.0.0.1",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "postgres",
        "PGPASSWORD": url.password or "",
    }

    # Restore the schema, then the data (custom-format dump is schema-complete;
    # a scratch DB is empty, so a plain restore brings the whole schema back).
    proc = subprocess.run(
        [pg_restore, "--dbname=" + str(url.set(database=scratch_db).render_as_string(hide_password=False)), str(dump_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    assert proc.returncode == 0, f"pg_restore failed: {proc.stderr[:500]}"

    restored = create_engine(str(url.set(database=scratch_db)))
    try:
        with restored.connect() as conn:
            rows = conn.execute(
                text("SELECT nom, prenom FROM patients ORDER BY id")
            ).fetchall()
            assert rows == [(patient["nom"], patient["prenom"])]
            doc_rows = conn.execute(
                text("SELECT doc_type, title FROM documents ORDER BY id")
            ).fetchall()
            assert doc_rows == [("ordonnance", doc["title"])]
            clinic_name = conn.execute(
                text("SELECT clinic_name FROM clinic_settings LIMIT 1")
            ).scalar()
            assert clinic_name == "Cabinet RoundTrip"
            such_rows = conn.execute(text("SELECT count(*) FROM users")).scalar()
            assert such_rows and such_rows > 0
    finally:
        restored.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
        admin.dispose()


def test_migration_reversibility(db_url):
    """The schema can be downgraded and upgraded cleanly."""
    import os

    os.environ["CLINIC_DATABASE_URL"] = db_url
    from alembic import command
    from alembic.config import Config

    from app.core import db as db_mod

    ini = BACKEND_DIR / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "migrations"))
    cfg.attributes["configure_logger"] = False
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    db_mod.dispose_engine()
