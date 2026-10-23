r"""Build a customer-delivery zip of the clinic application.

Usage: .venv\\Scripts\\python tools\\make_release.py [--out PATH] [--name NAME]

Produces a zip that contains ONLY what a clinic needs per DEPLOY.md:
- backend source (app, migrations, tests are excluded; requirements.txt kept)
- frontend source
- convenience scripts (scripts\start.bat, scripts\start_silent.vbs, scripts\stop.bat, scripts\create_desktop_shortcut.bat, scripts\start.sh)
- tools\\cli.py and the package script itself (docs kept, licence keys excluded)
- DEPLOY.md + docs\\sales.md
Excludes: .git, e2e, tests, data runtime files, tools\\license\\ (private key
material), reference\\, node_modules, __pycache__, .env files, *.lic.

The delivered app boots LOCKED (no licence inside): per docs/sales.md the
seller issues the .lic at the clinic after init-prod.
"""

import argparse
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

INCLUDE_DIRS = ("backend", "frontend", "scripts", "tools", "docs")

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
    "scratch",
    "e2e",
    "tests",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "license",
}
EXCLUDE_SUFFIXES = (".lic", ".log")
EXCLUDE_FILES = {
    ".env",
    ".gitignore",
    "alembic.ini.bak",
    "cli_dev_fingerprint.json",
    "seed_demo_tmp.py",
    "seed_qa_tmp.py",
    "e2e_bootstrap.py",
}


def keep(path: Path, include_build: bool = False) -> bool:
    rel = path.relative_to(REPO)
    if len(rel.parts) == 1:
        if rel.name not in ("DEPLOY.md", "README.md", "INSTALLATION_GUIDE.md", "HKN_Dentaire_Installation_Guide.pdf", "install.bat", "pyrightconfig.json"):
            return False
    elif rel.parts[0] not in INCLUDE_DIRS:
        return False

    if include_build and rel.parts[:3] == ("frontend", ".output", "public"):
        pass
    elif any(p in EXCLUDE_DIR_NAMES for p in rel.parts):
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
    parser.add_argument("--force", action="store_true", help="overwrite existing zip if it exists")
    parser.add_argument("--include-build", action="store_true", help="include precompiled frontend/.output/public")
    args = parser.parse_args()

    if args.include_build:
        index_file = REPO / "frontend" / ".output" / "public" / "index.html"
        if not index_file.is_file():
            print(
                f"ERROR: --include-build requested but {index_file} was not found.\n"
                "Run `npm run generate` inside frontend/ first.",
                file=sys.stderr,
            )
            return 5

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    name = args.name or f"clinic-app-{stamp}"
    out_dir = Path(args.out) if args.out else REPO.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{name}.zip"

    if zip_path.exists():
        if args.force:
            zip_path.unlink()
        else:
            print(f"refusing to overwrite existing {zip_path}")
            return 2

    files = [p for p in REPO.rglob("*") if p.is_file() and keep(p, include_build=args.include_build)]
    if not files:
        print("nothing to package")
        return 3

    required_scripts = {
        REPO / "scripts" / "start.bat",
        REPO / "scripts" / "start.sh",
        REPO / "scripts" / "start_silent.vbs",
        REPO / "scripts" / "stop.bat",
        REPO / "scripts" / "create_desktop_shortcut.bat",
        REPO / "scripts" / "install.bat",
    }
    missing_scripts = [str(s.relative_to(REPO)) for s in required_scripts if s not in files]
    if missing_scripts:
        print(f"ERROR: missing required convenience scripts: {missing_scripts}", file=sys.stderr)
        return 6

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
