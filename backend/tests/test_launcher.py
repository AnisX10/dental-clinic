"""Launcher logging: support log file, quiet console, Windows disconnect noise."""
import logging


def test_configure_logging_writes_file_and_quiets_libraries(tmp_path, monkeypatch):
    from app import launcher
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        log_file = launcher.configure_logging()
        assert log_file == tmp_path / "logs" / launcher.LOG_FILENAME
        logging.getLogger("clinic").info("hello support")
        for h in root.handlers:
            h.flush()
        assert "hello support" in log_file.read_text(encoding="utf-8")
        assert logging.getLogger("alembic").level == logging.WARNING
        assert logging.getLogger("pgserver").level == logging.WARNING
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
        for h in saved:
            root.addHandler(h)
        for name in launcher._CHATTY_LOGGERS:
            logging.getLogger(name).setLevel(logging.NOTSET)


def test_client_disconnect_tracebacks_are_dropped():
    from app.launcher import _DropClientDisconnects

    f = _DropClientDisconnects()
    try:
        raise ConnectionResetError(10054, "An existing connection was forcibly closed")
    except ConnectionResetError:
        import sys

        rec = logging.LogRecord("asyncio", logging.ERROR, __file__, 1, "Exception in callback", None, sys.exc_info())
    assert f.filter(rec) is False
    ok = logging.LogRecord("asyncio", logging.ERROR, __file__, 1, "real problem", None, None)
    assert f.filter(ok) is True
