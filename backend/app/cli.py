"""CLI: create users, seed catalog, run migrations."""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import dispose_engine, get_session_factory  # noqa: E402
from app.core.services import create_user, get_settings_row, seed_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Clinic administration CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_user = sub.add_parser("create-user", help="Create a clinic user")
    p_user.add_argument("--username", required=True)
    p_user.add_argument("--role", required=True, choices=["dentiste", "reception"])
    p_user.add_argument("--full-name", default="")
    p_user.add_argument("--owner", action="store_true", help="Grant owner-level privileges")
    p_user.add_argument("--password", default="", help="Password (prompted if omitted)")

    p_seed = sub.add_parser("seed-catalog", help="Insert default treatment catalog")
    p_seed.add_argument("--migrate", action="store_true", help="Run migrations first")

    p_restore = sub.add_parser("restore", help="Restore the database from a backup dump")
    p_restore.add_argument("--backup", required=True, help="Path to the .dump file")
    p_restore.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    return _run(parser.parse_args())


def _run(args) -> int:
    if getattr(args, "migrate", False):
        _run_migrations()

    if args.command == "restore":
        return _restore(Path(args.backup), assume_yes=args.yes)

    db = get_session_factory()()
    try:
        if args.command == "create-user":
            password = args.password or getpass.getpass("Password (min 8 chars): ")
            user = create_user(
                db,
                username=args.username,
                password=password,
                full_name=args.full_name,
                role=args.role,
                is_owner=args.owner,
            )
            db.commit()
            label = f"{user.role}" + (" +owner" if user.is_owner else "")
            print(f"User created: {user.username} ({label})")
        elif args.command == "seed-catalog":
            get_settings_row(db)
            count = seed_catalog(db)
            db.commit()
            print(f"Catalog ready ({count} treatments added).")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
        dispose_engine()


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "migrations"))
    command.upgrade(cfg, "head")


def _restore(backup_path: Path, *, assume_yes: bool) -> int:
    """Restore a pg_dump custom-format backup into the clinic database.

    Drops and recreates the public schema, then pg_restore. The app must be
    stopped while restoring (connections would block the drop).
    """
    if not backup_path.is_file():
        print(f"Error: backup file not found: {backup_path}", file=sys.stderr)
        return 1
    if not assume_yes:
        answer = input(
            f"This will ERASE all current data and restore {backup_path.name}. Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 1

    from app.backup.service import _pg_dump_path
    from app.core.db import get_engine

    url = get_engine().url
    bin_dir = _pg_dump_path()
    pg_restore = str(Path(bin_dir) / "pg_restore") if bin_dir else "pg_restore"
    import subprocess

    cmd = [
        pg_restore,
        "--clean",
        "--if-exists",
        "--dbname=" + url.render_as_string(hide_password=False),
        str(backup_path),
    ]
    env = {
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
        "PGHOST": url.host or "127.0.0.1",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "postgres",
        "PGPASSWORD": url.password or "",
    }
    print("Restoring...")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    if proc.returncode != 0:
        # --clean reports non-zero when dropping objects that exist only in
        # the dump target; treat "does not exist" noise as non-fatal.
        fatal = [
            line for line in (proc.stderr or "").splitlines()
            if "does not exist" not in line and line.strip()
        ]
        if fatal:
            print("Restore failed:", file=sys.stderr)
            print("\n".join(fatal[:10]), file=sys.stderr)
            return 1
    print(f"Restore complete from {backup_path.name}.")
    print("Start the application normally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
