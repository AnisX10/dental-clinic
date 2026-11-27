"""Persistent, size-capped logs: ``data/logs/server.log`` (+ .1 … .9).

The server normally runs hidden (tray app / start_silent.vbs), so console
output is lost; support needs a file. 5 MB x 10 files caps disk use at ~50 MB
for years of operation.
"""
import logging
import logging.handlers
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_configured = False


def configure_logging(logs_dir: Path | None = None, *, console: bool = True) -> Path | None:
    """Idempotent: root logger -> rotating file (+ console). Returns the log path."""
    global _configured
    root = logging.getLogger()
    if _configured:
        return None
    if logs_dir is None:
        from app.core.config import get_settings

        logs_dir = Path(get_settings().data_dir) / "logs"
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(_FORMAT)
    path = None
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        path = logs_dir / "server.log"
        fh = logging.handlers.RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=9, encoding="utf-8", delay=True
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as exc:  # read-only / missing folder: keep console logging
        logging.getLogger("clinic").warning("File logging disabled (%s)", exc)
    if console and not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    # Health probes every 1.5 s would flood the log.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _configured = True
    return path


def rotate_postgres_log(pgdata: Path, max_bytes: int = 10 * 1024 * 1024) -> None:
    """Trim pgserver's ``pgdata/log`` (written via ``pg_ctl -l``) at start-up.

    Only called while PostgreSQL is not running (the file is then not open).
    """
    log = pgdata / "log"
    try:
        if log.is_file() and log.stat().st_size > max_bytes:
            old = pgdata / "log.old"
            old.unlink(missing_ok=True)
            log.rename(old)
    except OSError as exc:
        logging.getLogger("clinic").warning("Could not rotate %s: %s", log, exc)
