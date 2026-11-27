r"""Per-clinic offline licensing (Ed25519 signatures).

Two interchangeable artifacts unlock the app, both fully offline:

- **Paste-in keys** (primary workflow): the seller mints a batch of
  ``HKN1.<payload>.<signature>`` keys BEFORE delivery; the clinic pastes one
  into the licence screen or the installer. One line of ASCII, nothing to
  download or import.
- **Legacy .lic files**: signed JSON documents (tools/license.py issue);
  still read from data\ so already-activated installations keep working.

Validation checks the signature against the committed public key; a key (or
licence) that binds a specific installation ID only works on that database.
No phone-home, no cloud. The signing private key never ships: the seller
keeps it and mints/issures with tools/license.py.
"""
import base64
import binascii
import hashlib
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.config import get_settings

_PUBLIC_KEY_PATH = Path(__file__).resolve().parent / "public_key.pem"
PRODUCT_NAME = "clinic-dentaire"
FORMAT_VERSION = 1
REQUIRED_FIELDS = ("artifact", "form", "clinic", "dentist", "installation")  # legacy .lic
KEY_PREFIX = "HKN1."
KEY_FIELDS = ("form", "clinic", "dentist", "inst", "iat", "sid")  # payload schema of a key

_manager: "LicenseManager | None" = None


@dataclass(frozen=True)
class LicenseState:
    active: bool
    reason: str  # ok | missing | malformed | invalid_signature | installation_mismatch
    payload: dict | None = None
    installation_id: str = ""
    key_id: str = ""  # short fingerprint shown in the UI for support calls


