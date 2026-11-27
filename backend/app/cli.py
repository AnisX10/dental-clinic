"""CLI: create users, seed catalog, run migrations."""
import argparse
import getpass
import string
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import dispose_engine, get_session_factory  # noqa: E402
from app.core.security import hash_password  # noqa: E402
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
    p_init.add_argument(
        "--force",
        action="store_true",
        help="If an owner account with this username already exists, RESET its password and full name",
    )

    sub.add_parser(
        "check-password",
        help="Check CLINIC_INIT_PASSWORD against the production policy (exit 0 = OK, 2 = rejected)",
    )
    sub.add_parser("stop-server", help="Gracefully stop the bundled PostgreSQL server (clean shutdown)")
    p_print_id = sub.add_parser("print-installation-id", help="Print the installation ID used for licensing")
    p_print_id.add_argument("--json", action="store_true", help="Machine-readable output")

    return _run(parser.parse_args())


def _run(args) -> int:
    if args.command == "check-password":
        # Read from the environment so the password never appears on a
        # command line (visible to other processes). No database needed.
        import os

        problem = _prod_password_problem(os.environ.get("CLINIC_INIT_PASSWORD", ""))
        if problem:
            print(_password_problem_fr(problem))
            return 2
        return 0

    if args.command == "version":
        return _version()

    if args.command == "upgrade":
        return _upgrade()

    if args.command == "drill":
        return _drill(args.backup or None, keep=args.keep)

    if args.command == "init-prod":
        return _init_prod(args)

    if args.command == "stop-server":
        return _stop_server()

    if args.command == "print-installation-id":
        return _print_installation_id(as_json=args.json)

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
    """Upgrade to head, taking a pre-upgrade backup first when needed."""
    from app.core.schema import migrate_to_head

    migrate_to_head()


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

    print(f"Upgrading to v{APP_VERSION}...")

    # 1+2) Schema migrations, preceded by a verified safety dump whenever the
    # schema actually changes. A failed dump aborts the upgrade.
    from app.core.schema import SchemaError, migrate_to_head

    try:
        if not migrate_to_head():
            print("No schema change needed.")
    except SchemaError as exc:
        print(f"Upgrade aborted: {exc}")
        return 1
    finally:
        dispose_engine()
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
    """Restore a pg_dump backup without ever leaving the clinic half-wiped.

    1. Refuse while the application is running.
    2. Check the backup is a readable archive.
    3. Take a safety backup of the current data.
    4. Restore into a scratch database in ONE transaction (all or nothing).
    5. Swap databases by renaming; the previous one is kept as
       ``clinic_before_restore`` until the next restore.
    6. Put back attachment files from the backup mirror (never overwriting).
    """
    import shutil

    from sqlalchemy import create_engine, text

    from app.backup.service import _pg_dump_path, _verify_dump, run_backup
    from app.core.config import get_settings
    from app.core.db import dispose_engine, get_engine, get_session_factory

    if not backup_path.is_file():
        print(f"Error: backup file not found: {backup_path}", file=sys.stderr)
        return 1
    if _app_is_running():
        print(
            "HKN Dentaire est en cours d'execution. Fermez-le (clic droit sur l'icone -> Quitter, "
            "ou scripts\\stop.bat) puis relancez la restauration.",
            file=sys.stderr,
        )
        return 1
    try:
        _verify_dump(backup_path, _pg_dump_path())
    except Exception as exc:
        print(f"Error: this file is not a valid backup ({exc}).", file=sys.stderr)
        return 1
    if not assume_yes:
        answer = input(
            f"This will REPLACE all current data with {backup_path.name} "
            "(a safety backup is taken first). Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 1

    live = get_engine().url.database or "clinic"
    scratch, previous = f"{live}_restore", f"{live}_before_restore"
    url = get_engine().url

    print("Safety backup of the current data...")
    with get_session_factory()() as db:
        try:
            record = run_backup(db, kind="manual", reason="pre-restore")
            db.commit()
            print(f"  saved: {Path(record.file_path).name}")
        except Exception as exc:
            db.rollback()
            print(f"Restore aborted: the safety backup failed ({exc}).", file=sys.stderr)
            return 1
    dispose_engine()  # no connection of ours may stay on the live database

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            others = conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"),
                {"d": live},
            ).scalar()
            if others:
                print("Restore aborted: the database is still in use (close HKN Dentaire).", file=sys.stderr)
                return 1
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{scratch}"'))

        print(f"Restoring {backup_path.name} into a scratch database...")
        fatal = _pg_restore_fatal(scratch, backup_path, extra_args=("--single-transaction", "--exit-on-error"))
        if fatal:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'))
            print("Restore failed - your current data was NOT changed:", file=sys.stderr)
            print("\n".join(fatal[:10]), file=sys.stderr)
            return 1

        # pg_restore's version lookup reopened the app pool on the live
        # database: close it again, the rename needs zero connections.
        dispose_engine()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{previous}" WITH (FORCE)'))
            conn.execute(text(f'ALTER DATABASE "{live}" RENAME TO "{previous}"'))
            conn.execute(text(f'ALTER DATABASE "{scratch}" RENAME TO "{live}"'))
    finally:
        admin.dispose()

    # Attachment files: restore any that the restored records need.
    settings = get_settings()
    mirror = Path(settings.backups_dir) / "attachments"
    restored = 0
    if mirror.is_dir():
        for src in mirror.rglob("*"):
            if src.is_file() and not src.name.endswith(".tmp"):
                dest = Path(settings.attachments_dir) / src.relative_to(mirror)
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    restored += 1
    print(f"Restore complete from {backup_path.name} ({restored} attachment file(s) put back).")
    print(f"The previous data is kept in database '{previous}' until the next restore.")
    print("Start the application normally.")
    return 0


