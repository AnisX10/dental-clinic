"""Database engine/session setup + local PostgreSQL bootstrap.

If `CLINIC_DATABASE_URL` is not configured, the app uses the bundled,
admin-free local PostgreSQL provided by `pgserver` (PostgreSQL 16 binaries,
data stored under `data/pgdata`). A native PostgreSQL installation on the
server PC works identically: just set CLINIC_DATABASE_URL.
"""
import logging
import os
import threading
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("clinic")

_engine = None
_SessionLocal = None
_db_lock = threading.Lock()
_pgserver_db = None  # keep a reference so pgserver does not stop the server


def unsupported_path_chars(path: Path) -> str:
    """Non-ASCII characters in ``path`` ("" when the path is safe).

    PostgreSQL's Windows binaries read their own install path through the ANSI
    code page and then feed it to SQL as UTF-8: initdb fails ("invalid byte
    sequence for encoding UTF8") when the bundled binaries live under e.g.
    ``C:\\Users\\Amélie\\...`` or ``C:\\Users\\محمد\\...``. Verified on Windows
    11 / cp1252 with pgserver 0.1.4. Only enforced on Windows.
    """
    if os.name != "nt":
        return ""
    bad = []
    for ch in str(path):
        if ord(ch) > 127 and ch not in bad:
            bad.append(ch)
    return "".join(bad)


def remove_stale_postmaster_pid(pgdata: Path) -> bool:
    """Delete ``postmaster.pid`` unless it belongs to a live postgres process.

    After a power cut the pid file survives, and after reboot Windows often
    gives that PID to an unrelated program. pgserver only checks that the PID
    exists, so it would "attach" to a server that isn't running and the app
    could not start. Keep the file only when the PID is a ``postgres`` process
    started no later than the file was written. Returns True if removed.
    """
    pid_file = pgdata / "postmaster.pid"
    if not pid_file.is_file():
        return False
    try:
        first = pid_file.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        mtime = pid_file.stat().st_mtime
    except OSError as exc:
        logger.warning("Cannot read %s: %s", pid_file, exc)
        return False
    token = first[0].strip() if first else ""
    reason = None
    if not token.isdigit():
        reason = "unreadable PID"
    else:
        import psutil

        pid = int(token)
        try:
            proc = psutil.Process(pid)
            name = (proc.name() or "").lower()
            if not name.startswith("postgres"):
                reason = f"PID {pid} now belongs to {name!r}"
            elif proc.create_time() > mtime + 2:
                reason = f"PID {pid} is a postgres process started after the pid file"
        except psutil.NoSuchProcess:
            reason = f"PID {pid} is dead"
        except (psutil.AccessDenied, OSError) as exc:
            # Can't inspect it: leave the file and let pgserver decide.
            logger.warning("Cannot inspect PID %s from %s: %s", pid, pid_file, exc)
            return False
    if reason is None:
        return False  # a live postgres owns it: pgserver will attach to it
    logger.warning("Removing stale postmaster.pid (%s)", reason)
    try:
        pid_file.unlink(missing_ok=True)
    except OSError as exc:
        logger.error("Could not remove stale %s: %s", pid_file, exc)
        return False
    return True


def _ensure_local_postgres() -> str:
    """Start/attach the bundled local PostgreSQL and return a database URL."""
    global _pgserver_db
    try:
        import pgserver  # pyright: ignore[reportMissingImports]
    except ImportError:
        import sys
        err_msg = (
            f"Python {sys.version_info.major}.{sys.version_info.minor} detecte. "
            "Le moteur de base de donnees embarque sans installation (pgserver) necessite Python 3.11. "
            "Veuillez installer Python 3.11 (par exemple python-3.11.9-amd64.exe) ou configurer CLINIC_DATABASE_URL."
        )
        logger.critical(err_msg)
        raise RuntimeError(err_msg) from None

    settings = get_settings()
    pgdata = Path(settings.data_dir) / "pgdata"
    for path in (Path(pgserver.__file__).resolve().parent, pgdata):
        bad = unsupported_path_chars(path)
        if bad:
            msg = (
                f"Le dossier d'installation contient des caracteres non pris en charge ({bad}) : {path}. "
                "La base de donnees ne peut pas demarrer depuis ce dossier. "
                "Reinstallez HKN Dentaire dans C:\\HKN Dentaire."
            )
            logger.critical(msg)
            raise RuntimeError(msg)
    pgdata.parent.mkdir(parents=True, exist_ok=True)

    remove_stale_postmaster_pid(pgdata)
    if not (pgdata / "postmaster.pid").exists():
        # PostgreSQL is about to be started: its stdout log isn't open yet.
        from app.core.logging_setup import rotate_postgres_log

        rotate_postgres_log(pgdata)

    _pgserver_db = pgserver.get_server(str(pgdata), cleanup_mode=None)
    from app.core.pg_security import secure_local_postgres

    uri = secure_local_postgres(
        Path(_pgserver_db.pgdata), _pgserver_db.get_uri(), Path(settings.data_dir) / "pg_secret"
    )
    logger.info("Bundled local PostgreSQL ready (%s)", _pgserver_db.pgdata)
    _ensure_postgres_log_rotation(uri)
    return uri


