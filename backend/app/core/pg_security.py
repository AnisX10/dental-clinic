"""Password-protect the bundled PostgreSQL.

pgserver runs ``initdb --auth=trust``: any program on the PC (or another
Windows account) could connect to 127.0.0.1 as superuser and read or drop
the medical records. On first start we set a random superuser password,
store it in ``data/pg_secret`` (ACL restricted to the current Windows user)
and switch ``pg_hba.conf`` to ``scram-sha-256``.

Self-healing: if the secret is lost or no longer matches, ``pg_hba.conf`` is
put back to ``trust`` (we own the data directory), the server is reloaded
and a new secret is set. A lost file can never lock the clinic out.
"""
import logging
import os
import secrets
import subprocess
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

logger = logging.getLogger("clinic")

MARKER = "# HKN Dentaire: password authentication (managed automatically)"

_HBA_TRUST = """# HKN Dentaire: temporary trust while the password is (re)set
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
"""

_HBA_SECURE = MARKER + """
# Only this PC (127.0.0.1) and only with the password in data/pg_secret.
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
"""


def _with_password(uri: str, password: str | None) -> str:
    return make_url(uri).set(password=password).render_as_string(hide_password=False)


def _can_connect(uri: str) -> bool:
    engine = create_engine(uri, pool_pre_ping=False, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()


def _reload(pgdata: Path) -> None:
    from pgserver._commands import pg_ctl  # pyright: ignore[reportMissingImports]

    pg_ctl(["reload"], pgdata=pgdata)


def _write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _restrict_to_current_user(path: Path) -> None:
    if os.name != "nt":
        os.chmod(path, 0o600)
        return
    user = os.environ.get("USERNAME", "")
    if not user:
        return
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not restrict %s: %s", path, exc)


def _wait_until(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.3)
    return predicate()


def secure_local_postgres(pgdata: Path, trust_uri: str, secret_file: Path) -> str:
    """Return a connection URI that carries the password (see module doc).

    Never raises: on any failure the server is left in trust mode and the
    password-less URI is returned, so the clinic keeps working.
    """
    hba = pgdata / "pg_hba.conf"
    try:
        hardened = MARKER in hba.read_text(encoding="utf-8", errors="replace")
        secret = secret_file.read_text(encoding="utf-8").strip() if secret_file.is_file() else ""
        if hardened and secret and _can_connect(_with_password(trust_uri, secret)):
            return _with_password(trust_uri, secret)

        if hardened:
            logger.warning("Database password missing or invalid: resetting it")
            _write(hba, _HBA_TRUST)
            _reload(pgdata)
            if not _wait_until(lambda: _can_connect(trust_uri)):
                raise RuntimeError("server did not return to trust mode")

        secret = secrets.token_hex(24)  # [0-9a-f] only: safe inside SQL quotes
        engine = create_engine(trust_uri, isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                conn.execute(text("SET password_encryption = 'scram-sha-256'"))
                user = conn.execute(text("SELECT current_user")).scalar()
                conn.execute(text(f"ALTER ROLE \"{user}\" WITH PASSWORD '{secret}'"))
        finally:
            engine.dispose()
        _write(secret_file, secret + "\n")
        _restrict_to_current_user(secret_file)

        _write(hba, _HBA_SECURE)
        _reload(pgdata)
        secure_uri = _with_password(trust_uri, secret)
        if _wait_until(lambda: _can_connect(secure_uri) and not _can_connect(trust_uri)):
            logger.info("Bundled PostgreSQL is now password-protected")
            return secure_uri
        if _can_connect(secure_uri):
            return secure_uri  # password works; trust check raced the reload
        raise RuntimeError("password authentication could not be verified")
    except Exception as exc:
        logger.error("Could not password-protect the database (%s); continuing without", exc)
        try:
            if MARKER in hba.read_text(encoding="utf-8", errors="replace"):
                _write(hba, _HBA_TRUST)
                _reload(pgdata)
        except Exception:
            logger.exception("Could not restore trust authentication")
        return trust_uri
