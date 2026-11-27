"""License subsystem: paste-in key verification, lockout, activate endpoint.

The conftest autouse `_license_unlocked` stub is swapped out here for the REAL
machinery: a runtime-generated Ed25519 keypair verifies the minted keys and
legacy .lic files. The key format is `HKN1.<b64url payload>.<b64url sig>`.
"""
import base64
import datetime
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.licensing import service


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture()
def real_license(monkeypatch, tmp_path):
    """Swap the conftest stub for a real manager + runtime keys."""
    key = Ed25519PrivateKey.generate()
    pub_pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    pub_path = tmp_path / "public_key.pem"
    pub_path.write_bytes(pub_pem)

    monkeypatch.setattr(service, "_PUBLIC_KEY_PATH", pub_path)
    monkeypatch.setenv("CLINIC_LICENSE_FILE", str(tmp_path / "license.lic"))
    monkeypatch.setattr(
        service,
        "_manager",
        service.LicenseManager(service.license_key_file(), service.license_file(), service.installation_getter),
    )
    monkeypatch.setattr(service, "get_manager", service._original_get_manager or service.get_manager)
    service._public_key.cache_clear()

    def _mint_key(**override) -> str:
        payload = {"form": service.FORMAT_VERSION, "iat": datetime.date.today().isoformat()}
        payload.update(override)
        payload = {k: v for k, v in payload.items() if k == "form" or k in service.KEY_FIELDS}
        sig = base64.urlsafe_b64encode(key.sign(service._canonical(payload))).rstrip(b"=").decode("ascii")
        return f"HKN1.{_b64url(service._canonical(payload))}.{sig}"

    def _issueinstallation(**override) -> str:
        """Legacy .lic file content (older installations keep working)."""
        payload = {
            "artifact": service.PRODUCT_NAME,
            "form": service.FORMAT_VERSION,
            "clinic": "Clinique Sourire",
            "dentist": "Dr Sourire",
            "installation": "00000000000000000000000000000000",
            "issued_at": datetime.date.today().isoformat(),
        }
        payload.update(override)
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = base64.urlsafe_b64encode(key.sign(canon)).decode("ascii")
        return json.dumps({"license": payload, "signature": sig}, indent=2, ensure_ascii=False)

    yield {"mint_key": _mint_key, "issue_lic": _issueinstallation}
    service._public_key.cache_clear()


def test_verify_key_valid_and_tampered(real_license):
    key = real_license["mint_key"]()
    state = service.verify_key_text(key)
    assert state.active and state.reason == "ok"
    assert state.payload is not None
    assert state.key_id.startswith("HKN1-") and len(state.key_id) == 15

    tampered = key[:-4] + "AAAA"
    assert service.verify_key_text(tampered).reason == "invalid_signature"
    assert service.verify_key_text(key.replace("HKN1.", "HKN2.")).reason == "malformed"
    assert service.verify_key_text("HKN1.badpayload").reason == "malformed"


def test_verify_key_rejects_broken_structure(real_license):
    key = real_license["mint_key"]()
    forged_payload = _b64url(service._canonical({"form": service.FORMAT_VERSION}))
    forged = f"HKN1.{forged_payload}.{key.rsplit('.', 1)[1]}"  # forged payload with our sig
    assert service.verify_key_text(forged).reason == "invalid_signature"
    assert service.verify_key_text("HKN1.").reason == "malformed"
    assert service.verify_key_text("HKN1.badpayload").reason == "malformed"


def test_verify_key_tolerates_paste_artefacts(real_license):
    """Spaces, line-wraps and a BOM around/inside the key must not matter."""
    key = real_license["mint_key"](clinic="Clinique Émail")
    wrapped = "\ufeffHKN1." + key[len("HKN1."):]
    wrapped = wrapped.replace(".", ".\r\n  ")
    state = service.verify_key_text("  " + wrapped + "\r\n")
    assert state.active
    assert state.payload["clinic"] == "Clinique Émail"


