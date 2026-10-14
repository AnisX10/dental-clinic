"""Backup service: pg_dump logical backups, retention, daily scheduler.

- Backups go to data/backups as compressed custom-format dumps.
- Retention: keep N daily-auto and M manual backups; never delete the newest
  valid backup; failed dumps never displace good ones.
- The scheduler runs inside the API process (single local server, no extra
  services for the clinic to manage).
"""
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.models import BackupRecord

_scheduler_started = False
_scheduler_lock = threading.Lock()
_last_run: dict = {}


def _pg_dump_path() -> str | None:
    """Locate pg_dump: bundled with pgserver first, then system PATH."""
    try:
        import pgserver

        candidate = Path(pgserver.__file__).parent / "pginstall" / "bin"
        if (candidate / "pg_dump.exe").is_file() or (candidate / "pg_dump").is_file():
            return str(candidate)
    except Exception:
        pass
    from shutil import which

    return which("pg_dump")


def run_backup(db: OrmSession, *, kind: str, reason: str = "") -> BackupRecord:
    """Run pg_dump now and record the outcome. Raises on failure."""

    from app.core.config import get_settings
    from app.core.db import get_engine

    settings = get_settings()
    if kind not in ("auto", "manual"):
        raise ValueError("bad backup kind")
    backups_dir = Path(settings.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)

    stamp = now_tz().strftime("%Y%m%d_%H%M%S")
    target = backups_dir / f"clinic_{kind}_{stamp}.dump"
    # Same-second backups must not overwrite each other: disambiguate the name.
    counter = 2
    while target.exists():
        target = backups_dir / f"clinic_{kind}_{stamp}_{counter}.dump"
        counter += 1

    url = get_engine().url
    bin_dir = _pg_dump_path()
    pg_dump = (str(Path(bin_dir) / "pg_dump") if bin_dir else "pg_dump")

    cmd = [
        pg_dump,
        "--format=custom",
        "--compress=6",
        f"--file={target}",
        f"--dbname={url.render_as_string(hide_password=False)}",
    ]
    started = now_tz()
    record = BackupRecord(kind=kind, file_path=str(target), status="failed", size_bytes=0)
    db.add(record)
    db.flush()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env={
                **_minimal_env(),
                "PGHOST": url.host or "127.0.0.1",
                "PGPORT": str(url.port or 5432),
                "PGUSER": url.username or "postgres",
                "PGPASSWORD": url.password or "",
            },
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:500] or "pg_dump failed")
        size = target.stat().st_size if target.exists() else 0
        if size == 0:
            raise RuntimeError("backup file is empty")
        record.status = "success"
        record.size_bytes = size
        record.error = ""
    except Exception as exc:
        record.status = "failed"
        record.error = str(exc)[:500]
        _last_run.clear()
        _last_run.update(
            {
                "kind": kind,
                "ok": False,
                "error": str(exc)[:200],
                "at": started.isoformat(),
            }
        )
        # Failed backup surfaces as an error to the caller (API -> user).
        raise
    finally:
        db.flush()

    _last_run.clear()
    _last_run.update({"kind": kind, "ok": True, "file": str(target), "at": started.isoformat()})
    from app.core.services import get_settings_row

    settings_row = get_settings_row(db)
    _apply_retention(
        db,
        keep_daily=settings_row.backup_keep_daily,
        keep_manual=settings_row.backup_keep_manual,
    )
    return record


def _minimal_env() -> dict:
    import os

    keep = {}
    for key in ("SYSTEMROOT", "COMSPEC", "PATH", "SYSTEMDRIVE", "TMP", "TEMP", "WINDIR"):
        value = os.environ.get(key)
        if value:
            keep[key] = value
    return keep


def apply_retention(db: OrmSession, *, keep_daily: int = 14, keep_manual: int = 5) -> int:
    """Rolling retention; never deletes the newest valid backup of any kind."""
    return _apply_retention(db, keep_daily=keep_daily, keep_manual=keep_manual)


def _apply_retention(db: OrmSession, keep_daily: int = 14, keep_manual: int = 5) -> int:
    deleted = 0
    for kind, keep in (("auto", keep_daily), ("manual", keep_manual)):
        rows = list(
            db.execute(
                select(BackupRecord)
                .where(BackupRecord.kind == kind, BackupRecord.status == "success")
                .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
            )
            .scalars()
            .all()
        )
        # rows[0] is the newest success: never delete it.
        for record in rows[keep:]:
            path = Path(record.file_path)
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                continue  # never break backups over retention cleanup
            db.delete(record)
            deleted += 1
    db.flush()
    return deleted


def last_success(db: OrmSession) -> BackupRecord | None:
    return db.execute(
        select(BackupRecord)
        .where(BackupRecord.status == "success")
        .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def backup_status(db: OrmSession) -> dict:
    last = last_success(db)
    return {
        "last_success": (
            {
                "at": last.created_at.isoformat(),
                "kind": last.kind,
                "size_bytes": last.size_bytes,
            }
            if last
            else None
        )
    }


class BackupScheduler:
    """Runs the daily automatic backup at the configured Algiers hour."""

    def __init__(self, interval_seconds: int = 600):
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        global _scheduler_started
        with _scheduler_lock:
            if _scheduler_started:
                return
            _scheduler_started = True
        self._thread = threading.Thread(target=self._loop, name="backup-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                import logging

                logging.getLogger("clinic").exception("Backup scheduler tick failed")
            self._stop.wait(self.interval)

    def _tick(self) -> None:
        from app.core.dates import now_tz
        from app.core.db import get_session_factory
        from app.core.services import get_settings_row

        db = get_session_factory()()
        try:
            # Housekeeping: drop expired sessions alongside the daily backup tick.
            from app.core.auth import purge_expired_sessions

            purge_expired_sessions(db)
            db.commit()
        except Exception:
            db.rollback()
        try:
            settings_row = get_settings_row(db)
            target_hour = settings_row.backup_hour
            now = now_tz()
            today = now.date()
            already_done = (
                db.execute(
                    select(BackupRecord.id)
                    .where(
                        BackupRecord.kind == "auto",
                        BackupRecord.status == "success",
                        BackupRecord.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=now.tzinfo),
                        BackupRecord.created_at < now,
                    )
                    .limit(1)
                ).scalar()
                is not None
            )
            if now.hour >= target_hour and not already_done:
                try:
                    run_backup(db, kind="auto")
                    db.commit()
                except Exception:
                    # The failed attempt is recorded; a later tick retries.
                    db.rollback()
        finally:
            db.close()
