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


def _ensure_local_postgres() -> str:
    """Start/attach the bundled local PostgreSQL and return a database URL."""
    global _pgserver_db
    import pgserver  # pyright: ignore[reportMissingImports]

    settings = get_settings()
    pgdata = Path(settings.data_dir) / "pgdata"
    pgdata.parent.mkdir(parents=True, exist_ok=True)
    _pgserver_db = pgserver.get_server(str(pgdata), cleanup_mode=None)
    uri = _pgserver_db.get_uri()
    logger.info("Bundled local PostgreSQL ready (%s)", _pgserver_db.pgdata)
    return uri


def _configured_url() -> str:
    settings = get_settings()
    url = settings.database_url or os.environ.get("DATABASE_URL", "")
    if url:
        return url
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
    return str(url.set(database=dbname))


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
    """FastAPI dependency: one transactional scope per request."""
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
