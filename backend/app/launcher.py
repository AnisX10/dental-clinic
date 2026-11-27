"""HKN Dentaire - Standalone Application Launcher.

Zero-configuration launcher that provides:
1. Relocatable portable runtime compatibility.
2. Port collision & race condition management (graceful [Errno 10048] handling).
3. Database migrations on cold start; production accounts are created by the installer.
4. Automatic application browser/window launch on ready.
"""
import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.logging_setup import configure_logging  # noqa: E402

if not os.environ.get("PYTEST_CURRENT_TEST"):
    configure_logging(PROJECT_ROOT / "data" / "logs")
logger = logging.getLogger("clinic.launcher")


def is_port_listening(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, OSError):
        return False


def is_clinic_healthy(port: int, timeout: float = 1.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clinic-launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_pids_on_port(port: int) -> list[int]:
    """PIDs of processes listening on the port (best effort)."""
    ps_cmd = (
        f"$c = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue; "
        "if ($c) { $c | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { $_ } }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd], timeout=6, capture_output=True, text=True
        )
        return [int(tok) for tok in proc.stdout.split() if tok.strip().lstrip("-").isdigit() and int(tok) > 0]
    except Exception:
        return []


def _pid_matches_our_app(pid: int) -> bool:
    """True when the process was started by this application (not a stranger)."""
    root_marker = str(PROJECT_ROOT)
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
            ],
            timeout=6, capture_output=True, text=True,
        )
        cmdline = (proc.stdout or "").strip()
        if not cmdline:
            return False
        # Only THIS install's launcher counts: another clinic program or a
        # second HKN install on the same port must never be killed.
        own_launcher = str(Path(root_marker) / "backend" / "app" / "launcher.py").lower()
        return own_launcher in cmdline.lower().replace("/", "\\")
    except Exception:
        return False


def kill_process_on_port(port: int) -> bool:
    """Terminate ONLY processes that belong to this application on the port.

    A foreign process (another service, another tool on port 8000) is NEVER
    killed: the launcher reports a clear error instead. Returns True when the
    port was freed (or already free) and safe to bind.
    """
    pids = list_pids_on_port(port)
    if not pids:
        return True
    ours: list[int] = []
    foreign: list[int] = []
    for pid in pids:
        (ours if _pid_matches_our_app(pid) else foreign).append(pid)
    for pid in foreign:
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').Name"],
                timeout=6, capture_output=True, text=True)
            name = (proc.stdout or "").strip()
        except Exception:
            name = "?"
        logger.error(
            "Port %d is occupied by another program (%s, PID %d). Please close that program, "
            "or change \"port\" in data\\config.json before starting again.",
            port, name or "unknown", pid,
        )
    for pid in ours:
        logger.info("Stopping leftover HKN Dentaire process %d on port %d...", pid, port)
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Stop-Process -Id {pid} -Force -ErrorAction Stop"], timeout=6, capture_output=True
            )
        except Exception as exc:
            logger.warning("Could not stop leftover process %d: %s", pid, exc)
    time.sleep(0.8)
    return not list_pids_on_port(port)


def find_app_browser() -> str | None:
    """Find Microsoft Edge or Google Chrome for clean borderless --app mode."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramW6432%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramW6432%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None


def open_browser(port: int, as_app: bool = True) -> None:
    url = f"http://127.0.0.1:{port}"
    if as_app:
        browser = find_app_browser()
        if browser:
            try:
                subprocess.Popen([browser, f"--app={url}"])
                return
            except Exception:
                pass
    webbrowser.open(url)


def schedule_browser_open(port: int, as_app: bool = True, max_wait: float = 30.0) -> None:
    def _poll_and_open():
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if is_clinic_healthy(port, timeout=0.5):
                logger.info("Server is ready on port %d. Opening application...", port)
                time.sleep(0.3)
                open_browser(port, as_app=as_app)
                return
            time.sleep(0.4)
        logger.warning("Server did not become healthy within %d seconds.", int(max_wait))

    threading.Thread(target=_poll_and_open, daemon=True).start()


def ensure_database_bootstrapped() -> None:
    """Migrate the database and refuse startup until production has an owner."""
    from sqlalchemy import select

    from app.core.db import dispose_engine, get_session_factory
    from app.core.models import User
    from app.core.schema import migrate_to_head

    try:
        # Backs up first whenever a migration is needed (after an update).
        migrate_to_head()
        logger.info("Database schema is up to date.")
    except Exception as exc:
        logger.error("Database migration error: %s", exc)
        raise

    try:
        factory = get_session_factory()
        from sqlalchemy import func
        with factory() as db:
            owner_count = db.execute(
                select(func.count(User.id)).where(User.is_owner.is_(True))
            ).scalar() or 0
            if owner_count == 0:
                raise RuntimeError(
                    "No clinic owner account exists. Run scripts\\install.bat or "
                    "backend\\app\\cli.py init-prod to finish setup."
                )
    except Exception as exc:
        logger.error("Database bootstrap failed: %s", exc)
        raise
    finally:
        dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description="HKN Dentaire Server Launcher")
    parser.add_argument(
        "--host", default=None,
        help="Interface to bind (default: from data/config.json: 127.0.0.1, or 0.0.0.0 when LAN is enabled)",
    )
    parser.add_argument("--port", type=int, default=None, help="Port (default: from data/config.json, else 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")
    parser.add_argument("--browser-only", action="store_true", help="Plain browser tab instead of app window")
    parser.add_argument("--no-pause", action="store_true", help="Ignored flag for compatibility with batch scripts")
    args = parser.parse_args()

    from app.core.runtime_config import load_runtime_config

    runtime_cfg = load_runtime_config()
    port = args.port or runtime_cfg.port
    host = args.host or runtime_cfg.bind_host
    as_app = not args.browser_only

    logger.info(
        "Starting HKN Dentaire launcher (port %d, %s)...",
        port, "network access enabled" if host != "127.0.0.1" else "this PC only",
    )

    # 1. Pre-flight check: is port already occupied?
    if is_port_listening("127.0.0.1", port):
        if is_clinic_healthy(port):
            logger.info("HKN Dentaire is ALREADY running on http://127.0.0.1:%d!", port)
            if not args.no_browser:
                open_browser(port, as_app=as_app)
            return 0
        logger.warning("Port %d is occupied by an unresponsive process. Cleaning up...", port)
        if not kill_process_on_port(port):
            logger.error("Could not free port %d. Start aborted (see messages above).", port)
            return 1
        time.sleep(0.5)

    # 2. Ensure database schema & initial account
    ensure_database_bootstrapped()

    # 3. Schedule browser opening upon server ready
    if not args.no_browser:
        schedule_browser_open(port, as_app=as_app)

    # 4. Start uvicorn server with graceful collision recovery
    import uvicorn

    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        lifespan="on",
        # Keep our rotating file handler: uvicorn must not replace logging.
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except (OSError, SystemExit) as exc:
        time.sleep(0.5)
        if is_clinic_healthy(port):
            logger.info("HKN Dentaire is active and healthy on port %d. Exiting launcher cleanly.", port)
            if not args.no_browser:
                open_browser(port, as_app=as_app)
            return 0
        if isinstance(exc, OSError):
            logger.error("Failed to start server: %s", exc)
            return 1
        code = exc.code if isinstance(exc, SystemExit) else 1
        if code != 0:
            logger.error("Server exited with code %s", code)
            return int(code) if isinstance(code, int) else 1
        return 0
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
