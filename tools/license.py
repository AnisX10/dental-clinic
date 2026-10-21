"""Vendor-side licensing CLI (stays with the seller, not the deployed clinic).

Generate the signing keypair once, then issue one .lic file per installation:

    .venv\\Scripts\\python.exe tools\\license.py keygen
    .venv\\Scripts\\python.exe tools\\license.py issue --clinic "Clinique X" \
        --dentist "Dr Y" --installation <installation-id from the Parametres screen>

The produced file IS the license: copy it into the clinic's `data\\` folder
(or upload it from Parametres) and the application becomes fully usable.
"""
import argparse
import base64
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

DEFAULT_PRIVATE = REPO_ROOT / "tools" / "license" / "private.pem"
DEFAULT_PUBLIC = REPO_ROOT / "backend" / "app" / "licensing" / "public_key.pem"

PRODUCT = "clinic-dentaire"


def _canon(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def cmd_keygen(args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    priv_path = Path(args.out_private)
    pub_path = Path(args.out_public)
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_pem)
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.write_bytes(pub_pem)
    print(f"signing key written : {priv_path}  (KEEP PRIVATE, gitignored)")
    print(f"public key written  : {pub_path}  (committed, embedded in the app)")
    return 0


def cmd_issue(args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    pem = Path(args.private).read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        print("The key file is not an Ed25519 private key.", file=sys.stderr)
        return 1

    payload = {
        "artifact": PRODUCT,
        "form": 1,
        "clinic": args.clinic.strip(),
        "dentist": args.dentist.strip(),
        "installation": args.installation.strip(),
        "issued_at": dt.date.today().isoformat(),
    }
    sig = base64.urlsafe_b64encode(key.sign(_canon(payload))).decode("ascii")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"license": payload, "signature": sig}, indent=2), encoding="utf-8")
    print(f"license issued : {out}")
    print(f"  clinic       : {payload['clinic']}")
    print(f"  dentist      : {payload['dentist']}")
    print(f"  installation : {payload['installation']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Clinic license issuer (vendor only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("keygen", help="Create the Ed25519 signing keypair (run once)")
    p_gen.add_argument("--out-private", default=str(DEFAULT_PRIVATE))
    p_gen.add_argument("--out-public", default=str(DEFAULT_PUBLIC))

    p_issue = sub.add_parser("issue", help="Sign a perpetual per-clinic license")
    p_issue.add_argument("--clinic", required=True, help="Clinic name")
    p_issue.add_argument("--dentist", required=True, help="Dentist full name")
    p_issue.add_argument("--installation", required=True, help="Installation ID shown in Parametres")
    p_issue.add_argument("--private", default=str(DEFAULT_PRIVATE), help="Signing key path")
    p_issue.add_argument("--out", default="", help="Output .lic path (default: tools/license/<clinic>.lic)")

    return _run(parser.parse_args())


def _run(args) -> int:
    if args.command == "keygen":
        return cmd_keygen(args)
    if args.command == "issue":
        out = args.out or str(Path(args.private).parent / f"{args.clinic.lower().replace(' ', '-')}.lic")
        args.out = out
        return cmd_issue(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
