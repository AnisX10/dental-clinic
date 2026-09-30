"""Payment and balance tests, including concurrency."""
import threading

from tests.conftest import BACKEND_DIR  # noqa: F401


def _patient_with_charge(client, price="5000"):
    patient = client.post(
        "/api/patients", json={"nom": "Zerrouki", "prenom": "Nadir", "telephone": "0666 11 22 33"}
    ).json()["patient"]
    item = client.post(
        "/api/clinical/catalog",
        json={"name": f"Soins complet {price}", "category": "Soins", "default_price": price},
    ).json()["item"]
    client.post(
        "/api/clinical/treatments", json={"patient_id": patient["id"], "catalog_item_id": item["id"]}
    )
    return patient


def _ledger(client, patient_id):
    return client.get(f"/api/payments/patients/{patient_id}/ledger").json()


def test_payment_and_balance(owner_client, users):
    patient = _patient_with_charge(owner_client)
    resp = owner_client.post(
        "/api/payments", json={"patient_id": patient["id"], "amount": "2000"}
    )
    assert resp.status_code == 201
    ledger = _ledger(owner_client, patient["id"])
    assert ledger["total"] == "5000.00"
    assert ledger["paye"] == "2000.00"
    assert ledger["reste"] == "3000.00"
    assert len(ledger["payments"]) == 1


def test_overpayment_rejected(owner_client, users):
    patient = _patient_with_charge(owner_client, price="1000")
    resp = owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": "1500"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "overpayment"
    assert resp.json()["error"]["values"]["reste"] == "1000.00"


def test_invalid_amounts_rejected(owner_client, users):
    patient = _patient_with_charge(owner_client)
    for amount in ("0", "-5", "abc"):
        resp = owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": amount})
        assert resp.status_code == 400, amount


def test_payment_without_any_charge_rejected(owner_client, users):
    patient = owner_client.post(
        "/api/patients", json={"nom": "No", "prenom": "Charge", "telephone": "0500 00 00 00"}
    ).json()["patient"]
    resp = owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": "100"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "nothing_due"


def test_independent_payment_after_visit(owner_client, users):
    """Patient owes, returns later, pays without any new clinical record."""
    patient = _patient_with_charge(owner_client, price="4000")
    owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": "1500"})
    # Later visit: pay the rest. No treatments/notes are created in between.
    resp = owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": "2500"})
    assert resp.status_code == 201
    ledger = _ledger(owner_client, patient["id"])
    assert ledger["reste"] == "0.00"
    assert len(ledger["payments"]) == 2


def test_concurrent_payments_never_overpay(owner_client, users):
    """Ten simultaneous 1000 DA payments against a 3000 DA debt -> exactly 3 succeed."""
    patient = _patient_with_charge(owner_client, price="3000")
    results = []
    barrier = threading.Barrier(10)

    def worker():
        barrier.wait()
        resp = owner_client.post(
            "/api/payments", json={"patient_id": patient["id"], "amount": "1000"}
        )
        results.append(resp.status_code)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(201) == 3, results
    assert results.count(400) == 7, results
    ledger = _ledger(owner_client, patient["id"])
    assert ledger["paye"] == "3000.00"
    assert ledger["reste"] == "0.00"
    assert len(ledger["payments"]) == 3


def test_daily_revenue_summary(owner_client, users):
    patient = _patient_with_charge(owner_client, price="5000")
    owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": "2000"})
    owner_client.post("/api/payments", json={"patient_id": patient["id"], "amount": "500"})
    today_summary = owner_client.get("/api/agenda/today").json()["summary"]
    assert today_summary["recettes_du_jour"] == "2500.00"
    assert today_summary["nombre_paiements"] == 2
