"""Patient flow tests: creation, validation, search, medical profile."""

from datetime import UTC

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


def test_duplicate_patient_returns_400(owner_client, users):
    """Same identity twice -> clean 400, never a 500 (uq_patient_identity)."""
    _create(owner_client, nom="Doublon", prenom="Idem", telephone="0550 99 88 77")
    resp = _create(owner_client, nom="Doublon", prenom="Idem", telephone="0550 99 88 77")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "patient_exists"
    # A different phone is a different identity: allowed.
    r2 = _create(owner_client, nom="Doublon", prenom="Idem", telephone="0550 99 88 78")
    assert r2.status_code == 201


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


def test_birth_date_and_age(owner_client, users):
    resp = _create(owner_client, date_naissance="1990-06-15")
    assert resp.status_code == 201
    p = resp.json()["patient"]
    assert p["date_naissance"] == "1990-06-15"
    assert p["age_years"] >= 30  # born 1990 -> at least 30 in 2026

    # Update via PUT
    r = owner_client.put(f"/api/patients/{p['id']}", json={
        "nom": "Benali", "prenom": "Amine", "telephone": "0550 12 34 56",
        "date_naissance": "1980-01-31",
    })
    assert r.status_code == 200
    assert r.json()["patient"]["date_naissance"] == "1980-01-31"
    assert r.json()["patient"]["age_years"] == 46


def test_birth_date_rejected_in_future(owner_client, users):
    resp = _create(owner_client, date_naissance="2099-01-01")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_date"
    # Bad format too
    resp = _create(owner_client, date_naissance="15/06/1990")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_date"
    # Empty string is fine (field is optional)
    resp = _create(owner_client)
    assert resp.status_code == 201
    assert resp.json()["patient"]["date_naissance"] == ""


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


def test_dormant_patients(owner_client, users):
    """Relance list: only patients whose last visit is older than `days`."""
    from datetime import datetime, timedelta

    from app.core.models import Payment

    old = _create(owner_client).json()["patient"]
    fresh = _create(owner_client, nom="Nadir", prenom="Sara", telephone="0770 55 66 77").json()["patient"]

    # Model the 'long-ago visit' with a backdated payment.
    from app.core.db import get_engine

    with get_engine().begin() as conn:
        conn.execute(
            Payment.__table__.insert().values(
                patient_id=old["id"],
                amount=2000,
                note="",
                created_at=datetime.now(UTC) - timedelta(days=240),
            )
        )

    rows = owner_client.get("/api/patients/dormant?days=180").json()["patients"]
    ids = {r["id"] for r in rows}
    assert old["id"] in ids
    assert fresh["id"] not in ids  # registered recently -> excluded
    row = next(r for r in rows if r["id"] == old["id"])
    assert row["days_since_visit"] >= 180
    assert row["last_visit"].startswith("20")
    assert row["telephone"]


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
