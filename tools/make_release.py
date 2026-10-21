"""Build a customer-delivery zip of the clinic application.

Usage: .venv\\Scripts\\python tools\\make_release.py [--out PATH] [--name NAME]

Produces a zip that contains ONLY what a clinic needs per DEPLOY.md:
- backend source (app, migrations, tests are excluded; requirements.txt kept)
- frontend source
- tools\\cli.py and the package script itself (docs kept, licence keys excluded)
- DEPLOY.md + docs\\sales.md
Excludes: .git, e2e, tests, data runtime files, tools\\license\\ (private key
material), reference\\, node_modules, __pycache__, .env files, *.lic.

The delivered app boots LOCKED (no licence inside): per docs/sales.md the
seller issues the .lic at the clinic after init-prod.
"""

import argparse
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

INCLUDE_DIRS = ("backend", "frontend", "tools", "docs")

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    ".nuxt",
    ".output",
    "dist",
    ".playwright-mcp",
    "playwright-report",
    "test-results",
    "pgdata",
    "reference",
    "e2e",
    "tests",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "license",
}
EXCLUDE_SUFFIXES = (".lic", ".log")
EXCLUDE_FILES = {".env", "alembic.ini.bak", "cli_dev_fingerprint.json"}


def keep(path: Path) -> bool:
    rel = path.relative_to(REPO)
    first = rel.parts[0]
    if first not in INCLUDE_DIRS and rel.name not in ("DEPLOY.md", "README.md", "pyrightconfig.json"):
        return False
    if any(p in EXCLUDE_DIR_NAMES for p in rel.parts):
        if rel.parts[:2] == ("tools", "license"):
            return False
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.name == ".env" or path.name.endswith(".env"):
        return False
    return path.name not in EXCLUDE_FILES


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--name", default=None, help="zip base name (default: clinic-app-YYYYMMDD)")
    parser.add_argument("--out", default=None, help="output directory (default: repo parent)")
    args = parser.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    name = args.name or f"clinic-app-{stamp}"
    out_dir = Path(args.out) if args.out else REPO.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{name}.zip"

    if zip_path.exists():
        print(f"refusing to overwrite existing {zip_path}")
        return 2

    files = [p for p in REPO.rglob("*") if p.is_file() and keep(p)]
    if not files:
        print("nothing to package")
        return 3

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = Path("dental-clinic") / f.relative_to(REPO)
            zf.write(f, str(arcname))

    # Safety net: verify no private key material slipped in.
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    private = [n for n in names if "private" in n.lower() or n.endswith(("private.pem", ".lic"))]
    if private:
        print(f"SAFETY ABORT: private/licence files present: {private}")
        zip_path.unlink()
        return 4

    print(f"OK: {zip_path} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
