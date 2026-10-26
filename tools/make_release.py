r"""Build customer deliverables for HKN Dentaire.

Usage:
    runtime\python.exe tools\make_release.py [--out PATH] [--name NAME] [--force]

Produces in --out (default: repo parent):
    HKN_Dentaire_<date>.zip          portable kit (extractable, same content as payload)
    tools\HKN Dentaire Setup.exe     one-file installer (rebuilt by tools\build_native.py)

Both share file selection from hkn_packaging.py. No universal license is shipped:
licensing is per-clinic via tools\license.py (.lic file imported at setup or later).
"""
import argparse
import hashlib
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkn_packaging import select_files

REPO = Path(__file__).resolve().parent.parent


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_setup() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "build_native.py")],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"tools/build_native.py failed (code {proc.returncode})")


def build_zip(out_dir: Path, name: str, force: bool) -> Path:
    items = select_files(REPO)

    required = (
        "runtime/python.exe",
        "frontend/.output/public/index.html",
        "scripts/HKN Dentaire.exe",
        "scripts/start.bat",
        "scripts/stop.bat",
        "scripts/install.bat",
        "backend/app/main.py",
        "backend/migrations/env.py",
        "branding/app.ico",
    )
    rels = {rel for rel, _ in items}
    missing = [r for r in required if r not in rels]
    if missing:
        raise SystemExit("MANQUANT dans le paquet: " + ", ".join(missing))

    banned = [rel for rel, _ in items if rel.startswith("data/") or rel.endswith("/private.pem")]
    if banned:
        raise SystemExit("SAFETY ABORT: fichiers interdits: " + ", ".join(banned))

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    if "%Y" in name:
        name = name.replace("%Y", stamp)
    zip_path = out_dir / (name + ".zip")
    if zip_path.exists():
        if not force:
            raise SystemExit("refuse d'écraser " + str(zip_path) + " (utilisez --force)")
        zip_path.unlink()

    root = "Dental care software"
    entries = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel, p in items:
            arc = root + "/" + rel
            zf.write(p, arc)
            entries.append((rel, arc, p))
        manifest_text = "\n".join(
            ["HKN Dentaire - manifeste des fichiers", "sha256  chemin", ""] +
            [_sha256(pp) + "  " + rel for rel, _arc, pp in entries] +
            [""]
        )
        zf.writestr(root + "/MANIFEST.txt", manifest_text)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    digest = _sha256(zip_path)
    print(f"ZIP: {zip_path} ({len(entries)} files, {size_mb:.1f} MB)")
    print(f"SHA256 zip: {digest}")
    return zip_path

def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--name", default="HKN_Dentaire_%Y", help="nom de base du zip (%%Y = date)")
    parser.add_argument("--out", default=None, help="dossier de sortie (défaut: parent du dépôt)")
    parser.add_argument("--force", action="store_true", help="écraser le zip existant")
    parser.add_argument("--skip-setup", action="store_true", help="ne pas reconstruire le Setup.exe")
    args = parser.parse_args()

    if not args.skip_setup:
        build_setup()

    out_dir = Path(args.out) if args.out else REPO.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = build_zip(out_dir, args.name, args.force)

    setup = REPO / "tools" / "HKN Dentaire Setup.exe"
    if setup.exists():
        print(f"SHA256 setup: {_sha256(setup)}")
    print(f"OK: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
