"""Clinical tests: notes, catalog, treatments, odontogram."""
from tests.conftest import BACKEND_DIR  # noqa: F401


def _patient(client):
    return client.post(
        "/api/patients", json={"nom": "Mesaadi", "prenom": "Yacine", "telephone": "0555 44 33 22"}
    ).json()["patient"]


def test_note_create_and_latest(owner_client, users):
    patient = _patient(owner_client)
    resp = owner_client.post(
        "/api/clinical/notes",
        json={
            "patient_id": patient["id"],
            "motif": "Douleur 36",
            "diagnostic": "Carie profonde",
            "traitement": "Traitement de canal",
            "remarques": "Contrôle dans 6 mois",
        },
    )
    assert resp.status_code == 201
    latest = owner_client.get(f"/api/clinical/patients/{patient['id']}/notes/latest").json()["note"]
    assert latest["diagnostic"] == "Carie profonde"
    # Empty history before creation for a new patient -> None handled by API
    assert latest["motif"] == "Douleur 36"


def test_note_requires_some_content(owner_client, users):
    patient = _patient(owner_client)
    resp = owner_client.post(
        "/api/clinical/notes",
        json={"patient_id": patient["id"], "motif": "", "diagnostic": "", "traitement": "", "remarques": ""},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "note_empty"


def test_note_edit_keeps_history_available(owner_client, users):
    patient = _patient(owner_client)
    note = owner_client.post(
        "/api/clinical/notes",
        json={"patient_id": patient["id"], "motif": "Initial"},
    ).json()["note"]
    resp = owner_client.put(
        f"/api/clinical/notes/{note['id']}",
        json={"motif": "Corrigé", "diagnostic": "", "traitement": "", "remarques": ""},
    )
    assert resp.status_code == 200
    history = owner_client.get(f"/api/clinical/patients/{patient['id']}/notes").json()["notes"]
    assert len(history) == 1  # edited in place, not duplicated
    assert history[0]["motif"] == "Corrigé"


def test_catalog_crud_and_categories(owner_client, users):
    resp = owner_client.post(
        "/api/clinical/catalog",
        json={"name": "Facette céramique", "category": "Prothèse", "default_price": "25000"},
    )
    assert resp.status_code == 201
    item = resp.json()["item"]
    assert item["default_price"] == "25000.00"
    # Duplicate name rejected
    resp = owner_client.post(
        "/api/clinical/catalog",
        json={"name": "facette céramique", "category": "Prothèse"},
    )
    assert resp.status_code == 400
    # Deactivate
    resp = owner_client.put(f"/api/clinical/catalog/{item['id']}", json={"is_active": False})
    assert resp.json()["item"]["is_active"] is False


def test_treatment_with_optional_tooth(owner_client, users):
    patient = _patient(owner_client)
    item = owner_client.post(
        "/api/clinical/catalog",
        json={"name": "Composite", "category": "Soins", "default_price": "3500"},
    ).json()["item"]
    # With tooth
    resp = owner_client.post(
        "/api/clinical/treatments",
        json={"patient_id": patient["id"], "catalog_item_id": item["id"], "tooth": 24},
    )
    assert resp.status_code == 201
    treatment = resp.json()["treatment"]
    assert treatment["tooth"] == 24
    assert treatment["price"] == "3500.00"  # default price from catalog
    # Without tooth
    resp = owner_client.post(
        "/api/clinical/treatments",
        json={"patient_id": patient["id"], "catalog_item_id": item["id"]},
    )
    assert resp.status_code == 201
    assert resp.json()["treatment"]["tooth"] is None


def test_invalid_tooth_rejected(owner_client, users):
    patient = _patient(owner_client)
    resp = owner_client.post(
        "/api/clinical/treatments",
        json={"patient_id": patient["id"], "name": "X", "price": "0", "tooth": 99},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_tooth"


def test_odontogram_states_and_treatments(owner_client, users):
    patient = _patient(owner_client)
    item = owner_client.post(
        "/api/clinical/catalog",
        json={"name": "Extraction", "category": "Chirurgie", "default_price": "2000"},
    ).json()["item"]
    owner_client.post(
        "/api/clinical/treatments",
        json={"patient_id": patient["id"], "catalog_item_id": item["id"], "tooth": 38},
    )
    resp = owner_client.put(
        f"/api/clinical/patients/{patient['id']}/odontogram",
        json={"tooth": 38, "state": "absent"},
    )
    assert resp.status_code == 200
    og = owner_client.get(f"/api/clinical/patients/{patient['id']}/odontogram").json()
    assert og["states"]["38"]["state"] == "absent"
    assert og["treatments_by_tooth"]["38"][0]["name"] == "Extraction"
    # Invalid state rejected
    resp = owner_client.put(
        f"/api/clinical/patients/{patient['id']}/odontogram",
        json={"tooth": 38, "state": "magenta"},
    )
    assert resp.status_code == 400