def test_status_reports_missing_license(client, real_license):
    resp = client.get("/api/license/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is False
    assert body["reason"] == "missing"
    assert body["key_id"] is None
    assert len(body["installation_id"]) == 32


def test_lockout_blocks_mutation_api_but_open_routes(client, real_license):
    assert client.get("/api/health").status_code == 200

    # Writes are blocked...
    blocked = client.post("/api/patients", json={"nom": "X", "prenom": "Y", "telephone": "0550"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "license_locked"
    # ...but the clinic can still log in, read its records and back them up.
    login = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert login.status_code != 403
    assert client.get("/api/patients").status_code == 401  # auth, not licence
    assert client.post("/api/backup/run").status_code == 401  # reachable (needs login)


def test_locked_owner_can_read_and_back_up(client, users, real_license):
    assert client.post("/api/auth/login", json={"username": "owner", "password": "password-123"}).status_code == 200
    assert client.get("/api/patients").status_code == 200
    assert client.post("/api/backup/run").status_code == 201
    assert client.post("/api/patients", json={"nom": "X", "prenom": "Y", "telephone": "0550"}).status_code == 403


def test_activate_floating_key_unlocks(client, real_license):
    """Minted before delivery: a key without `inst` works on any installation."""
    key = real_license["mint_key"](clinic="Clinique Batch")
    resp = client.post("/api/license/activate", json={"key": key})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active"] is True
    assert body["clinic"] == "Clinique Batch"
    assert body["key_id"] == service.key_id(service._soften(key))
    assert body["issued_at"] == datetime.date.today().isoformat()

    login = client.post("/api/auth/login", json={"username": "nobody", "password": "nope"})
    assert login.status_code != 403


def test_activate_bound_key_unlocks(client, real_license):
    install_id = client.get("/api/license/status").json()["installation_id"]
    key = real_license["mint_key"](inst=install_id)
    resp = client.post("/api/license/activate", json={"key": f"  {key} \n"})
    assert resp.status_code == 200
    assert resp.json()["active"] is True


def test_activate_rejects_foreign_binding(client, real_license):
    key = real_license["mint_key"](inst="ffffffffffffffffffffffffffffffff")
    resp = client.post("/api/license/activate", json={"key": key})
    assert resp.status_code == 400
    assert resp.json()["error"]["message_key"] == "license.reason_installation_mismatch"
    assert client.get("/api/license/status").json()["active"] is False


def test_activate_precise_rejection_reasons(client, real_license):
    resp = client.post("/api/license/activate", json={"key": "totally wrong text"})
    assert resp.status_code == 400
    assert resp.json()["error"]["message_key"] == "license.reason_malformed"

    tampered = real_license["mint_key"]()[:-4] + "AAAA"
    resp = client.post("/api/license/activate", json={"key": tampered})
    assert resp.status_code == 400
    assert resp.json()["error"]["message_key"] == "license.reason_invalid_signature"


def test_activate_does_not_persist_rejected_keys(client, real_license):
    key_path = Path(os.environ["CLINIC_LICENSE_FILE"]).with_suffix(".key")
    if key_path.exists():
        key_path.unlink()
    resp = client.post("/api/license/activate", json={"key": "not-a-key"})
    assert resp.status_code == 400
    assert not key_path.exists()


def test_activation_survives_restart(client, real_license):
    key = real_license["mint_key"]()
    client.post("/api/license/activate", json={"key": key})

    from app.licensing import service as srv

    fresh = srv.LicenseManager(srv.license_key_file(), srv.license_file(), srv.installation_getter)
    state = fresh.load()
    assert state.active
    assert state.payload["iat"] == datetime.date.today().isoformat()


def test_key_activation_replaces_legacy_lic_file(client, real_license):
    legacy = Path(os.environ["CLINIC_LICENSE_FILE"])
    legacy.write_text(real_license["issue_lic"](), encoding="utf-8")

    floating = real_license["mint_key"]()
    resp = client.post("/api/license/activate", json={"key": floating})
    assert resp.status_code == 200
    assert resp.json()["active"] is True

    key_path = legacy.with_suffix(".key")
    assert key_path.exists()
    assert not legacy.exists()
    assert client.get("/api/license/status").json()["active"] is True


def test_legacy_lic_still_activates_from_disk(client, real_license):
    """No pasted key available? An already-delivered .lic file keeps working."""
    install_id = client.get("/api/license/status").json()["installation_id"]
    legacy = Path(os.environ["CLINIC_LICENSE_FILE"])
    legacy.write_text(real_license["issue_lic"](installation=install_id), encoding="utf-8")

    from app.licensing import service as srv

    fresh = srv.LicenseManager(srv.license_key_file(), srv.license_file(), srv.installation_getter)
    state = fresh.load()
    assert state.active
    assert state.payload["clinic"] == "Clinique Sourire"
    # the running process picks the file up on its next startup load
    assert srv.get_manager().load().active
    assert client.get("/api/license/status").json()["active"] is True


def test_legacy_lic_installation_mismatch(real_license, client):
    legacy = Path(os.environ["CLINIC_LICENSE_FILE"])
    legacy.write_text(
        real_license["issue_lic"](installation="ffffffffffffffffffffffffffffffff"),
        encoding="utf-8",
    )

    from app.licensing import service as srv

    fresh = srv.LicenseManager(srv.license_key_file(), srv.license_file(), srv.installation_getter)
    state = fresh.load()
    assert not state.active
    assert state.reason == "installation_mismatch"


def test_invalid_key_does_not_shadow_valid_legacy_license(real_license, client):
    legacy = Path(os.environ["CLINIC_LICENSE_FILE"])
    install_id = client.get("/api/license/status").json()["installation_id"]
    legacy.write_text(real_license["issue_lic"](installation=install_id), encoding="utf-8")
    legacy.with_suffix(".key").write_text("HKN1.not-a-valid-key\n", encoding="utf-8")

    fresh = service.LicenseManager(
        service.license_key_file(), service.license_file(), service.installation_getter
    )
    state = fresh.load()
    assert state.active
    assert state.payload["clinic"] == "Clinique Sourire"
