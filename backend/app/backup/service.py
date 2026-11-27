"""Backup service: pg_dump logical backups, retention, daily scheduler.

- Backups go to data/backups as compressed custom-format dumps.
- Retention: keep N daily-auto and M manual backups; never delete the newest
  valid backup; failed dumps never displace good ones.
- The scheduler runs inside the API process (single local server, no extra
  services for the clinic to manage).
"""
import logging
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.models import BackupRecord

logger = logging.getLogger("clinic")

_scheduler_started = False
_scheduler_lock = threading.Lock()
_last_run: dict = {}
# In-memory health of the off-site / attachment copies (reset at restart).
_offsite_status: dict = {"configured": False, "error": "", "last_ok_at": None, "attachments_error": ""}


def _pg_dump_path() -> str | None:
    """Locate pg_dump matching the active server; fall back to the newest available client."""
    server_major = None
    try:
        from app.core.db import get_engine

        with get_engine().connect() as connection:
            version_num = int(connection.exec_driver_sql("SHOW server_version_num").scalar())
            server_major = version_num // 10000
    except Exception:
        pass

    candidates = []

    for pg_root in (Path(r"C:\Program Files\PostgreSQL"), Path(r"C:\Program Files (x86)\PostgreSQL")):
        if pg_root.is_dir():
            for pg_dir in pg_root.glob("*/bin"):
                exe = pg_dir / "pg_dump.exe"
                if exe.is_file():
                    try:
                        ver = int(pg_dir.parent.name)
                    except ValueError:
                        ver = 0
                    candidates.append((ver, str(pg_dir)))

    found = shutil.which("pg_dump")
    if found:
        candidates.append((_pg_dump_major(found), str(Path(found).parent)))

    try:
        import pgserver  # pyright: ignore[reportMissingImports]

        mod_file = pgserver.__file__
        if mod_file:
            candidate = Path(mod_file).parent / "pginstall" / "bin"
            exe = candidate / ("pg_dump.exe" if (candidate / "pg_dump.exe").is_file() else "pg_dump")
            if exe.is_file():
                candidates.append((_pg_dump_major(str(exe)), str(candidate)))
    except Exception:
        pass

    if server_major is not None:
        for major, directory in candidates:
            if major == server_major:
                return directory
    if candidates:
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        return candidates[0][1]
    return None


def _pg_dump_major(executable: str) -> int:
    """Read the major version from pg_dump --version, returning zero if unknown."""
    try:
        proc = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5)
        match = re.search(r"\b(\d+)\.\d+", proc.stdout + proc.stderr)
        return int(match.group(1)) if match else 0
    except Exception:
        return 0


def _pg_tool(bin_dir: str | None, name: str) -> str:
    if bin_dir:
        exe = Path(bin_dir) / f"{name}.exe"
        return str(exe) if exe.is_file() else str(Path(bin_dir) / name)
    return name


def _verify_dump(target: Path, bin_dir: str | None) -> None:
    """Check the dump is a readable archive (``pg_restore --list``). Raises if not."""
    proc = subprocess.run(
        [_pg_tool(bin_dir, "pg_restore"), "--list", str(target)],
        capture_output=True,
        text=True,
        timeout=300,
        env=_minimal_env(bin_dir),
    )
    if proc.returncode != 0 or "TABLE DATA" not in proc.stdout:
        raise RuntimeError(
            "backup verification failed: " + (proc.stderr.strip()[:300] or "no table data in archive")
        )


def _record_failure(kind: str, target: Path, error: str) -> None:
    """Persist a failed attempt in its own transaction.

    Callers roll back their own session after a failure, which used to erase
    the failure record; a separate session keeps it visible to the dashboard.
    """
    try:
        from app.core.db import get_session_factory

        with get_session_factory()() as s:
            s.add(
                BackupRecord(
                    kind=kind, file_path=str(target), status="failed", size_bytes=0, error=error[:500]
                )
            )
            s.commit()
    except Exception:
        logger.exception("Could not record failed backup")


