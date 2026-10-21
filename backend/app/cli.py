"""CLI: create users, seed catalog, run migrations."""
import argparse
import getpass
import string
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

    sub.add_parser("version", help="Show application version and schema revision")
    sub.add_parser("upgrade", help="Safe upgrade: backup, migrate, rebuild frontend, then restart manually")

    p_drill = sub.add_parser("drill", help="Prove the newest backup restores: test it in a throwaway database")
    p_drill.add_argument("--backup", default="", help="Use this dump file instead of the newest successful one")
    p_drill.add_argument("--keep", action="store_true", help="Keep the scratch database (clinic_drill) for inspection")

    p_init = sub.add_parser("init-prod", help="Prepare a production database: schema, catalog, first owner + security audit")
    p_init.add_argument("--username", default="", help="First owner username (prompted if omitted)")
    p_init.add_argument("--password", default="", help="Password (prompted twice if omitted)")
    p_init.add_argument("--full-name", default="", help="Full name (prompted if omitted)")
    p_init.add_argument("--force", action="store_true", help="Proceed even if demo users are present")

    return _run(parser.parse_args())


def _run(args) -> int:
    if args.command == "version":
        return _version()

    if args.command == "upgrade":
        return _upgrade()

    if args.command == "drill":
        return _drill(args.backup or None, keep=args.keep)

    if args.command == "init-prod":
        return _init_prod(args)

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


def _version() -> int:
    from sqlalchemy import inspect, text

    from app.core.config import APP_VERSION
    from app.core.db import get_engine

    revision = "(fresh — no schema yet)"
    with get_engine().connect() as conn:
        if inspect(conn).has_table("alembic_version"):
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar() or revision
    print(f"Clinic Management v{APP_VERSION} — schema {revision}")
    dispose_engine()
    return 0


def _upgrade() -> int:
    import shutil
    import subprocess

    from app.core.config import APP_VERSION, FRONTEND_DIST
    from app.core.db import get_session_factory

    print(f"Upgrading to v{APP_VERSION}...")

    # 1) Pre-upgrade safety dump (skipped politely on a brand-new empty DB).
    factory = get_session_factory()
    try:
        with factory() as db:
            try:
                from app.backup.service import run_backup

                record = run_backup(db, kind="manual", reason="pre-upgrade")
                db.commit()
                print(f"Backup saved: {Path(record.file_path).name}")
            except Exception as exc:
                db.rollback()
                print(f"Skipped pre-upgrade backup: {exc}")
    finally:
        dispose_engine()

    # 2) Schema migrations.
    _run_migrations()
    print("Schema is up to date.")

    # 3) Frontend bundle (Shipped by FastAPI from frontend/.output/public).
    npm = shutil.which("npm")
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if not npm:
        print(
            "Warning: npm not found — keeping the existing frontend build at\n"
            f"  {FRONTEND_DIST}\n"
            "Install Node.js or run `npm run generate` inside frontend/ manually."
        )
        return 0
    print("Building frontend (npm run generate)...")
    proc = subprocess.run([npm, "run", "generate"], cwd=frontend_dir)
    if proc.returncode != 0:
        print("Error: frontend build failed — keep the previous bundle installed.", file=sys.stderr)
        return 1

    print(f"Upgrade complete (v{APP_VERSION}). Restart the application now (start.bat).")
    return 0


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

    from app.core.db import get_engine

    dbname = get_engine().url.database or ""
    print("Restoring...")
    fatal = _pg_restore_fatal(dbname, backup_path)
    if fatal:
        print("Restore failed:", file=sys.stderr)
        print("\n".join(fatal[:10]), file=sys.stderr)
        return 1
    print(f"Restore complete from {backup_path.name}.")
    print("Start the application normally.")
    return 0


def _pg_restore_fatal(target_db: str, backup_path: Path) -> list[str]:
    """pg_restore into target_db; returns fatal stderr lines (empty = success).

    --clean reports non-zero when dropping objects that exist only in the dump
    target; "does not exist" noise is treated as non-fatal.
    """
    import os
    import subprocess

    from app.backup.service import _pg_dump_path
    from app.core.db import get_engine

    url = get_engine().url
    bin_dir = _pg_dump_path()
    pg_restore = str(Path(bin_dir) / "pg_restore") if bin_dir else "pg_restore"

    cmd = [
        pg_restore,
        "--clean",
        "--if-exists",
        # Bare database name: libpq must not receive the SQLAlchemy driver
        # scheme (postgresql+psycopg://...) — with the driver suffix it can
        # silently connect elsewhere; host/port/user/password come from the
        # PG* environment below.
        "--dbname=" + (target_db or ""),
        str(backup_path),
    ]
    env = {
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PGHOST": url.host or "127.0.0.1",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "postgres",
        "PGPASSWORD": url.password or "",
    }
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    if proc.returncode != 0:
        return [
            line for line in (proc.stderr or "").splitlines()
            if "does not exist" not in line and line.strip()
        ]
    return []


