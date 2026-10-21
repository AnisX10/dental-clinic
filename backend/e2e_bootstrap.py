"""Recreate the e2e sandbox database (clinic_e2e by default) and seed it.

Invoked automatically by the Playwright globalSetup. Schema migrations are
applied by the uvicorn startup hook once the webServer boots; this script only
recreates the database, seeds the treatment catalog and creates the login.

Manual run (from backend/ or repo root):
    .venv\\Scripts\\python.exe backend\\e2e_bootstrap.py
"""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/clinic_e2e"
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", "E2e-Pass-2026")


def main() -> None:
    url = make_url(os.environ.get("CLINIC_DATABASE_URL", DEFAULT_URL))
    admin = create_engine(str(url.set(database="postgres")), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        # FORCE (PG 13+) ends sessions from an orphaned server of a crashed
        # previous run before dropping.
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    print(f"e2e database ready: {url.database}")

    env = {**os.environ, "CLINIC_DATABASE_URL": str(url)}
    cli = str(BACKEND_DIR / "app" / "cli.py")
    # --migrate applies schema first: the database exists but has no tables
    # yet (migrations normally run at uvicorn startup, which happens later).
    subprocess.run(
        [sys.executable, cli, "seed-catalog", "--migrate"],
        check=True,
        cwd=BACKEND_DIR,
        env=env,
    )
    subprocess.run(
        [
            sys.executable, cli, "create-user",
            "--username", "owner",
            "--role", "dentiste",
            "--owner",
            "--full-name", "E2E Owner",
            "--password", E2E_PASSWORD,
        ],
        check=True,
        cwd=BACKEND_DIR,
        env=env,
    )

    # License: the lockout middleware would block every API call. Issue a real
    # one for this fresh installation with the vendor signing key (kept out of
    # git). One-time setup by the seller: tools/license.py keygen.
    lic_target = os.environ.get("CLINIC_LICENSE_FILE")
    private_key = Path(
        os.environ.get("CLINIC_LICENSE_PRIVATE_KEY", str(BACKEND_DIR.parent / "tools" / "license" / "private.pem"))
    )
    if not lic_target:
        print("CLINIC_LICENSE_FILE not set: e2e runs LOCKED (expected to fail).", file=sys.stderr)
    else:
        if not private_key.exists():
            print(
                "Missing signing key for e2e licenses.\n"
                "Run once: .venv\\Scripts\\python.exe tools\\license.py keygen\n"
                f"(expected at {private_key})",
                file=sys.stderr,
            )
            sys.exit(1)
        sys.path.insert(0, str(BACKEND_DIR))
        from app.licensing import service as lic

        install_id = lic.installation_getter()
        subprocess.run(
            [
                sys.executable,
                str(BACKEND_DIR.parent / "tools" / "license.py"),
                "issue",
                "--clinic", "Clinique E2E",
                "--dentist", "Dr E2E",
                "--installation", install_id,
                "--out", lic_target,
                "--private", str(private_key),
            ],
            check=True,
            cwd=BACKEND_DIR,
            env=env,
        )
        print(f"e2e license written: {lic_target}")


if __name__ == "__main__":
    main()
