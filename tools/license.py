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
import hashlib
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    print(f"  sha256       : {_sha(out)}")
    print("  [!] Send this file as-is (email attachment, USB or zipped folder).")
    print("      NEVER copy-paste its content into a chat or document: accented")
    print("      characters get re-encoded and the signature breaks.")
    return 0


def _mint_one(key, args, today: str, sid: str) -> str:
    payload = {"form": 1, "iat": today, "sid": sid}
    if args.clinic:
        payload["clinic"] = args.clinic.strip()
    if args.dentist:
        payload["dentist"] = args.dentist.strip()
    if args.installation:
        payload["inst"] = args.installation.strip()
    sig = base64.urlsafe_b64encode(key.sign(_canon(payload))).rstrip(b"=").decode("ascii")
    payload_b64 = base64.urlsafe_b64encode(_canon(payload)).rstrip(b"=").decode("ascii")
    return f"HKN1.{payload_b64}.{sig}"


def cmd_mint(args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    pem = Path(args.private).read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        print("The key file is not an Ed25519 private key.", file=sys.stderr)
        return 1

    import secrets

    from app.licensing import service

    today = dt.date.today().isoformat()
    keys = [_mint_one(key, args, today, secrets.token_hex(12)) for _ in range(args.count)]

    print(f"minted {args.count} licence key(s) for clinic-dentaire")
    print(f"  clinic : {args.clinic or '(unlabeled)'}")
    print(f"  dentist: {args.dentist or '(unlabeled)'}")
    print(f"  bound  : {args.installation or '(any installation)'}")
    print()
    lines = [k for k in keys]
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        header = [
            "HKN Dentaire - cle de licence (une cle par ligne, a coller dans l'application)",
            "Clinique: " + (args.clinic or "-"),
            "Dentiste: " + (args.dentist or "-"),
            "Liaison : " + (args.installation or "toute installation"),
            "Date    : " + today,
            "",
        ]
        out.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
        print(f"written to : {out}")
        print()
    for k in keys:
        print(f"  {service.key_id(k)}  {k}")
    print()
    print("  [!] Hand out ONE key per installation and record the HKN1-xxxx id")
    print("      alongside the clinic name. The clinic simply pastes it.")
    return 0


def cmd_verify(args) -> int:
    """Seller-side preflight: check a .lic or a pasted key like the app does."""
    from app.licensing import service

    key_text = args.file.strip()
    if key_text.upper().startswith(service.KEY_PREFIX):
        state = service.verify_key_text(key_text)
        text_note = "cle collee"
        if args.file != key_text and state.active:
            print("[i] espaces / retours a la ligne autour de la cle: tolérés")
    else:
        path = Path(args.file)
        if not path.is_file():
            print(f"FAIL: fichier introuvable: {path}")
            return 1
        raw = path.read_bytes()
        # Reproduce every realistic transfer damage: BOM re-save, ANSI re-save,
        # copy-paste transcoding. The app applies the same repair chain.
        try:
            raw.decode("utf-8")
            was_bit_exact_utf8 = True
        except UnicodeDecodeError:
            was_bit_exact_utf8 = False
        text = service._decode_file_bytes(raw)
        if raw.startswith(b"\xef\xbb\xbf"):
            text_note = "utf-8 avec BOM (re-sauvegarde Bloc-notes)"
        elif was_bit_exact_utf8:
            text_note = "utf-8 (bit-exact)"
        else:
            text_note = "cp1252 (re-sauvegarde ANSI - caracteres repares)"
        print(f"fichier  : {path} ({len(raw)} octets, sha256 {_sha(path)})")
        print(f"encodage : {text_note}")
        state = service.verify_key_text(text) if text.strip().upper().startswith(service.KEY_PREFIX) else service.verify_bytes(text)

    if not state.active:
        match state.reason:
            case "malformed":
                print("RESULTAT: REJETE - contenu illisible (JSON casse ou fichier altere).")
            case "invalid_signature":
                print("RESULTAT: REJETE - signature invalide.")
                print("  -> le contenu a ete modifie en route, ou signe avec une autre cle.")
                print("     Re-emettez (tools/license.py mint / issue) depuis CE poste.")
            case _:
                print(f"RESULTAT: REJETE - {state.reason}")
        return 1

    payload = state.payload or {}
    installation = payload.get("inst") or payload.get("installation") or "(toute installation)"
    print("signature  : VALIDE")
    print(f"  clinic   : {payload.get('clinic') or '-'}")
    print(f"  dentist  : {payload.get('dentist') or '-'}")
    print(f"  issued   : {payload.get('iat') or payload.get('issued_at') or '-'}")
    print(f"  install. : {installation}")
    if args.installation:
        from app.licensing.service import LicenseManager

        if LicenseManager._binds(payload, args.installation.strip()):
            print(f"liaison installation {args.installation.strip()}: OK")
        else:
            print(f"liaison installation: ECHEC (attendu {args.installation.strip()})")
            print("  -> la clinique doit fournir le numero affiche sur son ecran Licence.")
            return 1
    print("RESULTAT: VALIDE - ce fichier/cle activera l'installation.")
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

    p_mint = sub.add_parser("mint", help="Mint a batch of paste-in licence keys (HKN1.xxxx.yyyy)")
    p_mint.add_argument("--count", type=int, default=10, help="How many keys to generate (default 10)")
    p_mint.add_argument("--clinic", default="", help="Optional clinic name baked into each key")
    p_mint.add_argument("--dentist", default="", help="Optional dentist name baked into each key")
    p_mint.add_argument("--installation", default="", help="Optional: bind every key to one installation ID")
    p_mint.add_argument("--private", default=str(DEFAULT_PRIVATE), help="Signing key path")
    p_mint.add_argument("--out", default="", help="Also write keys to this text file (optional)")

    p_verify = sub.add_parser("verify", help="Preflight a .lic file or a pasted key like the installed app")
    p_verify.add_argument("file", help="Path to the .lic file — or the pasted key itself (starts with HKN1.)")
    p_verify.add_argument(
        "--installation", default="", help="Installation ID it must bind to (from the clinic's Licence screen)"
    )

    return _run(parser.parse_args())


def _run(args) -> int:
    if args.command == "keygen":
        return cmd_keygen(args)
    if args.command == "issue":
        out = args.out or str(Path(args.private).parent / f"{args.clinic.lower().replace(' ', '-')}.lic")
        args.out = out
        return cmd_issue(args)
    if args.command == "mint":
        return cmd_mint(args)
    if args.command == "verify":
        return cmd_verify(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
