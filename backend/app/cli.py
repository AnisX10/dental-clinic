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

    return _run(parser.parse_args())


def _run(args) -> int:
    if getattr(args, "migrate", False):
        _run_migrations()

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


if __name__ == "__main__":
    raise SystemExit(main())
