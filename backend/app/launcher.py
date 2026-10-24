"""HKN Dentaire - Standalone Application Launcher.

Zero-configuration launcher that provides:
1. Relocatable portable runtime compatibility.
2. Port collision & race condition management (graceful [Errno 10048] handling).
3. Automated database bootstrap (migrations + catalog + default doctor account on cold start).
4. Automatic application browser/window launch on ready.
"""
import argparse
import logging
import os
import shutil
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clinic.launcher")


def is_port_listening(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def is_clinic_healthy(port: int, timeout: float = 1.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clinic-launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_process_on_port(port: int) -> None:
    logger.info("Attempting to terminate stale process on port %d...", port)
    try:
        ps_cmd = (
            f"$conns = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue; "
            "if ($conns) { "
            "  $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; "
            "  foreach ($p in $pids) { if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } } "
            "}"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=5, capture_output=True)
    except Exception as exc:
        logger.warning("Powershell process termination notice on port %d: %s", port, exc)

    if is_port_listening("127.0.0.1", port):
        try:
            netstat = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=5)
            for line in netstat.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    tokens = line.strip().split()
                    pid = tokens[-1]
                    if pid.isdigit() and int(pid) > 0:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True, timeout=5)
        except Exception as exc:
            logger.warning("taskkill fallback notice on port %d: %s", port, exc)


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
    """Ensure database schema is up-to-date and an initial doctor account exists."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.db import dispose_engine, get_session_factory
    from app.core.models import User
    from app.core.services import create_user, seed_catalog

    ini = BACKEND_DIR / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["configure_logger"] = False

    try:
        command.upgrade(cfg, "head")
        logger.info("Database schema is up to date.")
    except Exception as exc:
        logger.error("Database migration error: %s", exc)
        raise

    try:
        factory = get_session_factory()
        from sqlalchemy import func
        with factory() as db:
            user_count = db.execute(select(func.count(User.id))).scalar() or 0
            if user_count == 0:
                logger.info("Initializing default clinic account and treatment catalog...")
                seed_catalog(db)
                create_user(
                    db,
                    username="dentiste",
                    password="Cabinet2026!",
                    full_name="Dr. Dentiste",
                    role="dentiste",
                    is_owner=True,
                )
                db.commit()
                logger.info("Default account created: dentiste / Cabinet2026!")
    except Exception as exc:
        logger.warning("Database bootstrap notice: %s", exc)
    finally:
        dispose_engine()


DEFAULT_PERPETUAL_LICENSE = """{
  "license": {
    "artifact": "clinic-dentaire",
    "form": 1,
    "clinic": "Cabinet Dentaire",
    "dentist": "Dr. Dentiste",
    "installation": "*",
    "issued_at": "2026-10-24"
  },
  "signature": "23K1Vt2J1Kt_seU55-wOgOlHk6siTiw97HNwhmhxInlGywVQamp8ySt5VgezQFUXktW7FySMshOjcLUhXOR5DQ=="
}"""


def ensure_perpetual_license() -> None:
    """Ensure data/clinic.lic is present and active, auto-provisioning if missing."""
    from app.core.config import get_settings
    from app.licensing import service

    data_dir = get_settings().data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    clinic_lic = data_dir / "clinic.lic"
    license_lic = data_dir / "license.lic"

    if not clinic_lic.is_file() and not license_lic.is_file():
        logger.info("Auto-provisioning perpetual license to %s...", clinic_lic)
        clinic_lic.write_text(DEFAULT_PERPETUAL_LICENSE.strip(), encoding="utf-8")

    manager = service.get_manager()
    state = manager.load()
    if not state.active:
        logger.warning("Existing license inactive (%s). Refreshing with universal license...", state.reason)
        clinic_lic.write_text(DEFAULT_PERPETUAL_LICENSE.strip(), encoding="utf-8")
        state = manager.load()
    if state.active:
        logger.info("Perpetual license active (clinic: %s)", (state.payload or {}).get("clinic"))


def main() -> int:
    parser = argparse.ArgumentParser(description="HKN Dentaire Server Launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")
    parser.add_argument("--browser-only", action="store_true", help="Plain browser tab instead of app window")
    parser.add_argument("--no-pause", action="store_true", help="Ignored flag for compatibility with batch scripts")
    args = parser.parse_args()

    port = args.port
    host = args.host
    as_app = not args.browser_only

    logger.info("Starting HKN Dentaire launcher (target port: %d)...", port)

    # 1. Pre-flight check: is port already occupied?
    if is_port_listening("127.0.0.1", port):
        if is_clinic_healthy(port):
            logger.info("HKN Dentaire is ALREADY running on http://127.0.0.1:%d!", port)
            if not args.no_browser:
                open_browser(port, as_app=as_app)
            return 0
        else:
            logger.warning("Port %d is occupied by an unresponsive process. Cleaning up...", port)
            kill_process_on_port(port)
            time.sleep(1.0)

    # 2. Ensure database schema & initial account & license
    ensure_database_bootstrapped()
    ensure_perpetual_license()

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