def _app_is_running() -> bool:
    import urllib.request

    from app.core.runtime_config import load_runtime_config

    port = load_runtime_config().port
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2):
            return True
    except urllib.error.HTTPError:
        return True  # it answered (e.g. 503): something is running there
    except Exception:
        return False


def _pg_restore_fatal(target_db: str, backup_path: Path, *, extra_args: tuple[str, ...] = ()) -> list[str]:
    """pg_restore into target_db; returns fatal stderr lines (empty = success)."""
    from app.backup.service import pg_restore_errors

    return pg_restore_errors(target_db, backup_path, extra_args=extra_args)


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


def _password_problem_fr(problem: str) -> str:
    """French wording of a _prod_password_problem() result (installer screens)."""
    if problem.startswith("at least 10"):
        return "Le mot de passe doit contenir au moins 10 caracteres."
    if problem.startswith("too common"):
        return "Ce mot de passe est trop courant, choisissez-en un autre."
    if problem.startswith("must mix"):
        return "Le mot de passe doit melanger lettres, chiffres et un symbole (ex: ! ? @ # - _)."
    return problem


def _init_prod(args) -> int:
    """One-shot production bootstrap: schema, catalog, first owner, audit.

    Credential inputs may come from (in order): --password/--username/--full-name
    flags, then CLINIC_INIT_* environment variables (used by the installer so the
    password never appears in another process's command line), then prompting.
    """
    import os

    from sqlalchemy import select

    from app.core.config import FRONTEND_DIST, get_settings
    from app.core.db import get_engine
    from app.core.models import User

    _run_migrations()

    username = args.username or os.environ.get("CLINIC_INIT_USERNAME", "")
    full_name = args.full_name or os.environ.get("CLINIC_INIT_FULLNAME", "")
    password = args.password or os.environ.get("CLINIC_INIT_PASSWORD", "")

    username = username.strip().lower()
    full_name = full_name.strip()

    if not password:
        while True:
            password = getpass.getpass("Password (>=10, letters+digits+symbol): ")
            problem = _prod_password_problem(password)
            if problem:
                print(f"Password rejected: {problem}")
                continue
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match, try again.")
                continue
            break
    else:
        problem = _prod_password_problem(password)
        if problem:
            print(f"Password rejected: {problem}", file=sys.stderr)
            return 1
    if not username:
        username = input("Owner username: ").strip().lower()
    if not full_name:
        full_name = input("Full name (e.g. Dr Benali Amine): ").strip()

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

        existing = db.execute(
            select(User).where(User.username == username, User.is_owner.is_(True))
        ).scalar_one_or_none()
        existing_owner = db.execute(
            select(User).where(User.is_owner.is_(True)).order_by(User.id)
        ).scalars().first()
        if existing is not None:
            if args.force:
                existing.password_hash = hash_password(password)
                existing.full_name = full_name or existing.full_name
                existing.is_active = True
                db.commit()
                print(
                    f"Owner '{username}' already existed: password and full name were REPLACED "
                    f"as requested (--force)."
                )
            else:
                print(
                    f"Owner '{username}' already exists. Credentials left unchanged.\n"
                    f"To reset the password of '{username}', run this command again with --force."
                )
        elif existing_owner is not None:
            if args.force:
                print(
                    f"Owner '{existing_owner.username}' already exists. "
                    "Use that exact username to reset its credentials.",
                    file=sys.stderr,
                )
                return 1
            print(
                f"Owner '{existing_owner.username}' already exists. "
                "Credentials left unchanged; no additional owner was created."
            )
        else:
            user = create_user(db, username=username, password=password, full_name=full_name,
                               role="dentiste", is_owner=True)
            print(f"Owner created: {user.username} (dentiste +owner)")
        if not seed_catalog(db):
            print("Treatment catalog: already present.")
        else:
            print("Treatment catalog: 21 items created.")
        db.commit()
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


