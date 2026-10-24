"""Per-clinic offline licensing (Ed25519 signature + installation binding).

A sales-issued `.lic` file unlocks the app. Validation is fully offline: the
signature is checked against the committed public key and the payload must
carry this database's installation ID. No phone-home, no cloud.

The signing private key never ships: the seller keeps it and issues licenses
with tools/license.py.
"""
import base64
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
REQUIRED_FIELDS = ("artifact", "form", "clinic", "dentist", "installation")

_manager: "LicenseManager | None" = None


@dataclass(frozen=True)
class LicenseState:
    active: bool
    reason: str  # ok | missing | malformed | invalid_signature | installation_mismatch
    payload: dict | None = None
    installation_id: str = ""


@lru_cache
def _public_key() -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(_PUBLIC_KEY_PATH.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("public_key.pem is not an Ed25519 public key")
    return key


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_bytes(content: str) -> LicenseState:
    """Verify .lic file text. Returns an active state or a rejection reason."""
    try:
        doc = json.loads(content)
        payload = dict(doc["license"])
        signature = base64.urlsafe_b64decode(doc["signature"].encode("ascii"))
        if payload.get("artifact") != PRODUCT_NAME or payload.get("form") != FORMAT_VERSION:
            return LicenseState(active=False, reason="malformed")
        if not all(k in payload for k in REQUIRED_FIELDS):
            return LicenseState(active=False, reason="malformed")
        _public_key().verify(signature, _canonical(payload))
        return LicenseState(active=True, reason="ok", payload=payload)
    except (InvalidSignature, KeyError, ValueError, TypeError, UnicodeDecodeError):
        return LicenseState(active=False, reason="invalid_signature")


def license_file() -> Path:
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


class LicenseManager:
    """In-process license state, loaded at startup and after every install."""

    def __init__(self, file_path: Path, ensure_installation=lambda: ""):
        self._file = file_path
        self._ensure_installation = ensure_installation
        self._state = LicenseState(active=False, reason="missing")

    @property
    def state(self) -> LicenseState:
        return self._state

    def load(self) -> LicenseState:
        try:
            content = self._file.read_text(encoding="utf-8")
        except OSError:
            content = ""
        state = verify_bytes(content) if content.strip() else LicenseState(active=False, reason="missing")
        if state.active:
            payload = state.payload or {}
            install_id = self._ensure_installation()
            if payload.get("installation") in ("*", "ALL", "PERPETUAL", install_id):
                state = LicenseState(active=True, reason="ok", payload=state.payload, installation_id=install_id)
            else:
                state = LicenseState(
                    active=False, reason="installation_mismatch", payload=state.payload, installation_id=install_id
                )
        self._state = state
        return state

    def install(self, content: str) -> LicenseState:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(content, encoding="utf-8")
        return self.load()


def get_manager() -> LicenseManager:
    global _manager
    if _manager is None:
        _manager = LicenseManager(license_file(), installation_getter)
    return _manager


# Test fixtures use this to restore the real getter after stubbing (conftest).
_original_get_manager: Callable[[], LicenseManager] | None = get_manager