def _ensure_postgres_log_rotation(uri: str) -> None:
    """Let PostgreSQL rotate its own log: one file per weekday in
    ``pgdata/pg_log``, overwritten each week, 10 MB max each. Takes effect at
    the next PostgreSQL restart (``logging_collector`` needs one)."""
    try:
        probe = create_engine(uri, isolation_level="AUTOCOMMIT")
        with probe.connect() as conn:
            if conn.execute(text("SHOW log_directory")).scalar() == "pg_log":
                probe.dispose()
                return
            for stmt in (
                "ALTER SYSTEM SET logging_collector = on",
                "ALTER SYSTEM SET log_directory = 'pg_log'",
                "ALTER SYSTEM SET log_filename = 'postgresql-%a.log'",
                "ALTER SYSTEM SET log_truncate_on_rotation = on",
                "ALTER SYSTEM SET log_rotation_age = '1d'",
                "ALTER SYSTEM SET log_rotation_size = '10MB'",
            ):
                conn.execute(text(stmt))
            conn.execute(text("SELECT pg_reload_conf()"))
        probe.dispose()
        logger.info("PostgreSQL log rotation configured (active after next restart)")
    except Exception as exc:  # never block start-up over logging
        logger.warning("Could not configure PostgreSQL log rotation: %s", exc)


def _configured_url() -> str:
    settings = get_settings()
    url = settings.database_url or os.environ.get("DATABASE_URL", "")
    if url:
        return url
    # Deterministic default: bundled local PostgreSQL (data/pgdata).
    # A native PostgreSQL must be selected explicitly via CLINIC_DATABASE_URL.
    local = _ensure_local_postgres()
    # Own dedicated database instead of the default `postgres` one.
    return _ensure_database(local, "clinic")


def _ensure_database(server_uri: str, dbname: str) -> str:
    """Create the application database if missing; return its URL."""
    from sqlalchemy.engine import make_url

    url = make_url(server_uri)
    if url.database == dbname:
        return server_uri
    admin_url = url.set(database="postgres")
    probe = create_engine(admin_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    with probe.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    probe.dispose()
    # render_as_string: str(url) would mask the password as "***".
    return url.set(database=dbname).render_as_string(hide_password=False)


def get_engine():
    global _engine, _SessionLocal
    with _db_lock:
        if _engine is None:
            url = _configured_url()
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                connect_args={"application_name": "clinic_app"},
            )
            _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
        return _engine


def get_session_factory() -> sessionmaker:
    get_engine()
    if _SessionLocal is None:  # pragma: no cover - get_engine() always sets it
        raise RuntimeError("session factory missing after engine bootstrap")
    return _SessionLocal


def dispose_engine() -> None:
    global _engine, _SessionLocal
    with _db_lock:
        if _engine is not None:
            _engine.dispose()
            _engine = None
            _SessionLocal = None


def get_db():
    """FastAPI dependency: one transactional scope per request.

    Always use it as ``Depends(get_db, scope="function")``. With the default
    request scope FastAPI runs this commit *after* the response has been sent,
    so a failed commit would reach the client as a success.
    """
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


_RECOVERY_INTERVAL = 30.0
_last_recovery = 0.0
_recovery_lock = threading.Lock()


def recover_local_postgres() -> bool:
    """Try to bring the bundled PostgreSQL back after it died (antivirus,
    manual kill, crash). Throttled; returns True if the database answers again.

    pgserver re-reads ``postmaster.pid`` and restarts the server (possibly on a
    new port); the engine is then rebuilt so the new URL is used.
    """
    global _last_recovery
    import time

    if _pgserver_db is None:
        return False  # external PostgreSQL: nothing we can restart
    with _recovery_lock:
        now = time.monotonic()
        if now - _last_recovery < _RECOVERY_INTERVAL:
            return False
        _last_recovery = now
        logger.error("Database is not answering: trying to restart the bundled PostgreSQL")
        try:
            remove_stale_postmaster_pid(_pgserver_db.pgdata)
            _pgserver_db.ensure_postgres_running()
        except Exception:
            logger.exception("Could not restart the bundled PostgreSQL")
            return False
    dispose_engine()
    ok = check_database()
    logger.log(logging.INFO if ok else logging.ERROR,
               "Bundled PostgreSQL recovery %s", "succeeded" if ok else "failed")
    return ok


def database_healthy() -> bool:
    """Health probe: check, and attempt one in-process recovery if down."""
    return check_database() or recover_local_postgres()
