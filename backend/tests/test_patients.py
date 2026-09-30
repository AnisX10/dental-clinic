"""Patient flow tests: creation, validation, search, medical profile."""

from tests.conftest import BACKEND_DIR  # noqa: F401


def _create(client, **overrides):
    payload = {"nom": "Benali", "prenom": "Amine", "telephone": "0550 12 34 56"}
    payload.update(overrides)
    return client.post("/api/patients", json=payload)


def test_create_patient_minimal(owner_client, users):
    resp = _create(owner_client)
    assert resp.status_code == 201
    patient = resp.json()["patient"]
    assert patient["nom"] == "Benali"
    assert patient["code"].startswith("P-")
    assert patient["medical"]["diabete"] is False


def test_phone_required(owner_client, users):
    resp = _create(owner_client, telephone="")
    assert resp.status_code == 400  # empty string fails the phone validator
    assert resp.json()["error"]["code"] == "invalid_phone"
    resp = _create(owner_client, telephone="abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_phone"


def test_name_required(owner_client, users):
    resp = _create(owner_client, nom="  ")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "name_required"


def test_search_by_name(owner_client, users):
    _create(owner_client)
    _create(owner_client, nom="Kaci", prenom="Lila", telephone="0661 22 33 44")
    resp = owner_client.get("/api/patients?q=kaci")
    assert resp.json()["pagination"]["total"] == 1
    assert resp.json()["patients"][0]["prenom"] == "Lila"
    # Accent-insensitive-ish partial search on prenom
    resp = owner_client.get("/api/patients?q=ami")
    assert resp.json()["pagination"]["total"] == 1


def test_search_by_phone(owner_client, users):
    _create(owner_client)
    _create(owner_client, nom="Kaci", prenom="Lila", telephone="0661 22 33 44")
    resp = owner_client.get("/api/patients?q=0661")
    assert resp.json()["pagination"]["total"] == 1


def test_patient_list_columns(owner_client, users):
    _create(owner_client)
    rows = owner_client.get("/api/patients").json()["patients"]
    assert set(rows[0].keys()) >= {"id", "nom", "prenom", "telephone"}


def test_update_patient(owner_client, users):
    patient = _create(owner_client).json()["patient"]
    resp = owner_client.put(
        f"/api/patients/{patient['id']}",
        json={
            "nom": "Benali", "prenom": "Amine", "telephone": "0550 12 34 56",
            "adresse": "12 rue Didouche Mourad, Alger",
            "wilaya": "Alger", "notes": "",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()["patient"]
    assert updated["wilaya"] == "Alger"
    assert updated["adresse"].startswith("12 rue")


def test_medical_profile_update(owner_client, users):
    patient = _create(owner_client).json()["patient"]
    resp = owner_client.put(
        f"/api/patients/{patient['id']}/medical",
        json={"diabete": True, "allergies": True, "autre": "Pénicilline"},
    )
    assert resp.status_code == 200
    medical = resp.json()["medical"]
    assert medical["diabete"] is True
    assert medical["autre"] == "Pénicilline"
    # Persisted
    refetched = owner_client.get(f"/api/patients/{patient['id']}").json()["patient"]["medical"]
    assert refetched["diabete"] is True
