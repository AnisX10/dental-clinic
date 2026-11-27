"""Single source of truth for customer-package contents.

select_files(ROOT) returns an ordered list of (relative_posix, absolute_path)
that goes into BOTH the customer zip kit (tools/make_release.py) and the
Setup.exe payload (tools/build_native.py).
"""
import fnmatch
import hashlib
import os
import tempfile
from pathlib import Path

# ------------------------------------------------------------- runtime rules --
# Aggressive dir-name pruning is ONLY for stdlib top-level + explicit paths.
# Never prune generic names (tests/sources/...) inside third-party packages:
# pydantic_settings/sources and sqlalchemy/testing are RUNTIME-required.
RUNTIME_STDLIB_PRUNE = ["Lib/test", "Lib/idlelib", "Lib/turtledemo"]
RUNTIME_PRUNE_SITEPACKAGES = {
    "pip",
    "wheel",
    "colorama",
    "pytest",
    "pluggy",
    "_pytest",
    "iniconfig",
    "hypothesis",
    "coverage",
    "pytest-cov",
    # dev-only tooling pulled in via requirements.txt extras
    "ruff",              # 25 MB linter binary, never used at runtime
    "pygments",          # syntax highlighting (ruff/pytest companion)
    "httpx",             # TestClient only (dev); starlette/fastapi don't need it
    "httpcore",          # httpx transport layer
    "watchfiles",        # uvicorn --reload helper (dev only)
    "websockets",        # uvicorn WS protocol (app has no websocket endpoints)
}

# CLI launcher stubs installed into site-packages/bin by these same dev packages
RUNTIME_PRUNE_BIN_STUBS = {
    "ruff.exe",
    "pytest.exe",
    "py.test.exe",
    "pygmentize.exe",
    "httpx.exe",
    "watchfiles.exe",
    "websockets.exe",
    "dotenv.exe",
    "mako-render.exe",
    "fastapi.exe",
    "idna.exe",
    "cffi-gen-src.exe",
}


# PostgreSQL client tools / libraries never used by the app or its
# maintenance (pg_dump, pg_restore, pg_ctl, initdb, pg_amcheck, pg_checksums,
# psql stay). ecpg + its libs are the embedded-SQL C precompiler.
RUNTIME_PRUNE_PG_BIN = {
    "ecpg.exe",
    "libecpg.dll",
    "libecpg_compat.dll",
    "libpgtypes.dll",
    "pgbench.exe",
    "pg_test_fsync.exe",
    "pg_test_timing.exe",
    "pg_config.exe",
}


def _runtime_file_ok(rel: str) -> bool:
    rel = rel.replace(os.sep, "/")
    name = rel.rsplit("/", 1)[-1]
    if name.endswith((".pyc", ".pyo")):
        return False
    if "site-packages/" in rel:
        parent = rel.rsplit("/", 1)[0]
        # dev CLI stubs (site-packages/bin/*.exe)
        if parent.endswith("/bin") and name in RUNTIME_PRUNE_BIN_STUBS:
            return False
        # license/readme noise inside third-party packages
        if name in ("RECORD", "INSTALLER", "REQUESTED") and parent.endswith(".dist-info"):
            return False
        if fnmatch.fnmatch(name, "LICENSE*") or fnmatch.fnmatch(name, "NOTICE*"):
            return False
        if fnmatch.fnmatch(name, "README*") and rel.startswith("Lib/site-packages/"):
            # keep README only if tiny? drop: docs never needed at runtime
            return False
        if name == "PG_CREDITS" or name == "PG_FULLCOPYRIGHT":
            return False
        if parent.endswith("pgserver/pginstall/bin") and name in RUNTIME_PRUNE_PG_BIN:
            return False
    return True


def _runtime_walk_ok(rel: str, is_dir: bool) -> bool:
    rel = rel.replace(os.sep, "/")
    rel = rel.removeprefix("runtime/")
    parts = rel.split("/")
    name = parts[-1] if parts else ""
    if is_dir:
        if name == "__pycache__":
            return False
        for std in RUNTIME_STDLIB_PRUNE:
            if rel == std or rel.startswith(std + "/"):
                return False
        if "site-packages/" in rel:
            # top-level third-party package ban (also catches versioned
            # .dist-info / .data dirs, e.g. pytest-9.1.1.dist-info)
            tail = rel.split("site-packages/", 1)[1]
            head = tail.split("/", 1)[0] if "/" in tail else tail
            base = head.split("-", 1)[0]
            if base in RUNTIME_PRUNE_SITEPACKAGES or head in RUNTIME_PRUNE_SITEPACKAGES:
                return False
            # pgserver source leftovers
            if tail == "pgserver/sources" or tail == "pgserver/_source":
                return False
            # C headers for building PostgreSQL extensions (7 MB, never used)
            if tail == "pgserver/pginstall/include":
                return False
            # bundled self-tests inside third-party packages
            if tail in ("certifi/tests", "certifi/tests/"):
                return False
        return True
    else:
        return _runtime_file_ok(rel)