@lru_cache
def _public_key() -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(_PUBLIC_KEY_PATH.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("public_key.pem is not an Ed25519 public key")
    return key


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _decode_file_bytes(raw: bytes) -> str:
    """Decode raw .lic bytes the way the app reads them from disk.

    UTF-8 first; fall back to the Windows ANSI codepage so a licence re-saved
    by Notepad as "ANSI" still carries its accented characters intact.
    """
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def verify_bytes(content: str) -> LicenseState:
    """Verify .lic file text. Returns an active state or a rejection reason.

    Tolerant to harmless transfer artefacts (UTF-8 BOM, surrounding
    whitespace) because the signature covers the canonical JSON body, not the
    file formatting. Real content changes still fail the signature.
    """
    text = content.replace("\ufeff", "").strip()
    try:
        doc = json.loads(text)
        if not isinstance(doc, dict):
            return LicenseState(active=False, reason="malformed")
        payload = dict(doc.get("license") or {})
        signature_text = doc.get("signature", "")
        if not isinstance(signature_text, str):
            return LicenseState(active=False, reason="malformed")
        if payload.get("artifact") != PRODUCT_NAME or payload.get("form") != FORMAT_VERSION:
            return LicenseState(active=False, reason="malformed")
        if not all(k in payload for k in REQUIRED_FIELDS):
            return LicenseState(active=False, reason="malformed")
        signature = base64.urlsafe_b64decode(signature_text.encode("ascii"))
        _public_key().verify(signature, _canonical(payload))
        return LicenseState(active=True, reason="ok", payload=payload)
    except json.JSONDecodeError:
        return LicenseState(active=False, reason="malformed")
    except (InvalidSignature, KeyError, ValueError, TypeError, UnicodeDecodeError):
        return LicenseState(active=False, reason="invalid_signature")


# ---------------------------------------------------------------- key format --

def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _soften(text: str) -> str:
    """Paste tolerance: kill BOM, all whitespace and line wraps a chat client
    or PDF clipboard may inject around (or inside) the key."""
    cleaned = text.replace("\ufeff", "").strip()
    return "".join(cleaned.split())


def key_id(key: str) -> str:
    """Short stable fingerprint for support: 'HKN1-a1b2c3d4e5'."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    return f"HKN1-{digest}"


def verify_key_text(text: str) -> LicenseState:
    """Verify a pasted `HKN1.<payload>.<sig>` key. Returns active/rejection state."""
    normalized = _soften(text)
    if not normalized:
        return LicenseState(active=False, reason="malformed")
    if not normalized.upper().startswith(KEY_PREFIX):
        return LicenseState(active=False, reason="malformed")
    normalized = KEY_PREFIX + normalized[len(KEY_PREFIX):]
    body = normalized[len(KEY_PREFIX):]
    parts = body.split(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return LicenseState(active=False, reason="malformed")
    try:
        payload = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        signature = _b64url_decode(parts[1])
        if not isinstance(payload, dict):
            return LicenseState(active=False, reason="malformed")
        if payload.get("form") != FORMAT_VERSION or any(field not in KEY_FIELDS for field in payload):
            return LicenseState(active=False, reason="malformed")
        _public_key().verify(signature, _canonical(payload))
        return LicenseState(active=True, reason="ok", payload=payload, key_id=key_id(normalized))
    except json.JSONDecodeError:
        return LicenseState(active=False, reason="malformed")
    except (InvalidSignature, binascii.Error, KeyError, ValueError, TypeError, UnicodeDecodeError):
        return LicenseState(active=False, reason="invalid_signature")


def license_key_file() -> Path:
    override = os.environ.get("CLINIC_LICENSE_FILE")
    if override:
        override_path = Path(override)
        return override_path.with_suffix(".key")
    return get_settings().data_dir / "clinic.key"


def license_file() -> Path:
    """Legacy .lic location (already-activated installations keep working)."""
    override = os.environ.get("CLINIC_LICENSE_FILE")
    if override:
        return Path(override)
    data_dir = get_settings().data_dir
    for candidate_name in ("clinic.lic", "license.lic"):
        cand = data_dir / candidate_name
        if cand.is_file():
            return cand
    if data_dir.is_dir():
        lics = sorted(data_dir.glob("*.lic"))
        if lics:
            return lics[0]
    return data_dir / "clinic.lic"


def installation_getter() -> str:
    """Installation ID of this database: generated once on first run."""
    from app.core.db import get_session_factory
    from app.core.services import get_settings_row

    db = get_session_factory()()
    try:
        row = get_settings_row(db)
        value = row.installation_id
        if not value:
            value = uuid.uuid4().hex
            row.installation_id = value
            db.commit()
        return value
    finally:
        db.close()


def _legacy_files() -> list[Path]:
    """All licence files that could exist in the activation folder."""
    override = os.environ.get("CLINIC_LICENSE_FILE")
    data_dir = Path(override).parent if override else get_settings().data_dir
    if not data_dir.is_dir():
        return []
    named = [data_dir / name for name in ("clinic.lic", "license.lic")]
    found = [cand for cand in named if cand.is_file()]
    found.extend(sorted(p for p in data_dir.glob("*.lic") if p not in found))
    return found


class LicenseManager:
    """In-process license state, loaded at startup and after every activation."""

    def __init__(self, key_file: Path, licence_file: Path, ensure_installation=lambda: ""):
        self._key_file = key_file
        self._licence_file = licence_file
        self._ensure_installation = ensure_installation
        self._state = LicenseState(active=False, reason="missing")

    @property
    def state(self) -> LicenseState:
        return self._state

    @staticmethod
    def _binds(payload: dict, install_id: str) -> bool:
        # A pasted key with no `inst` field floats (works on any installation:
        # the seller mints batches before delivery). A bound key or legacy
        # licence only matches its installation; wildcards pass everything.
        installation = payload.get("inst") or payload.get("installation") or "*"
        return installation in ("*", "ALL", "PERPETUAL", install_id)

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return _decode_file_bytes(path.read_bytes())
        except OSError:
            return ""

    def load(self) -> LicenseState:
        key_text = self._read_text(self._key_file)
        legacy_text = self._read_text(self._licence_file)
        key_state = verify_key_text(key_text) if key_text.strip() else None
        legacy_state = verify_bytes(legacy_text) if legacy_text.strip() else None

        # A bad key pasted during a repair must not hide a working legacy
        # licence. Prefer a valid, installation-bound activation in either file.
        candidates = []
        if key_state is not None:
            candidates.append((key_text, key_state))
        if legacy_state is not None:
            candidates.append((legacy_text, legacy_state))
        install_id = ""
        mismatch = None
        state = LicenseState(active=False, reason="missing")
        for text, candidate in candidates:
            if not candidate.active:
                if state.reason == "missing":
                    state = candidate
                continue
            if not install_id:
                install_id = self._ensure_installation()
            payload = candidate.payload or {}
            if self._binds(payload, install_id):
                state = LicenseState(
                    active=True,
                    reason="ok",
                    payload=payload,
                    installation_id=install_id,
                    key_id=candidate.key_id or key_id(text),
                )
                break
            mismatch = LicenseState(
                active=False,
                reason="installation_mismatch",
                payload=candidate.payload,
                installation_id=install_id,
            )
        else:
            if mismatch is not None:
                state = mismatch
        self._state = state
        return state

    def activate(self, pasted: str) -> LicenseState:
        """Paste-in activation: nothing is stored until the key verifies and
        binds this installation."""
        state = verify_key_text(pasted)
        if not state.active:
            return state
        payload = state.payload or {}
        install_id = self._ensure_installation()
        if not self._binds(payload, install_id):
            return LicenseState(
                active=False, reason="installation_mismatch", payload=state.payload, installation_id=install_id
            )
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        self._key_file.write_text(_soften(pasted) + "\n", encoding="utf-8")
        # One source of truth: a floating key replaces the legacy file era.
        self._remove_legacy_files()
        return self.load()

    def _remove_legacy_files(self) -> None:
        try:
            for legacy in _legacy_files():
                legacy.unlink(missing_ok=True)
        except OSError:
            pass


def get_manager() -> LicenseManager:
    global _manager
    if _manager is None:
        _manager = LicenseManager(license_key_file(), license_file(), installation_getter)
    return _manager


# Test fixtures use this to restore the real getter after stubbing (conftest).
_original_get_manager: Callable[[], LicenseManager] | None = get_manager
