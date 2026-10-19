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


def test_odontogram_conditions_and_treatments(owner_client, users):
    patient = _patient(owner_client)
    item = owner_client.post(
        "/api/clinical/catalog",
        json={"name": "Extraction", "category": "Chirurgie", "default_price": "2000"},
    ).json()["item"]
    owner_client.post(
        "/api/clinical/treatments",
        json={"patient_id": patient["id"], "catalog_item_id": item["id"], "tooth": 38},
    )
    path = f"/api/clinical/patients/{patient['id']}/odontogram"
    resp = owner_client.put(path, json={"tooth": 38, "condition": "absent"})
    assert resp.status_code == 200
    assert resp.json() == {"tooth": 38, "condition": "absent", "surface": ""}
    og = owner_client.get(path).json()
    assert {(c["tooth"], c["surface"]): c["condition"] for c in og["conditions"]} == {(38, ""): "absent"}
    assert og["treatments_by_tooth"]["38"][0]["name"] == "Extraction"
    # Invalid condition rejected
    resp = owner_client.put(path, json={"tooth": 38, "condition": "magenta"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_state"
    # Invalid tooth rejected
    resp = owner_client.put(path, json={"tooth": 57, "condition": "a_traiter"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_tooth"


def test_odontogram_surface_marks(owner_client, users):
    patient = _patient(owner_client)
    path = f"/api/clinical/patients/{patient['id']}/odontogram"

    def conds():
        og = owner_client.get(path).json()
        return {(c["tooth"], c["surface"]): c["condition"] for c in og["conditions"]}

    # Surface conditions require a valid surface
    resp = owner_client.put(path, json={"tooth": 16, "condition": "carie"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "surface_required"
    resp = owner_client.put(path, json={"tooth": 16, "condition": "carie", "surface": "haut"})
    assert resp.status_code == 400
    # Mark two surfaces; a second condition replaces the first on that surface
    assert owner_client.put(path, json={"tooth": 16, "condition": "carie", "surface": "occlusale"}).status_code == 200
    assert owner_client.put(path, json={"tooth": 16, "condition": "obturation", "surface": "occlusale"}).status_code == 200
    assert owner_client.put(path, json={"tooth": 16, "condition": "carie", "surface": "mesiale"}).status_code == 200
    assert conds() == {(16, "occlusale"): "obturation", (16, "mesiale"): "carie"}
    # Couronne coexists with surface marks (a crowned tooth may keep carie /
    # obturation records); other whole-tooth conditions replace surface marks
    assert owner_client.put(path, json={"tooth": 16, "condition": "couronne"}).status_code == 200
    assert conds() == {
        (16, ""): "couronne",
        (16, "occlusale"): "obturation",
        (16, "mesiale"): "carie",
    }
    assert owner_client.put(path, json={"tooth": 16, "condition": "bridge"}).status_code == 200
    assert conds() == {(16, ""): "bridge"}
    # A whole-tooth condition never carries a surface
    resp = owner_client.put(path, json={"tooth": 16, "condition": "couronne", "surface": "occlusale"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "surface_not_allowed"
    # 'sain' with a surface clears just that mark
    assert owner_client.put(path, json={"tooth": 16, "condition": "carie", "surface": "distale"}).status_code == 200
    assert owner_client.put(path, json={"tooth": 16, "condition": "sain", "surface": "distale"}).status_code == 200
    assert (16, "distale") not in conds()
    # 'sain' clears the tooth entirely
    assert owner_client.put(path, json={"tooth": 16, "condition": "sain"}).status_code == 200
    assert conds() == {}
    # Deciduous teeth are supported
    assert owner_client.put(path, json={"tooth": 55, "condition": "carie", "surface": "occlusale"}).status_code == 200
    assert conds() == {(55, "occlusale"): "carie"}


def test_odontogram_history(owner_client, users):
    patient = _patient(owner_client)
    path = f"/api/clinical/patients/{patient['id']}/odontogram"
    hist_path = f"/api/clinical/patients/{patient['id']}/odontogram/history"

    # Unknown patient -> 404
    r = owner_client.get("/api/clinical/patients/999999/odontogram/history")
    assert r.status_code == 404

    # Start clean, then make a sequence of changes
    owner_client.put(path, json={"tooth": 36, "condition": "sain"})
    owner_client.put(path, json={"tooth": 36, "condition": "carie", "surface": "occlusale"})
    owner_client.put(path, json={"tooth": 36, "condition": "obturation", "surface": "occlusale"})
    owner_client.put(path, json={"tooth": 24, "condition": "absent"})
    owner_client.put(path, json={"tooth": 24, "condition": "sain"})

    rows = owner_client.get(hist_path).json()["history"]
    # Newest first: the last change (sain on 24) logs as clear; the plain set
    # events are all present. The leading sain on the unmarked 36 records nothing.
    assert len([h for h in rows if h["action"] == "clear"]) == 1
    assert rows[0]["condition"] == "sain" and rows[0]["tooth"] == 24
    assert rows[1]["condition"] == "absent" and rows[1]["tooth"] == 24
    assert rows[2]["condition"] == "obturation" and rows[2]["surface"] == "occlusale"
    assert rows[3]["condition"] == "carie"
    assert all(h.get("changed_by") for h in rows)