# ----------------------------------------------------------------- assembly ---
def select_files(root: Path, with_manifest: bool = True):
    """Return ordered [(rel_posix, absolute_path), ...] for the customer package.

    The last item is MANIFEST.txt (sha256 + path of every other item), generated
    into a temp dir, unless with_manifest=False.
    """
    root = Path(root)
    items = []

    def add(rel: str, p: Path):
        items.append((rel.replace(os.sep, "/"), p))

    def add_tree(src_dir: Path, prefix: str, filter_fn=None):
        if not src_dir.exists():
            raise SystemExit("Dossier manquant dans le paquet: " + str(src_dir))
        for base, dirs, files in os.walk(src_dir):
            base_rel = Path(base).relative_to(src_dir)
            for d in list(dirs):
                rel_dir = (base_rel / d).as_posix() if base_rel.as_posix() != "." else d
                if filter_fn and not filter_fn(prefix + "/" + rel_dir, True):
                    dirs.remove(d)
            for f in files:
                rel_file = (base_rel / f).as_posix() if base_rel.as_posix() != "." else f
                full_rel = prefix + "/" + rel_file
                if filter_fn and not filter_fn(full_rel, False):
                    continue
                if not filter_fn and "__pycache__" in rel_file:
                    continue
                add(full_rel, Path(base) / f)

    # backend
    add_tree(root / "backend" / "app", "backend/app")
    add_tree(root / "backend" / "migrations", "backend/migrations")
    for f in ("alembic.ini", "pyproject.toml", "requirements.txt"):
        p = root / "backend" / f
        if p.exists():
            add("backend/" + f, p)

    # frontend build output (Nuxt generate -> .output/public, what backend serves)
    add_tree(root / "frontend" / ".output" / "public", "frontend/.output/public")

    # scripts (launcher must already be built)
    for f in ("start.bat", "stop.bat", "install.bat", "reset_password.bat",
              "make_shortcuts.ps1", "read_password.ps1", "HKN Dentaire.exe"):
        p = root / "scripts" / f
        if p.exists():
            add("scripts/" + f, p)
        else:
            raise SystemExit("scripts/" + f + " manquant - lancez tools/build_native.py d'abord.")

    # branding
    for f in ("app.ico", "app-icon.svg", "icon-512.png", "logo-blue.svg", "logo-white.svg"):
        p = root / "branding" / f
        if p.exists():
            add("branding/" + f, p)

    # runtime (portable python + pgserver)
    add_tree(root / "runtime", "runtime", filter_fn=_runtime_walk_ok)

    # single version source (read by the backend, Setup and the uninstall entry)
    p = root / "VERSION"
    if not p.is_file():
        raise SystemExit("VERSION manquant a la racine du depot.")
    add("VERSION", p)

    # docs
    p = root / "INSTALLATION_GUIDE.md"
    if p.exists():
        add("INSTALLATION_GUIDE.md", p)
    p = root / "HKN_Dentaire_Installation_Guide.pdf"
    if p.exists():
        add("HKN_Dentaire_Installation_Guide.pdf", p)

    if with_manifest:
        add(MANIFEST_NAME, write_manifest(items))
    return items


# ----------------------------------------------------------------- manifest ---
# MANIFEST.txt is shipped at the install root. The uninstaller
# (tools/native/HKNUninstall.cs) deletes ONLY the files it lists plus the known
# application dirs, so user files that share the folder are never touched.
MANIFEST_NAME = "MANIFEST.txt"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_text(items) -> str:
    """'<sha256>  <rel_posix>' per line (format parsed by HKNUninstall.cs)."""
    lines = ["HKN Dentaire - manifeste des fichiers", "sha256  chemin", ""]
    lines += [sha256_file(p) + "  " + rel for rel, p in items if rel != MANIFEST_NAME]
    return "\n".join(lines + [""])


def write_manifest(items) -> Path:
    out = Path(tempfile.mkdtemp(prefix="hkn_manifest_")) / MANIFEST_NAME
    out.write_text(manifest_text(items), encoding="utf-8", newline="\n")
    return out
