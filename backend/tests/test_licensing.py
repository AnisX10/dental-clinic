"""License subsystem: verification, lockout middleware, install endpoint.

The conftest autouse `_license_unlocked` stub is swapped out here for the REAL
machinery: a runtime-generated Ed25519 keypair verifies the signed files.
"""
import base64
import datetime
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.licensing import service


@pytest.fixture()
def real_license(monkeypatch, tmp_path):
    """Swap the conftest stub for a real file-backed manager + runtime keys."""
    key = Ed25519PrivateKey.generate()
    pub_pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    pub_path = tmp_path / "public_key.pem"
    pub_path.write_bytes(pub_pem)

    monkeypatch.setattr(service, "_PUBLIC_KEY_PATH", pub_path)
    monkeypatch.setenv("CLINIC_LICENSE_FILE", str(tmp_path / "license.lic"))
    monkeypatch.setattr(service, "_manager", service.LicenseManager(service.license_file(), service.installation_getter))
    monkeypatch.setattr(service, "get_manager", service._original_get_manager or service.get_manager)

    def _issueinstallation(**override) -> str:
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
        return json.dumps({"license": payload, "signature": sig}, indent=2)

    service._public_key.cache_clear()
    yield _issueinstallation
    service._public_key.cache_clear()


def test_verify_bytes_valid_and_tampered(real_license):
    content = real_license()

    state = service.verify_bytes(content)
    assert state.active and state.reason == "ok"
    assert state.payload is not None
    assert state.payload["clinic"] == "Clinique Sourire"

    tampered = content.replace("Sourire", "Sourire!", 1)
    assert not service.verify_bytes(tampered).active

    payload = json.loads(content)["license"]
    payload["artifact"] = "something-else"
    assert not service.verify_bytes(json.dumps({"license": payload, "signature": "AAAA"})).active


def test_status_reports_missing_license(client, real_license):
    resp = client.get("/api/license/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is False
    assert body["reason"] == "missing"
    assert len(body["installation_id"]) == 32


def test_lockout_blocks_mutation_api_but_open_routes(client, real_license):
    assert client.get("/api/health").status_code == 200

    blocked = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "license_locked"


def test_install_with_existing_installation_unlocks(client, real_license):
    install_id = client.get("/api/license/status").json()["installation_id"]
    content = real_license(installation=install_id)

    resp = client.post("/api/license/install", json={"content": content})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active"] is True
    assert body["clinic"] == "Clinique Sourire"

    login = client.post("/api/auth/login", json={"username": "nobody", "password": "nope"})
    assert login.status_code != 403


def test_install_rejects_bad_content(client, real_license):
    resp = client.post("/api/license/install", json={"content": "not-a-license"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "license_rejected"

    still = client.post("/api/auth/login", json={"username": "nobody", "password": "nope"})
    assert still.status_code == 403


def test_install_rejects_wrong_installation(client, real_license):
    content = real_license(installation="ffffffffffffffffffffffffffffffff")
    resp = client.post("/api/license/install", json={"content": content})
    assert resp.status_code == 400

    assert client.get("/api/license/status").json()["active"] is False


def test_license_survives_files_on_disk(client, real_license):
    """install() must persist the file so the next startup loads it."""
    install_id = client.get("/api/license/status").json()["installation_id"]
    client.post("/api/license/install", json={"content": real_license(installation=install_id)})

    from app.core.db import dispose_engine
    from app.licensing import service as srv

    dispose_engine()
    manager = srv.LicenseManager(srv.license_file(), srv.installation_getter)
    state = manager.load()
    assert state.active
