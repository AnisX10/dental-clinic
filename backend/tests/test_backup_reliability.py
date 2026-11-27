"""Backup reliability: attachments, failure records, catch-up, pre-upgrade backup."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.core.dates import CLINIC_TZ
from app.core.db import get_engine, get_session_factory
from app.core.models import BackupRecord


def _rows():
    with get_session_factory()() as db:
        return list(db.execute(select(BackupRecord).order_by(BackupRecord.id)).scalars().all())


def test_attachments_are_mirrored_with_backup(owner_client, users, tmp_path, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    xray = settings.attachments_dir / "42" / "panoramique.png"
    xray.parent.mkdir(parents=True, exist_ok=True)
    xray.write_bytes(b"\x89PNG fake x-ray")
    monkeypatch.setattr(settings, "backup_offsite_dir", str(tmp_path / "usb"))

    resp = owner_client.post("/api/backup/run")
    assert resp.status_code == 201, resp.text

    local = settings.backups_dir / "attachments" / "42" / "panoramique.png"
    offsite = tmp_path / "usb" / "attachments" / "42" / "panoramique.png"
    assert local.read_bytes() == b"\x89PNG fake x-ray"
    assert offsite.read_bytes() == b"\x89PNG fake x-ray"
    status = owner_client.get("/api/backup/status").json()
    assert status["offsite"] == {"configured": True, "error": "", "last_ok_at": status["offsite"]["last_ok_at"]}


def test_mirror_is_incremental_and_keeps_deleted_files(tmp_path):
    from app.backup.service import mirror_attachments

    src, dest = tmp_path / "src", tmp_path / "dest"
    (src / "1").mkdir(parents=True)
    (src / "1" / "a.pdf").write_bytes(b"a")
    assert mirror_attachments(src, dest) == 1
    assert mirror_attachments(src, dest) == 0  # unchanged -> nothing copied
    (src / "1" / "a.pdf").unlink()
    assert mirror_attachments(src, dest) == 0
    assert (dest / "1" / "a.pdf").is_file()  # deleted at source, kept in backup


def test_failed_backup_is_recorded_and_partial_file_removed(owner_client, users, monkeypatch):
    from app.backup import service

    seen = {}

    def broken_verify(target, bin_dir):
        seen["target"] = target
        assert target.is_file()  # pg_dump produced something...
        raise RuntimeError("backup verification failed: simulated")

    monkeypatch.setattr(service, "_verify_dump", broken_verify)
    resp = owner_client.post("/api/backup/run")
    assert resp.status_code == 500

    assert not seen["target"].exists()  # ...which was deleted
    failed = [r for r in _rows() if r.status == "failed"]
    assert len(failed) == 1 and "simulated" in failed[0].error  # survived the rollback
    status = owner_client.get("/api/backup/status").json()
    assert status["last_failure"]["error"].endswith("simulated")

    monkeypatch.undo()
    assert owner_client.post("/api/backup/run").status_code == 201
    assert owner_client.get("/api/backup/status").json()["last_failure"] is None


def _add(kind, status, at):
    with get_session_factory()() as db:
        db.add(BackupRecord(kind=kind, status=status, file_path="x", size_bytes=1, error="", created_at=at))
        db.commit()


def _due(now, hour=13):
    from app.backup.service import auto_backup_due

    with get_session_factory()() as db:
        return auto_backup_due(db, now, hour)


def test_auto_backup_catch_up_rules(client):
    morning = datetime(2026, 3, 10, 8, 0, tzinfo=CLINIC_TZ)
    # Never backed up: catch up immediately, even before the configured hour.
    assert _due(morning) is True

    # Backed up yesterday at 13:30 -> not overdue at 08:00, due again at 13:00.
    _add("auto", "success", morning - timedelta(hours=18, minutes=30))
    assert _due(morning) is False
    assert _due(morning.replace(hour=13, minute=5)) is True

    # PC was off for two days -> catch up at the first tick, before 13:00.
    assert _due(morning + timedelta(days=2)) is True

    # Already done today -> no second backup.
    _add("auto", "success", morning.replace(hour=13, minute=10))
    assert _due(morning.replace(hour=18)) is False


def test_auto_backup_waits_after_failure(client):
    now = datetime(2026, 3, 10, 14, 0, tzinfo=CLINIC_TZ)
    _add("auto", "failed", now - timedelta(minutes=10))
    assert _due(now) is False
    assert _due(now + timedelta(minutes=55)) is True


def test_migrate_to_head_noop_when_current(client):
    from app.core.schema import migrate_to_head

    assert migrate_to_head() is False


def test_migrate_refuses_unknown_revision(client):
    from app.core.schema import SchemaError, migrate_to_head

    with get_engine().begin() as conn:
        real = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        conn.execute(text("UPDATE alembic_version SET version_num = 'ffffffffffff'"))
    try:
        with pytest.raises(SchemaError, match="unknown"):
            migrate_to_head()
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num = :v"), {"v": real})


def test_migration_takes_backup_first(client, users):
    from pathlib import Path

    from alembic import command

    from app.core.schema import alembic_config, migrate_to_head

    command.downgrade(alembic_config(), "-1")
    assert migrate_to_head() is True
    manual = [r for r in _rows() if r.kind == "manual" and r.status == "success"]
    assert len(manual) == 1 and Path(manual[0].file_path).is_file()


def test_migration_aborts_when_backup_fails(client, users, monkeypatch):
    from alembic import command

    from app.backup import service
    from app.core.schema import SchemaError, alembic_config, migrate_to_head, schema_revisions

    command.downgrade(alembic_config(), "-1")
    before, heads, _ = schema_revisions()

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(service, "run_backup", boom)
    with pytest.raises(SchemaError, match="Pre-upgrade backup failed"):
        migrate_to_head()
    assert schema_revisions()[0] == before  # schema untouched
    monkeypatch.undo()
    command.upgrade(alembic_config(), "head")