def run_backup(db: OrmSession, *, kind: str, reason: str = "") -> BackupRecord:
    """Run pg_dump now, verify it, mirror attachments, and record the outcome.

    Raises on failure; the failure itself is committed separately so it
    survives the caller's rollback.
    """

    from app.core.config import get_settings
    from app.core.db import get_engine

    settings = get_settings()
    if kind not in ("auto", "manual"):
        raise ValueError("bad backup kind")
    backups_dir = Path(settings.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    _check_free_space(backups_dir)

    stamp = now_tz().strftime("%Y%m%d_%H%M%S")
    target = backups_dir / f"clinic_{kind}_{stamp}.dump"
    # Same-second backups must not overwrite each other: disambiguate the name.
    counter = 2
    while target.exists():
        target = backups_dir / f"clinic_{kind}_{stamp}_{counter}.dump"
        counter += 1

    url = get_engine().url.set(drivername="postgresql")
    bin_dir = _pg_dump_path()

    # Connection details go through PG* env vars; the password never appears
    # on the command line.
    cmd = [
        _pg_tool(bin_dir, "pg_dump"),
        "--format=custom",
        "--compress=6",
        f"--file={target}",
        f"--dbname={url.database or 'clinic'}",
    ]
    started = now_tz()
    if reason:
        logger.info("Starting %s backup (%s)", kind, reason)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env={
                **_minimal_env(bin_dir),
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
        _verify_dump(target, bin_dir)
    except Exception as exc:
        error = str(exc)[:500] or exc.__class__.__name__
        logger.error("%s backup failed: %s", kind, error)
        try:
            target.unlink(missing_ok=True)  # never leave a partial dump behind
        except OSError:
            pass
        _record_failure(kind, target, error)
        _last_run.clear()
        _last_run.update({"kind": kind, "ok": False, "error": error[:200], "at": started.isoformat()})
        # Failed backup surfaces as an error to the caller (API -> user).
        raise

    record = BackupRecord(kind=kind, file_path=str(target), status="success", size_bytes=size, error="")
    db.add(record)
    db.flush()

    _last_run.clear()
    _last_run.update({"kind": kind, "ok": True, "file": str(target), "at": started.isoformat()})

    # Patient files (X-rays, PDFs) live outside the database: mirror them.
    attachments_dir = Path(settings.attachments_dir)
    _offsite_status.update({"attachments_error": ""})
    try:
        copied = mirror_attachments(attachments_dir, backups_dir / "attachments")
        if copied:
            logger.info("Attachments mirrored to backups: %d new/changed file(s)", copied)
    except OSError as exc:
        logger.error("Attachment backup failed: %s", exc)
        _offsite_status["attachments_error"] = str(exc)[:200]

    keep_daily, keep_manual = _retention_settings(db)
    _copy_offsite(target, kind, keep_daily=keep_daily, keep_manual=keep_manual)
    _apply_retention(db, keep_daily=keep_daily, keep_manual=keep_manual)
    prune_orphan_dumps(backups_dir, keep_daily, keep_manual)
    return record


def _retention_settings(db: OrmSession) -> tuple[int, int]:
    """Read retention counts with plain SQL.

    The pre-upgrade backup runs against the *old* schema, where the ORM model
    may list columns that don't exist yet; these two columns exist in every
    schema version, so this read can't fail on an older database.
    """
    row = db.execute(
        text("SELECT backup_keep_daily, backup_keep_manual FROM clinic_settings WHERE id = 1")
    ).first()
    if row is None:
        return 14, 5
    return int(row[0]), int(row[1])


MIN_FREE_BYTES = 1 * 1024**3  # refuse to back up below 1 GB free
WARN_FREE_BYTES = 5 * 1024**3


def _check_free_space(directory: Path) -> None:
    free = shutil.disk_usage(directory).free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(f"not enough free disk space ({free // 1024**2} MB left)")


def disk_free_bytes() -> int | None:
    from app.core.config import get_settings

    try:
        return shutil.disk_usage(Path(get_settings().data_dir)).free
    except OSError:
        return None


def _atomic_copy(src: Path, dest: Path) -> None:
    """Copy via a temp file so an interrupted copy never looks like a good one."""
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.copy2(src, tmp)
    if tmp.stat().st_size != src.stat().st_size:
        tmp.unlink(missing_ok=True)
        raise OSError(f"incomplete copy of {src.name}")
    os.replace(tmp, dest)


def mirror_attachments(source: Path, dest: Path) -> int:
    """Copy new or changed files from ``source`` into ``dest`` (incremental).

    Files deleted from ``source`` are kept in the mirror on purpose: a medical
    image removed by mistake can still be recovered. Returns files copied.
    """
    if not source.is_dir():
        return 0
    copied = 0
    for root, _dirs, files in os.walk(source):
        rel = Path(root).relative_to(source)
        for name in files:
            if name.endswith(".tmp"):
                continue
            src = Path(root) / name
            out = dest / rel / name
            try:
                st = src.stat()
                if out.is_file():
                    ost = out.stat()
                    if ost.st_size == st.st_size and int(ost.st_mtime) >= int(st.st_mtime):
                        continue
                out.parent.mkdir(parents=True, exist_ok=True)
                _atomic_copy(src, out)
                copied += 1
            except FileNotFoundError:
                continue  # deleted while we were copying
    return copied


def _copy_offsite(target: Path, kind: str, *, keep_daily: int, keep_manual: int) -> None:
    """Mirror a successful dump (and attachments) to the off-site target, best-effort.

    An off-site failure must never fail the original backup: it is logged and
    exposed through :func:`backup_status`.
    """
    from app.core.config import get_settings

    settings = get_settings()
    raw = (settings.backup_offsite_dir or "").strip().strip('"')
    _offsite_status.update({"configured": bool(raw), "error": ""})
    if not raw:
        return
    off_dir = Path(raw)
    try:
        off_dir.mkdir(parents=True, exist_ok=True)
        _atomic_copy(target, off_dir / target.name)
        mirror_attachments(Path(settings.attachments_dir), off_dir / "attachments")
        _offsite_status["last_ok_at"] = now_tz().isoformat()
        keep = keep_daily if kind == "auto" else keep_manual
        siblings = sorted(
            off_dir.glob(f"clinic_{kind}_*.dump"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in siblings[max(keep, 1):]:
            try:
                stale.unlink()
            except OSError:
                continue
        logger.info("Offsite copy saved: %s", off_dir / target.name)
    except OSError as exc:
        logger.warning("Offsite copy failed (%s): %s", off_dir, exc)
        _offsite_status["error"] = str(exc)[:200]


def _minimal_env(bin_dir: str | None = None) -> dict:
    import os

    keep = {}
    for key in ("SYSTEMROOT", "COMSPEC", "PATH", "SYSTEMDRIVE", "TMP", "TEMP", "WINDIR"):
        value = os.environ.get(key)
        if value:
            keep[key] = value
    if bin_dir and "PATH" in keep:
        keep["PATH"] = f"{bin_dir};{keep['PATH']}"
    elif bin_dir:
        keep["PATH"] = bin_dir
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


def last_failure(db: OrmSession) -> BackupRecord | None:
    """Most recent failed attempt that is newer than the last success, if any."""
    last = last_success(db)
    q = select(BackupRecord).where(BackupRecord.status == "failed")
    if last is not None:
        q = q.where(BackupRecord.created_at > last.created_at)
    return db.execute(
        q.order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc()).limit(1)
    ).scalar_one_or_none()


def backup_status(db: OrmSession) -> dict:
    last = last_success(db)
    failed = last_failure(db)
    free = disk_free_bytes()
    return {
        "last_success": (
            {
                "at": last.created_at.isoformat(),
                "kind": last.kind,
                "size_bytes": last.size_bytes,
            }
            if last
            else None
        ),
        "last_failure": (
            {"at": failed.created_at.isoformat(), "kind": failed.kind, "error": failed.error}
            if failed
            else None
        ),
        "offsite": {
            "configured": _offsite_status.get("configured", False),
            "error": _offsite_status.get("error", ""),
            "last_ok_at": _offsite_status.get("last_ok_at"),
        },
        "attachments_error": _offsite_status.get("attachments_error", ""),
        "drill": drill_status(),
        "disk_free_bytes": free,
        "disk_low": free is not None and free < WARN_FREE_BYTES,
    }


CATCH_UP_AFTER = timedelta(hours=24)
RETRY_FAILED_AFTER = timedelta(minutes=60)


def auto_backup_due(db: OrmSession, now: datetime, target_hour: int) -> bool:
    """Decide whether the scheduler should run the automatic backup now.

    - Normal case: once per day, at or after the configured hour.
    - Catch-up: if the PC was off at that hour, the last automatic backup is
      over 24 h old -> run at the first tick (i.e. right after start-up).
    - After a failure, wait an hour before retrying instead of every tick.
    """
    last_auto = db.execute(
        select(BackupRecord.created_at)
        .where(BackupRecord.kind == "auto", BackupRecord.status == "success")
        .order_by(BackupRecord.created_at.desc())
        .limit(1)
    ).scalar()
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=now.tzinfo)
    if last_auto is not None and last_auto >= day_start:
        return False  # already done today
    overdue = last_auto is None or now - last_auto >= CATCH_UP_AFTER
    if now.hour < target_hour and not overdue:
        return False
    last_fail = db.execute(
        select(BackupRecord.created_at)
        .where(BackupRecord.kind == "auto", BackupRecord.status == "failed")
        .order_by(BackupRecord.created_at.desc())
        .limit(1)
    ).scalar()
    if last_fail is not None and now - last_fail < RETRY_FAILED_AFTER:
        return False
    return True


class BackupScheduler:
    """Runs the daily automatic backup at the configured Algiers hour."""

    def __init__(self, interval_seconds: int = 300):
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
            if auto_backup_due(db, now_tz(), settings_row.backup_hour):
                try:
                    run_backup(db, kind="auto")
                    db.commit()
                except Exception:
                    # run_backup committed the failure record in its own
                    # session; a later tick retries (after RETRY_FAILED_AFTER).
                    db.rollback()
        finally:
            db.close()
        # Weekly proof that the newest backup really restores.
        if drill_due(now_tz()):
            run_restore_drill()


# --------------------------------------------------------------------------- #
# Restore helpers + weekly restore drill
# --------------------------------------------------------------------------- #


def pg_restore_errors(target_db: str, backup_path: Path, *, extra_args: tuple[str, ...] = ()) -> list[str]:
    """pg_restore ``backup_path`` into ``target_db``; returns fatal stderr lines.

    An empty list means success. "does not exist" lines (from --clean on an
    empty target) are not fatal. Connection details travel in PG* env vars.
    """
    from app.core.db import get_engine

    url = get_engine().url
    bin_dir = _pg_dump_path()
    cmd = [
        _pg_tool(bin_dir, "pg_restore"),
        "--clean",
        "--if-exists",
        *extra_args,
        # Bare database name: host/port/user/password come from the env below.
        "--dbname=" + (target_db or ""),
        str(backup_path),
    ]
    env = {
        **_minimal_env(bin_dir),
        "PGHOST": url.host or "127.0.0.1",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "postgres",
        "PGPASSWORD": url.password or "",
    }
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1800)
    if proc.returncode != 0:
        lines = [ln for ln in (proc.stderr or "").splitlines() if ln.strip() and "does not exist" not in ln]
        return lines or [f"pg_restore exited with code {proc.returncode}"]
    return []


DRILL_EVERY = timedelta(days=7)
_DRILL_DB = "clinic_drill"


def _drill_status_path() -> Path:
    from app.core.config import get_settings

    return Path(get_settings().backups_dir) / "drill_status.json"


def drill_status() -> dict | None:
    import json

    try:
        return json.loads(_drill_status_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run_restore_drill(dump: Path | None = None) -> dict:
    """Restore the newest successful backup into a scratch database, count
    rows, check mirrored attachment files exist, drop it. Never touches the
    live database. Result is saved next to the backups and returned."""
    import json

    from sqlalchemy import create_engine, inspect

    from app.core.config import get_settings
    from app.core.db import get_engine, get_session_factory

    result: dict = {"at": now_tz().isoformat(), "ok": False, "error": "", "counts": {}, "missing_files": 0}
    if dump is None:
        with get_session_factory()() as db:
            last = last_success(db)
            dump = Path(last.file_path) if last else None
    if dump is None or not dump.is_file():
        result["error"] = "no backup file to test"
    else:
        result["file"] = dump.name
        url = get_engine().url
        admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{_DRILL_DB}" WITH (FORCE)'))
                conn.execute(text(f'CREATE DATABASE "{_DRILL_DB}"'))
            errors = pg_restore_errors(_DRILL_DB, dump)
            if errors:
                result["error"] = "; ".join(errors[:3])[:500]
            else:
                scratch = create_engine(url.set(database=_DRILL_DB))
                try:
                    with scratch.connect() as conn:
                        names = set(inspect(conn).get_table_names())
                        for table in ("patients", "appointments", "payments", "attachments", "users"):
                            if table in names:
                                result["counts"][table] = int(
                                    conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                                )
                        if "attachments" in names:
                            # Every attachment row must have its file in the backup mirror.
                            # Files live at <patient_id>/<stored_name>.
                            mirror = Path(get_settings().backups_dir) / "attachments"
                            rows = conn.execute(text("SELECT patient_id, stored_name FROM attachments")).all()
                            result["missing_files"] = sum(
                                1 for pid, name in rows if not (mirror / str(pid) / name).is_file()
                            )
                finally:
                    scratch.dispose()
                if not result["counts"].get("users"):
                    result["error"] = "restored database has no users"
                elif result["missing_files"]:
                    result["error"] = f"{result['missing_files']} attachment file(s) missing from backup"
                else:
                    result["ok"] = True
        except Exception as exc:
            result["error"] = str(exc)[:500]
        finally:
            try:
                with admin.connect() as conn:
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{_DRILL_DB}" WITH (FORCE)'))
            except Exception:
                logger.warning("Could not drop drill database %s", _DRILL_DB)
            admin.dispose()
    level = logging.INFO if result["ok"] else logging.ERROR
    logger.log(level, "Restore drill %s: %s", "passed" if result["ok"] else "FAILED", result)
    try:
        _drill_status_path().parent.mkdir(parents=True, exist_ok=True)
        _drill_status_path().write_text(json.dumps(result, indent=2), encoding="utf-8")
    except OSError:
        pass
    return result


def drill_due(now: datetime) -> bool:
    status = drill_status()
    if not status or not status.get("at"):
        return True
    try:
        last = datetime.fromisoformat(status["at"])
    except ValueError:
        return True
    # A failed drill is retried daily rather than weekly.
    return now - last >= (DRILL_EVERY if status.get("ok") else timedelta(days=1))


def prune_orphan_dumps(backups_dir: Path, keep_daily: int, keep_manual: int) -> int:
    """Retention by filename on disk, independent of the database records.

    After a restore, ``backup_records`` describes an older state and newer
    dump files would otherwise never be pruned. Keeps the newest
    ``keep_*`` files per kind (by name = timestamp); also removes stale
    ``.tmp`` leftovers from interrupted copies.
    """
    removed = 0
    for kind, keep in (("auto", keep_daily), ("manual", keep_manual)):
        files = sorted(backups_dir.glob(f"clinic_{kind}_*.dump"), key=lambda p: p.name, reverse=True)
        for stale in files[max(keep, 1):]:
            try:
                stale.unlink()
                removed += 1
            except OSError:
                continue
    for tmp in backups_dir.glob("*.tmp"):
        try:
            if now_tz().timestamp() - tmp.stat().st_mtime > 3600:
                tmp.unlink()
        except OSError:
            continue
    return removed