def _pg_bin_dir() -> Path | None:
    """Directory holding the bundled PostgreSQL binaries (pg_ctl.exe, ...)."""
    try:
        from pgserver.postgres_server import POSTGRES_BIN_PATH  # pyright: ignore[reportMissingImports]

        return Path(POSTGRES_BIN_PATH)
    except ImportError:
        return None


def _stop_server() -> int:
    """Gracefully stop the bundled PostgreSQL (data/pgdata) via pg_ctl.

    `fast` lets all clients finish, checkpoints, THEN exits — the safe way to
    close a medical database. Escalates only if a fast stop is refused.
    """
    import os

    from app.core.config import get_settings

    settings = get_settings()
    pgdata = Path(settings.data_dir) / "pgdata"
    if not (pgdata / "PG_VERSION").is_file():
        print(f"No bundled database found at {pgdata}. Nothing to stop.")
        return 0

    bin_dir = _pg_bin_dir()
    pg_ctl = (bin_dir / "pg_ctl.exe") if bin_dir else Path("pg_ctl.exe")
    env = dict(os.environ)
    if bin_dir:
        env["PATH"] = f"{bin_dir};{env.get('PATH', '')}"
    env["PGDATA"] = str(pgdata)
    for mode in ("fast", "immediate"):
        print(f"Stopping PostgreSQL ({mode})...")
        proc = subprocess.run(
            [str(pg_ctl), "-D", str(pgdata), "-m", mode, "stop"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if proc.returncode == 0:
            print("PostgreSQL stopped cleanly. Your data is safe.")
            return 0
        if "does not appear" in out or "no server" in out.lower() or "no such process" in out.lower():
            (pgdata / "postmaster.pid").unlink(missing_ok=True)
            print("PostgreSQL was not running (stale postmaster.pid cleaned up).")
            return 0
        print(out)
    print("Could not stop PostgreSQL with pg_ctl.", file=sys.stderr)
    return 1


def _print_installation_id(*, as_json: bool = False) -> int:
    """Print the installation ID of THIS database (for licence issuance)."""
    import json

    from app.licensing import service

    try:
        installation_id = service.installation_getter()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()
    if as_json:
        print(json.dumps({"installation": installation_id}))
    else:
        print(f"Installation ID: {installation_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
