r"""Build a customer-delivery zip of the clinic application.

Usage: runtime\python.exe tools\make_release.py [--out PATH] [--name NAME] [--include-runtime] [--include-license]

Produces a zip that contains what a clinic needs:
- backend source (app, migrations; tests excluded)
- frontend pre-built SPA (.output/public)
- isolated portable Python runtime (runtime/) with PostgreSQL 16 embedded (pgserver)
- universal perpetual license (data/clinic.lic)
- convenience scripts (start.bat, install.bat, stop.bat, desktop shortcut, silent launcher)
Excludes: .git, .venv, e2e, tests, data/pgdata, tools/license/private.pem.
"""

import argparse
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DEFAULT_INCLUDE_DIRS = ("backend", "frontend", "scripts", "tools", "docs", "branding")

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    ".nuxt",
    "dist",
    ".playwright-mcp",
    "playwright-report",
    "test-results",
    "pgdata",
    "pgdata-test",
    "test-backups",
    "test-attachments",
    "attachments",
    "backups",
    "reference",
    "scratch",
    "e2e",
    "tests",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "license",
}
EXCLUDE_SUFFIXES = (".log", ".tmp", ".bak", ".db", ".sqlite")
EXCLUDE_FILES = {
    ".env",
    ".gitignore",
    "alembic.ini.bak",
    "cli_dev_fingerprint.json",
    "seed_demo_tmp.py",
    "seed_qa_tmp.py",
    "e2e_bootstrap.py",
    "private.pem",
}


def keep(path: Path, include_build: bool = True, include_runtime: bool = True, include_license: bool = True) -> bool:
    rel = path.relative_to(REPO)
    parts = rel.parts

    # Root level files
    if len(parts) == 1:
        allowed_root = (
            "DEPLOY.md",
            "README.md",
            "INSTALLATION_GUIDE.md",
            "HKN_Dentaire_Installation_Guide.pdf",
            "install.bat",
            "start.bat",
            "stop.bat",
            "pyrightconfig.json",
        )
        return rel.name in allowed_root

    top_dir = parts[0]
    include_dirs = list(DEFAULT_INCLUDE_DIRS)
    if include_runtime:
        include_dirs.append("runtime")
    if include_license:
        include_dirs.append("data")

    if top_dir not in include_dirs:
        return False

    # Handling runtime
    if top_dir == "runtime":
        if any(p in ("__pycache__", ".pytest_cache", ".ruff_cache") for p in parts):
            return False
        return path.suffix.lower() not in EXCLUDE_SUFFIXES

    # Handling data
    if top_dir == "data":
        if not include_license:
            return False
        return rel.name in ("clinic.lic", "license.lic")

    # Handling frontend build
    if include_build and parts[:3] == ("frontend", ".output", "public"):
        pass
    elif any(p in EXCLUDE_DIR_NAMES for p in parts):
        return False

    if not include_license and path.suffix.lower() == ".lic":
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
    parser.add_argument("--include-build", action="store_true", default=True, help="include precompiled frontend/.output/public")
    parser.add_argument("--include-runtime", action="store_true", default=True, help="include isolated portable runtime")
    parser.add_argument("--include-license", action="store_true", default=True, help="include perpetual license file")
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

    if args.include_runtime:
        py_exe = REPO / "runtime" / "python.exe"
        if not py_exe.is_file():
            print(f"ERROR: --include-runtime requested but {py_exe} was not found.", file=sys.stderr)
            return 7

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

    files = [
        p
        for p in REPO.rglob("*")
        if p.is_file()
        and keep(
            p,
            include_build=args.include_build,
            include_runtime=args.include_runtime,
            include_license=args.include_license,
        )
    ]
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

    print(f"Packaging {len(files)} files into {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in files:
            arcname = Path("dental-clinic") / f.relative_to(REPO)
            zf.write(f, str(arcname))

    # Safety net: verify no private key material slipped in.
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    # Never ship private keys
    private = [n for n in names if "private.pem" in n.lower() or "tools/license/private" in n.lower()]
    if private:
        print(f"SAFETY ABORT: private key files present: {private}")
        zip_path.unlink()
        return 4

    # Ensure required items are in zip
    assert any("runtime/python.exe" in n for n in names), "Missing runtime/python.exe in zip"
    assert any("frontend/.output/public/index.html" in n for n in names), "Missing frontend build in zip"
    assert any("data/clinic.lic" in n for n in names), "Missing data/clinic.lic in zip"
    assert any("scripts/start.bat" in n for n in names), "Missing start.bat in zip"

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: {zip_path} ({len(files)} files, {zip_size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