def _drill(backup: str | None, *, keep: bool) -> int:
    """Restore-drill: load a backup into a throwaway database and count rows.

    The live database is never touched; the scratch database is dropped at the
    end unless --keep is passed.
    """
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url

    from app.core.db import dispose_engine, get_engine

    if backup:
        dump = Path(backup)
    else:
        from sqlalchemy import select

        from app.core.db import get_session_factory
        from app.core.models import BackupRecord

        dump = None
        try:
            factory = get_session_factory()
            with factory() as db:
                row = db.execute(
                    select(BackupRecord)
                    .where(BackupRecord.status == "success")
                    .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
                    .limit(1)
                ).scalar_one_or_none()
                dump = Path(row.file_path) if row else None
        finally:
            dispose_engine()
        if dump is None:
            print("No successful backup found yet — run one first (Paramètres or cli.py upgrade).", file=sys.stderr)
            return 1

    if not dump.is_file():
        print(f"Error: backup file not found: {dump}", file=sys.stderr)
        return 1

    url = make_url(get_engine().url.render_as_string(hide_password=False))
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    scratch = "clinic_drill"
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{scratch}"'))
    admin.dispose()

    print(f"Drilling {dump.name} -> {scratch} ...")
    fatal = _pg_restore_fatal(scratch, dump)
    if fatal:
        with create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT").connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
        print("Drill FAILED (restore errors):", file=sys.stderr)
        print("\n".join(fatal[:10]), file=sys.stderr)
        return 1

    drill = create_engine(url.set(database=scratch))
    wanted = ("patients", "patient_treatments", "payments", "clinical_notes",
              "documents", "attachments", "treatment_catalog", "users")
    counts: dict[str, str] = {}
    try:
        with drill.connect() as conn:
            names = set(inspect(conn).get_table_names())
            for table in wanted:
                if table in names:
                    counts[table] = str(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar())
    finally:
        drill.dispose()
        if not keep:
            with create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT").connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
    dispose_engine()

    print("DRILL PASSED: the backup restores cleanly.")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    if keep:
        print(f"Scratch database {scratch} kept for inspection.")
    else:
        print("Scratch database dropped. Your data was never touched.")
    return 0



def _demo_users_present(db) -> list[str]:
    """Usernames created by the demo/QA seeders — forbidden on production."""
    from sqlalchemy import select

    from app.core.models import User

    demos = ("drbenali", "sarah", "qa-owner")
    rows = db.execute(select(User.username).where(User.username.in_(demos))).scalars().all()
    return [row for row in rows if row is not None]


def _prod_password_problem(password: str) -> str | None:
    """Production password policy: >=10 chars, letters + digits + symbol, not a known weak one."""
    weak = {
        "password", "password123", "password-123", "password1234",
        "1234567890", "123456789a", "qwerty12345", "admin12345!",
        "clinique123", "dentaire123", "azerty12345",
    }
    if len(password) < 10:
        return f"at least 10 characters (got {len(password)})"
    if password.lower() in weak:
        return "too common / guessable"
    has = (any(c in string.ascii_letters for c in password),
           any(c.isdigit() for c in password),
           any(c in string.punctuation for c in password))
    if not all(has):
        return "must mix letters, digits and a symbol (e.g. Dr#-something-2026)"
    return None


def _init_prod(args) -> int:
    """One-shot production bootstrap: schema, catalog, first owner, audit."""
    from app.core.config import FRONTEND_DIST, get_settings
    from app.core.db import get_engine

    _run_migrations()

    username = (args.username or input("Owner username: ").strip().lower())
    full_name = args.full_name or input("Full name (e.g. Dr Benali Amine): ").strip()
    while True:
        password = args.password or getpass.getpass("Password (>=10, letters+digits+symbol): ")
        if args.password:
            problem = _prod_password_problem(password)
            if problem:
                print(f"Password rejected: {problem}", file=sys.stderr)
                return 1
            break
        problem = _prod_password_problem(password)
        if problem:
            print(f"Password rejected: {problem}")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match, try again.")
            continue
        break

    db = get_session_factory()()
    try:
        demos = _demo_users_present(db)
        if demos and not args.force:
            print(
                "This database contains DEMO accounts: " + ", ".join(demos) + "\n"
                "Never seed demo data onto production. Restore a production backup,\n"
                "recreate the database empty, or pass --force if you cleaned them up.",
                file=sys.stderr,
            )
            return 1

        user = create_user(db, username=username, password=password, full_name=full_name,
                           role="dentiste", is_owner=True)
        if not seed_catalog(db):
            print("Treatment catalog: already present.")
        else:
            print("Treatment catalog: 21 items created.")
        db.commit()
        print(f"Owner created: {user.username} (dentiste +owner)")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
        dispose_engine()

    # ------- Security audit printout (fails nothing, displays everything) ----
    settings = get_settings()

    def _db_and_backups_ok() -> bool:
        from sqlalchemy import text as _text

        try:
            with get_engine().connect() as conn:
                conn.execute(_text("SELECT 1"))
            Path(settings.backups_dir).mkdir(parents=True, exist_ok=True)
            probe = Path(settings.backups_dir) / ".write-probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    checks = [
        ("Frontend build present (SPA served by FastAPI)", FRONTEND_DIST.is_dir()),
        ("Database reachable + backups folder writable", _db_and_backups_ok()),
        ("Off-site backup configured (CLINIC_BACKUP_OFFSITE_DIR)", bool(settings.backup_offsite_dir.strip())),
        ("Cookie security OK for LAN (plain HTTP, never expose to the internet)… ", not settings.cookie_secure),
        ("No extra CORS origins (production serves same origin)", settings.cors_extra_origins.strip() == ""),
    ]
    print("\nProduction audit:")
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'TODO'}] {label}")
    print(
        "\nNext steps:\n"
        "  - create staff accounts: cli.py create-user --role reception ...\n"
        "  - monthly drill task: see DEPLOY.md 'Automated monthly drill'\n"
        "  - finish section 7 checklist of DEPLOY.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
