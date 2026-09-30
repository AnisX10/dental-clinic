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
