"""Build the native exes for HKN Dentaire (offline, uses in-box csc.exe).

Outputs:
  scripts/HKN Dentaire.exe       tray launcher (also /uninstall mode)
  tools/HKN Dentaire Setup.exe   one-file installer with payload appended

Run from repo root:  python tools/build_native.py
"""
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
NATIVE = ROOT / "tools" / "native"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
MARKER = b"HKNPAYLOAD!"

RESOURCES = [
    "/r:System.dll",
    "/r:System.Core.dll",
    "/r:System.Windows.Forms.dll",
    "/r:System.Drawing.dll",
    "/r:System.Management.dll",
    "/r:System.IO.Compression.dll",
    "/r:System.IO.Compression.FileSystem.dll",
    "/warn:1",
]
ICON = ROOT / "branding" / "app.ico"


def compile_launcher(out: Path) -> None:
    sources = [
        str(NATIVE / "Common.cs"),
        str(NATIVE / "HKNLauncherApp.cs"),
        str(NATIVE / "HKNUninstall.cs"),
        str(NATIVE / "HKNPayload.cs"),
    ]
    cmd = [
        str(CSC),
        "/nologo",
        "/target:winexe",
        "/platform:anycpu",
        "/optimize+",
        f'/win32icon:{ICON}',
        "/define:HKN_TRAY",
        "/out:" + str(out),
        f"/res:{ICON},HKN.app.ico",
    ] + RESOURCES + sources
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit("launcher compile failed")


def build_payload(tmp: Path) -> Path:
    """Create the payload zip (customer kit content)."""
    from hkn_packaging import select_files  # lives next to this file
    files = select_files(ROOT)
    out = tmp / "payload.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, src in files:
            z.write(src, rel)
    return out


def compile_setup(out: Path) -> None:
    sources = [
        str(NATIVE / "Common.cs"),
        str(NATIVE / "HKNSetupUI.cs"),
        str(NATIVE / "HKNSteps.cs"),
        str(NATIVE / "HKNUninstall.cs"),
        str(NATIVE / "HKNPayload.cs"),
    ]
    cmd = [
        str(CSC),
        "/nologo",
        "/target:winexe",
        "/platform:anycpu",
        "/optimize+",
        f'/win32icon:{ICON}',
        "/define:HKN_SETUP",
        "/out:" + str(out),
        f"/res:{ICON},HKN.app.ico",
    ] + RESOURCES + sources
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit("setup compile failed")


def append_payload(setup_exe: Path, payload_zip: Path) -> None:
    zip_bytes = payload_zip.read_bytes()
    with open(setup_exe, "ab") as f:
        f.write(zip_bytes)
        f.write(MARKER)
        f.write(struct.pack("<Q", len(zip_bytes)))


def main() -> None:
    if not CSC.exists():
        raise SystemExit("csc.exe introuvable: " + str(CSC))
    tmp = Path(tempfile.mkdtemp(prefix="hkn_build_"))
    launcher_out = ROOT / "scripts" / "HKN Dentaire.exe"
    setup_out = ROOT / "tools" / "HKN Dentaire Setup.exe"
    payload_exe = tmp / "setup_base.exe"

    compile_launcher(launcher_out)
    print("launcher:", launcher_out.stat().st_size, "bytes")

    compile_setup(payload_exe)
    print("setup base:", payload_exe.stat().st_size, "bytes")

    payload = build_payload(tmp)
    print("payload:", payload.stat().st_size, "bytes")

    setup_out.write_bytes(payload_exe.read_bytes())
    append_payload(setup_out, payload)
    print("setup:", setup_out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
