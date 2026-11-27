"""Schema migrations with a safety backup first.

Single entry point used by the launcher, the API startup and ``cli.py upgrade``
so that an update never changes the database without a fresh backup.
"""
import logging
from pathlib import Path

logger = logging.getLogger("clinic")

BACKEND_DIR = Path(__file__).resolve().parents[2]


class SchemaError(RuntimeError):
    """The database cannot be brought to this software's schema safely."""


def alembic_config():
    from alembic.config import Config

    ini = BACKEND_DIR / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["configure_logger"] = False
    return cfg


def schema_revisions() -> tuple[str | None, set[str], set[str]]:
    """Return (current DB revision, head revisions, all known revisions)."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    from app.core.db import get_engine

    script = ScriptDirectory.from_config(alembic_config())
    heads = set(script.get_heads())
    known = {rev.revision for rev in script.walk_revisions()}
    with get_engine().connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    return current, heads, known


def migrate_to_head(*, backup_first: bool = True) -> bool:
    """Upgrade the schema to head. Returns True if a migration ran.

    - Empty database (fresh install): migrate, no backup needed.
    - Already at head: nothing to do.
    - Database stamped with a revision this software doesn't know (made by a
      newer version): refuse, so an old installer never damages new data.
    - Otherwise: take a ``manual`` pre-upgrade backup and abort if it fails.
    """
    from alembic import command

    current, heads, known = schema_revisions()
    if current is not None and current in heads:
        return False
    if current is not None and current not in known:
        raise SchemaError(
            f"Database revision {current} is unknown to this version of the software "
            "(it was probably created by a newer version). Install the latest version "
            "or restore a matching backup."
        )
    if current is not None and backup_first:
        from app.backup.service import run_backup
        from app.core.db import get_session_factory

        logger.info("Database schema %s is behind %s: taking a pre-upgrade backup", current, heads)
        with get_session_factory()() as db:
            try:
                record = run_backup(db, kind="manual", reason="pre-upgrade")
                db.commit()
            except Exception as exc:
                db.rollback()
                raise SchemaError(
                    f"Pre-upgrade backup failed, database left unchanged: {exc}"
                ) from exc
        logger.info("Pre-upgrade backup saved: %s", Path(record.file_path).name)
    try:
        command.upgrade(alembic_config(), "head")
    except Exception:
        logger.exception("Migration failed")
        raise
    logger.info("Database schema upgraded to head")
    return True
