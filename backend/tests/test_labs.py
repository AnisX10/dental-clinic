"""Lab module tests: registry, order state machine, invoices + payments."""


def _lab(c, name="Lab Central"):
    r = c.post("/api/labs", json={"name": name, "phone": "0555 00 00 00"})
    assert r.status_code == 201, r.text
    return r.json()["lab"]


def _patient(c):
    r = c.post(
        "/api/patients", json={"nom": "Benali", "prenom": "Amine", "telephone": "0550 12 34 56"}
    )
    assert r.status_code == 201, r.text
    return r.json()["patient"]


def _order(c, patient_id, lab_id, **overrides):
    payload = {
        "patient_id": patient_id,
        "lab_id": lab_id,
        "work_type": "couronne",
        "teeth": "26",
        "shade": "A2",
        "price": "8000",
    }
    payload.update(overrides)
    r = c.post("/api/lab-orders", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["order"]


# --------------------------------------------------------------------------- #
# Labs registry
# --------------------------------------------------------------------------- #


def test_lab_crud_and_duplicate(owner_client, users):
    c = owner_client
    lab = _lab(c)
    assert lab["name"] == "Lab Central"
    assert lab["is_active"] is True

    # duplicate name refused (case-insensitive)
    r = c.post("/api/labs", json={"name": "lab central"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "duplicate_name"

    # update
    r = c.put(f"/api/labs/{lab['id']}", json={"phone": "0777 11 22 33"})
    assert r.status_code == 200
    assert r.json()["lab"]["phone"] == "0777 11 22 33"

    # deactivate filters it out of the default list
    r = c.put(f"/api/labs/{lab['id']}", json={"is_active": False})
    assert r.status_code == 200
    r = c.get("/api/labs", params={"include_inactive": False})
    assert all(row["id"] != lab["id"] for row in r.json()["labs"])
    r = c.get("/api/labs", params={"include_inactive": True})
    assert any(row["id"] == lab["id"] for row in r.json()["labs"])

    # missing name refused
    r = c.post("/api/labs", json={"name": "  "})
    assert r.status_code == 400


def test_lab_requires_auth(client):
    r = client.get("/api/labs")
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# Orders: creation validation + state machine
# --------------------------------------------------------------------------- #


def test_order_create_validation(owner_client, users):
    c = owner_client
    patient = _patient(c)
    lab = _lab(c)

    # bad work type
    r = c.post(
        "/api/lab-orders",
        json={"patient_id": patient["id"], "lab_id": lab["id"], "work_type": "implant"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_work_type"

    # bad teeth string
    r = c.post(
        "/api/lab-orders",
        json={"patient_id": patient["id"], "lab_id": lab["id"], "work_type": "couronne", "teeth": "abc"},
    )
    assert r.status_code == 400

    # unknown lab
    r = c.post(
        "/api/lab-orders",
        json={"patient_id": patient["id"], "lab_id": 9999, "work_type": "couronne"},
    )
    assert r.status_code == 404

    # negative price
    r = c.post(
        "/api/lab-orders",
        json={"patient_id": patient["id"], "lab_id": lab["id"], "work_type": "couronne", "price": "-5"},
    )
    assert r.status_code == 400


def test_order_state_machine_happy_path(owner_client, users):
    c = owner_client
    patient = _patient(c)
    lab = _lab(c)
    order = _order(c, patient["id"], lab["id"])
    assert order["status"] == "envoye"
    assert order["patient"]["code"] == "P-000001"
    assert order["lab"]["name"] == "Lab Central"

    # forward walk: envoye -> en_fabrication -> pret -> recu
    for status in ("en_fabrication", "pret", "recu"):
        r = c.post(f"/api/lab-orders/{order['id']}/status", json={"status": status})
        assert r.status_code == 200, r.text
    final = r.json()["order"]
    assert final["status"] == "recu"
    assert final["received_date"] is not None

    # no transition out of a terminal status
    r = c.post(f"/api/lab-orders/{order['id']}/status", json={"status": "envoye"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_transition"

    # edits locked once received
    r = c.put(f"/api/lab-orders/{order['id']}", json={"price": "9000"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "lab_order_locked"


def test_order_state_machine_rejections(owner_client, users):
    c = owner_client
    patient = _patient(c)
    lab = _lab(c)
    order = _order(c, patient["id"], lab["id"])

    r = c.post(f"/api/lab-orders/{order['id']}/status", json={"status": "recu"})
    assert r.status_code == 200
    # recu -> en_fabrication forbidden
    r = c.post(f"/api/lab-orders/{order['id']}/status", json={"status": "en_fabrication"})
    assert r.status_code == 400

    # unknown status value
    order2 = _order(c, patient["id"], lab["id"])
    r = c.post(f"/api/lab-orders/{order2['id']}/status", json={"status": "livre"})
    assert r.status_code == 400

    # cancel path works from envoye
    r = c.post(f"/api/lab-orders/{order2['id']}/status", json={"status": "annule"})
    assert r.status_code == 200
    assert r.json()["order"]["status"] == "annule"


def test_order_filters_and_patient_route(owner_client, users):
    c = owner_client
    patient = _patient(c)
    lab = _lab(c)
    lab2 = _lab(c, "Lab Nord")
    _order(c, patient["id"], lab["id"])
    _order(c, patient["id"], lab2["id"], work_type="bridge", teeth="36,37")

    r = c.get("/api/lab-orders", params={"status": "envoye"})
    data = r.json()
    assert len(data["orders"]) == 2
    assert data["counts"]["envoye"] == 2

    r = c.get("/api/lab-orders", params={"lab_id": lab["id"]})
    assert len(r.json()["orders"]) == 1
    assert r.json()["orders"][0]["lab"]["name"] == "Lab Central"

    r = c.get(f"/api/patients/{patient['id']}/lab-orders")
    assert len(r.json()["orders"]) == 2

    # invalid filter value
    r = c.get("/api/lab-orders", params={"status": "nope"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Invoices + payments
# --------------------------------------------------------------------------- #


def test_invoice_create_and_duplicates(owner_client, users):
    c = owner_client
    lab = _lab(c)
    r = c.post(
        "/api/lab-invoices",
        json={"lab_id": lab["id"], "number": "F-2026-001", "amount": "15000", "label": "Couronnes octobre"},
    )
    assert r.status_code == 201, r.text
    invoice = r.json()["invoice"]
    assert invoice["amount"] == "15000.00"
    assert invoice["paye"] == "0.00"
    assert invoice["reste"] == "15000.00"

    # duplicate number for same lab refused; same number for another lab OK
    r = c.post(
        "/api/lab-invoices", json={"lab_id": lab["id"], "number": "f-2026-001", "amount": "10"}
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "duplicate_number"

    lab2 = _lab(c, "Lab Sud")
    r = c.post(
        "/api/lab-invoices", json={"lab_id": lab2["id"], "number": "F-2026-001", "amount": "10"}
    )
    assert r.status_code == 201

    # zero / bad amounts refused
    r = c.post("/api/lab-invoices", json={"lab_id": lab["id"], "number": "F-2", "amount": "0"})
    assert r.status_code == 400
    r = c.post("/api/lab-invoices", json={"lab_id": lab["id"], "number": "F-3", "amount": "abc"})
    assert r.status_code == 400


def test_invoice_payment_flow(owner_client, users):
    c = owner_client
    lab = _lab(c)
    r = c.post(
        "/api/lab-invoices",
        json={"lab_id": lab["id"], "number": "F-1", "amount": "10000"},
    )
    invoice = r.json()["invoice"]

    # partial payment
    r = c.post(f"/api/lab-invoices/{invoice['id']}/payments", json={"amount": "4000", "note": "acompte"})
    assert r.status_code == 201, r.text
    assert r.json()["invoice"]["paye"] == "4000.00"
    assert r.json()["invoice"]["reste"] == "6000.00"

    # overpayment refused
    r = c.post(f"/api/lab-invoices/{invoice['id']}/payments", json={"amount": "9999"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "overpayment"
    assert r.json()["error"]["values"]["reste"] == "6000.00"

    # settle exactly
    r = c.post(f"/api/lab-invoices/{invoice['id']}/payments", json={"amount": "6000"})
    assert r.status_code == 201
    assert r.json()["invoice"]["reste"] == "0.00"

    # nothing more due
    r = c.post(f"/api/lab-invoices/{invoice['id']}/payments", json={"amount": "100"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "nothing_due"

    # detail includes payment history
    r = c.get(f"/api/lab-invoices/{invoice['id']}")
    payments = r.json()["invoice"]["payments"]
    assert len(payments) == 2
    assert {p["amount"] for p in payments} == {"4000.00", "6000.00"}


def test_invoice_list_totals(owner_client, users):
    c = owner_client
    lab = _lab(c)
    c.post("/api/lab-invoices", json={"lab_id": lab["id"], "number": "A", "amount": "5000"})
    c.post("/api/lab-invoices", json={"lab_id": lab["id"], "number": "B", "amount": "3000"})
    r = c.get("/api/lab-invoices")
    data = r.json()
    assert len(data["invoices"]) == 2
    assert data["totaux"]["total"] == 8000.0
    assert data["totaux"]["paye"] == 0.0

    # filter by lab
    lab2 = _lab(c, "Autre")
    c.post("/api/lab-invoices", json={"lab_id": lab2["id"], "number": "C", "amount": "1000"})
    r = c.get("/api/lab-invoices", params={"lab_id": lab["id"]})
    assert len(r.json()["invoices"]) == 2
