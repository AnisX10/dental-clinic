"""Tests for DSP & CNAS register, Devis, Sterilization modules."""
import pytest


def _login(client):
    r = client.post("/api/auth/login", json={"username": "owner", "password": "password-123"})
    assert r.status_code == 200, r.text


@pytest.fixture(autouse=True)
def _auth(client, users):
    """Every test in this module runs logged-in as owner."""
    _login(client)
    yield


# --------------------------------------------------------------------------- #
# DSP & CNAS
# --------------------------------------------------------------------------- #

def _patient(client) -> int:
    r = client.post(
        "/api/patients",
        json={"nom": "Benali", "prenom": "Karim", "telephone": "0550 99 88 77"},
    )
    assert r.status_code == 201, r.text
    return r.json()["patient"]["id"]


def test_dsp_create_and_get(client):
    pid = _patient(client)
    r = client.post("/api/dsp", json={
        "patient_id": pid, "caisse": "CNAS", "insured_nin": "1234567890123",
        "first_act_date": "2026-10-01", "beneficiary_relation": "assure",
    })
    assert r.status_code == 201, r.text
    dsp_id = r.json()["registry"]["id"]

    r = client.get(f"/api/dsp/{dsp_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["registry"]["caisse"] == "CNAS"
    assert body["days_to_deadline"] > 0
    assert body["deadline_days"] == 90
    # clinic template data is included for the printable AS 2
    assert "clinic" in body and "clinic_name" in body["clinic"]


def test_dsp_invalid_caisse(client):
    pid = _patient(client)
    r = client.post("/api/dsp", json={
        "patient_id": pid, "caisse": "CNSS", "first_act_date": "2026-10-01",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_caisse"


def test_dsp_list_includes_deadline(client):
    pid = _patient(client)
    client.post("/api/dsp", json={
        "patient_id": pid, "caisse": "CASNOS", "first_act_date": "2026-06-01",
    })
    r = client.get("/api/dsp", params={"caisse": "CASNOS"})
    assert r.status_code == 200
    rows = r.json()["registries"]
    assert len(rows) == 1
    row = rows[0]
    assert row["patient"]["id"] == pid
    assert row["days_to_deadline"] < 0  # 2026-06-01 + 90d is long past
    assert row["deadline_date"].startswith("2026-08-")


def test_dsp_act_lifecycle(client):
    pid = _patient(client)
    dsp_id = client.post("/api/dsp", json={
        "patient_id": pid, "caisse": "CNAS", "first_act_date": "2026-10-01",
    }).json()["registry"]["id"]

    # add act with FDI tooth
    r = client.post(f"/api/dsp/{dsp_id}/acts", json={
        "act_date": "2026-10-05", "tooth": 26, "act_label": "Composite",
        "act_code": "SC", "coefficient": 2, "fee": 3500,
    })
    assert r.status_code == 201, r.text
    act = r.json()["act"]

    # act before first_act_date rejected
    r = client.post(f"/api/dsp/{dsp_id}/acts", json={
        "act_date": "2026-09-30", "tooth": 26, "act_label": "Composite",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "dsp_act_before_first"

    # invalid tooth rejected
    r = client.post(f"/api/dsp/{dsp_id}/acts", json={
        "act_date": "2026-10-06", "tooth": 99, "act_label": "Extraction",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_tooth"

    # empty label rejected (pydantic field missing entirely -> 422;
    # blank string -> 400 dsp_act_label_required)
    r = client.post(f"/api/dsp/{dsp_id}/acts", json={"act_date": "2026-10-07", "act_label": "  "})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "dsp_act_label_required"

    # edit
    r = client.put(f"/api/dsp/{dsp_id}/acts/{act['id']}", json={"fee": 4000})
    assert r.status_code == 200
    assert float(r.json()["act"]["fee"]) == 4000.00

    # delete
    r = client.delete(f"/api/dsp/{dsp_id}/acts/{act['id']}")
    assert r.status_code == 204
    r = client.get(f"/api/dsp/{dsp_id}")
    assert r.json()["acts"] == []


def test_dsp_q_search(client):
    pid = _patient(client)
    client.post("/api/dsp", json={
        "patient_id": pid, "caisse": "CNAS", "first_act_date": "2026-10-01",
        "insured_nin": "998877665544",
    })
    r = client.get("/api/dsp", params={"q": "998877"})
    assert r.status_code == 200
    assert len(r.json()["registries"]) == 1


# --------------------------------------------------------------------------- #
# Devis
# --------------------------------------------------------------------------- #

def _catalog_item(client) -> int:
    r = client.post("/api/clinical/catalog", json={
        "name": "Composite QA", "category": "Soins", "default_price": 3500,
    })
    assert r.status_code == 201, r.text
    return r.json()["item"]["id"]


def test_devis_create_total_and_flow(client):
    pid = _patient(client)
    cid = _catalog_item(client)
    r = client.post("/api/devis", json={
        "patient_id": pid,
        "items": [
            {"catalog_item_id": cid, "label": "Couronne céramique", "tooth": 26,
             "quantity": 1, "unit_price": 18000},
            {"label": "Détartrage", "quantity": 2, "unit_price": 3000},
        ],
        "issue_date": "2026-10-12",
        "notes": "Plan complet",
    })
    assert r.status_code == 201, r.text
    devis = r.json()["devis"]
    assert devis["status"] == "draft"
    assert devis["total"] == "24000.00"
    assert len(devis["items"]) == 2

    did = devis["id"]
    # draft -> sent
    r = client.post(f"/api/devis/{did}/status", json={"status": "sent"})
    assert r.status_code == 200
    # sent -> accepted
    r = client.post(f"/api/devis/{did}/status", json={"status": "accepted"})
    assert r.status_code == 200
    # accepted is terminal
    r = client.post(f"/api/devis/{did}/status", json={"status": "draft"})
    assert r.status_code == 400
    # accepted devis no longer editable
    r = client.put(f"/api/devis/{did}", json={
        "items": [{"label": "X", "quantity": 1, "unit_price": 1}],
        "notes": "",
        "due_date": None,
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "devis_not_editable"


def test_devis_invalid_transition(client):
    pid = _patient(client)
    cid = _catalog_item(client)
    did = client.post("/api/devis", json={
        "patient_id": pid,
        "items": [{"catalog_item_id": cid, "label": "Composite", "quantity": 1, "unit_price": 3500}],
        "issue_date": "2026-10-12",
    }).json()["devis"]["id"]
    # draft -> rejected is not allowed
    r = client.post(f"/api/devis/{did}/status", json={"status": "rejected"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_status"


def test_devis_empty_items_rejected(client):
    pid = _patient(client)
    r = client.post("/api/devis", json={
        "patient_id": pid, "items": [], "issue_date": "2026-10-12",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "devis_empty"


def test_devis_list_by_patient(client):
    pid = _patient(client)
    cid = _catalog_item(client)
    client.post("/api/devis", json={
        "patient_id": pid,
        "items": [{"catalog_item_id": cid, "label": "Composite", "quantity": 1, "unit_price": 3500}],
        "issue_date": "2026-10-12",
    })
    r = client.get("/api/devis", params={"patient_id": pid})
    assert r.status_code == 200
    rows = r.json()["devis"]
    assert len(rows) == 1
    assert rows[0]["patient_id"] == pid


def test_devis_edit_draft_only(client):
    pid = _patient(client)
    cid = _catalog_item(client)
    did = client.post("/api/devis", json={
        "patient_id": pid,
        "items": [{"catalog_item_id": cid, "label": "Composite", "quantity": 1, "unit_price": 3500}],
        "issue_date": "2026-10-12",
    }).json()["devis"]["id"]
    r = client.put(f"/api/devis/{did}", json={
        "items": [{"catalog_item_id": cid, "label": "Composite 2", "quantity": 2, "unit_price": 3500}],
        "notes": "revu",
        "due_date": None,
    })
    assert r.status_code == 200
    assert r.json()["devis"]["total"] == "7000.00"


# --------------------------------------------------------------------------- #
# Sterilization
# --------------------------------------------------------------------------- #

def test_sterilization_cycle_lifecycle(client):
    r = client.post("/api/sterilization/cycles", json={
        "items": [
            {"item_name": "Sondes", "quantity": 5},
            {"item_name": "Miroirs", "quantity": 3},
        ],
        "autoclave_name": "Autoclave A", "program": "B 134°C",
    })
    assert r.status_code == 201, r.text
    cycle = r.json()["cycle"]
    assert cycle["status"] == "in_progress"
    assert cycle["cycle_no"].startswith("S-")

    cid = cycle["id"]
    # finish as done
    r = client.post(f"/api/sterilization/cycles/{cid}/finish", json={"result": "done"})
    assert r.status_code == 200
    assert r.json()["cycle"]["status"] == "done"

    # second: failed instrument blocks 'done'
    r = client.post("/api/sterilization/cycles", json={
        "items": [{"item_name": "Luxateurs", "quantity": 2, "instrument_status": "failed"}],
    })
    did = r.json()["cycle"]["id"]
    r = client.post(f"/api/sterilization/cycles/{did}/finish", json={"result": "done"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "sterilization_failed_items"
    r = client.post(f"/api/sterilization/cycles/{did}/finish", json={"result": "failed"})
    assert r.status_code == 200

    # already-finished cycle cannot be finished again
    r = client.post(f"/api/sterilization/cycles/{cid}/finish", json={"result": "done"})
    assert r.status_code == 400


def test_sterilization_blank_item_rejected(client):
    # Blank item name must be rejected with a 400 (not accepted as 201).
    r = client.post("/api/sterilization/cycles", json={"items": [{"item_name": "  "}]})
    assert r.status_code == 400


def test_sterilization_cycle_numbers_sequential(client):
    a = client.post("/api/sterilization/cycles", json={
        "items": [{"item_name": "Fouloirs", "quantity": 1}]}).json()["cycle"]
    b = client.post("/api/sterilization/cycles", json={
        "items": [{"item_name": "Curettes", "quantity": 1}]}).json()["cycle"]
    # same day => sequential numbers
    assert a["cycle_no"].rsplit("-", 1)[-1] == "001"
    assert b["cycle_no"].rsplit("-", 1)[-1] == "002"


def test_sterilization_list(client):
    client.post("/api/sterilization/cycles", json={
        "items": [{"item_name": "Pinces", "quantity": 4}]})
    r = client.get("/api/sterilization/cycles")
    assert r.status_code == 200
    assert len(r.json()["cycles"]) == 1


# --------------------------------------------------------------------------- #
# Settings: DSP defaults
# --------------------------------------------------------------------------- #

def test_settings_dsp_defaults_roundtrip(owner_client):
    r = owner_client.put("/api/settings", json={
        "dsp_default_caisse": "CASNOS",
        "dsp_default_code": "SC1",
        "dsp_default_coefficient": 2,
        "dsp_default_fee": 3500,
    })
    assert r.status_code == 200, r.text
    s = r.json()["settings"]
    assert s["dsp_default_caisse"] == "CASNOS"

    r = owner_client.get("/api/settings")
    s = r.json()["settings"]
    assert s["dsp_default_code"] == "SC1"
    assert s["dsp_default_fee"] == "3500.00"


def test_settings_dsp_default_caisse_invalid(owner_client):
    r = owner_client.put("/api/settings", json={"dsp_default_caisse": "XYZ"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_caisse"


def test_settings_dsp_reception_forbidden(reception_client):
    r = reception_client.put("/api/settings", json={"dsp_default_caisse": "CNAS"})
    assert r.status_code == 403
