"""Stock module tests: items, race-safe adjust path, ledger invariant, auto-deduction."""
from decimal import Decimal

from app.core.db import get_session_factory
from app.core.models import StockItem, StockMovement


def _item(c, name="Gants nitrile", **overrides):
    payload = {"name": name, "category": "consommable", "unit": "boîte", "initial_quantity": "50", "min_quantity": "10"}
    payload.update(overrides)
    r = c.post("/api/stock", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["item"]


def _catalog(c, name="Composite", price="3500"):
    r = c.post("/api/clinical/catalog", json={"name": name, "category": "Soins", "default_price": price})
    assert r.status_code == 201, r.text
    return r.json()["item"]


def _patient(c):
    r = c.post("/api/patients", json={"nom": "Haddad", "prenom": "Nour", "telephone": "0661 22 33 44"})
    assert r.status_code == 201, r.text
    return r.json()["patient"]


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #


def test_item_create_with_initial_ledger(owner_client, users):
    c = owner_client
    item = _item(c)
    assert item["stock_quantity"] == "50.00"
    assert item["is_low"] is False

    # ledger records the opening stock
    r = c.get(f"/api/stock/{item['id']}/movements")
    moves = r.json()["movements"]
    assert len(moves) == 1
    assert moves[0]["reason"] == "initial"
    assert moves[0]["delta"] == "50.00"


def test_item_duplicates_and_validation(owner_client, users):
    c = owner_client
    _item(c)
    r = c.post("/api/stock", json={"name": "gants NITRILE", "category": "consommable"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "duplicate_name"

    r = c.post("/api/stock", json={"name": "Autre chose", "category": "médicament"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_category"

    r = c.post("/api/stock", json={"name": "X", "category": "consommable", "initial_quantity": "-3"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Adjust / correct paths + ledger invariant
# --------------------------------------------------------------------------- #


def test_adjust_flow_and_negative_refusal(owner_client, users):
    c = owner_client
    item = _item(c)

    # restock +20
    r = c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "20", "reason": "restock", "note": "livraison"})
    assert r.status_code == 201, r.text
    assert r.json()["item"]["stock_quantity"] == "70.00"

    # consume -30
    r = c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "-30", "reason": "consumption"})
    assert r.status_code == 201
    assert r.json()["item"]["stock_quantity"] == "40.00"

    # more than available refused (row-locked floor check)
    r = c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "-100"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "stock_insufficient"

    # zero delta refused
    r = c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "0"})
    assert r.status_code == 400

    # bad reason refused
    r = c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "1", "reason": "correction"})
    assert r.status_code == 400  # correction only via the /correct endpoint


def test_ledger_sums_to_quantity(owner_client, users):
    c = owner_client
    item = _item(c, "Résine", initial_quantity="100")
    c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "-40", "reason": "consumption"})
    c.post(f"/api/stock/{item['id']}/adjust", json={"delta": "15", "reason": "restock"})

    # absolute correction sets quantity; delta lands in ledger
    r = c.post(f"/api/stock/{item['id']}/correct", json={"quantity": "10", "note": "inventaire"})
    assert r.status_code == 201, r.text
    assert r.json()["item"]["stock_quantity"] == "10.00"

    db = get_session_factory()()
    try:
        rows = (
            db.query(StockMovement)
            .filter(StockMovement.item_id == item["id"])
            .all()
        )
        total = sum(Decimal(str(m.delta)) for m in rows)
        item_row = db.get(StockItem, item["id"])
        assert total == Decimal(str(item_row.stock_quantity))
    finally:
        db.close()

    # correction to the same value refused
    r = c.post(f"/api/stock/{item['id']}/correct", json={"quantity": "10"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "nothing_to_correct"


def test_low_stock_filter_and_valuation(owner_client, users):
    c = owner_client
    _item(c, "Article A", initial_quantity="5", min_quantity="10")   # low
    _item(c, "Article B", initial_quantity="40", min_quantity="10", unit_cost="250")  # 10000
    _item(c, "Article C", initial_quantity="3", min_quantity="3", unit_cost="100")    # low, 300
    # Equipment/bureau items never trigger low-stock alerts (1 fauteuil is normal).
    _item(c, "Fauteuil", initial_quantity="1", min_quantity="1", category="equipement")
    _item(c, "Papier", initial_quantity="0", min_quantity="5", category="bureau")

    r = c.get("/api/stock", params={"low_stock": "true"})
    names = {i["name"] for i in r.json()["items"]}
    assert names == {"Article A", "Article C"}
    assert r.json()["low_count"] == 2

    r = c.get("/api/stock/valuation")
    assert r.json()["valeur"] == "10300.00"
    assert r.json()["nb_articles"] == 2


# --------------------------------------------------------------------------- #
# Auto-deduction via treatment consumable links
# --------------------------------------------------------------------------- #


def _link(c, catalog_id, stock_id, qty="2"):
    r = c.post("/api/stock/links", json={"catalog_item_id": catalog_id, "stock_item_id": stock_id, "quantity": qty})
    assert r.status_code == 201, r.text
    return r.json()["link"]


def test_link_management_owner_only(owner_client, reception_client, users):
    stock = _item(owner_client, "Composite seringue")
    catalog = _catalog(owner_client)
    _link(owner_client, catalog["id"], stock["id"], "1")

    # reception (non-owner) cannot manage links
    r = reception_client.post(
        "/api/stock/links",
        json={"catalog_item_id": catalog["id"], "stock_item_id": stock["id"], "quantity": "1"},
    )
    assert r.status_code == 403
    r = reception_client.delete("/api/stock/links/1")
    assert r.status_code == 403

    # duplicate link refused
    r = owner_client.post(
        "/api/stock/links",
        json={"catalog_item_id": catalog["id"], "stock_item_id": stock["id"], "quantity": "5"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "duplicate_link"

    # listing is open to all users
    r = reception_client.get("/api/stock/links")
    assert r.status_code == 200
    assert len(r.json()["links"]) == 1


def test_auto_deduction_on_treatment(owner_client, users):
    c = owner_client
    stock = _item(c, "Composite seringue", initial_quantity="20")
    catalog = _catalog(c)
    _link(c, catalog["id"], stock["id"], "3")

    patient = _patient(c)
    r = c.post("/api/clinical/treatments", json={"patient_id": patient["id"], "catalog_item_id": catalog["id"]})
    assert r.status_code == 201, r.text
    treatment = r.json()["treatment"]

    # stock dropped by 3
    r = c.get(f"/api/stock/{stock['id']}/movements")
    moves = [m for m in r.json()["movements"] if m["reason"] == "consumption"]
    assert len(moves) == 1
    assert moves[0]["delta"] == "-3.00"
    assert moves[0]["reference_type"] == "patient_treatment"
    assert moves[0]["reference_id"] == treatment["id"]

    r = c.get("/api/stock")
    item = next(i for i in r.json()["items"] if i["id"] == stock["id"])
    assert item["stock_quantity"] == "17.00"


def test_auto_deduction_idempotent_and_clamped(owner_client, users):
    c = owner_client
    stock = _item(c, "Petit stock", initial_quantity="4")
    catalog = _catalog(c)
    _link(c, catalog["id"], stock["id"], "3")

    patient = _patient(c)

    # Treatment consumes 3 of 4 (insufficient for full 3? no — fits). Then the
    # deduction function is re-invoked with the same treatment: must stay -3.
    r = c.post("/api/clinical/treatments", json={"patient_id": patient["id"], "catalog_item_id": catalog["id"]})
    treatment = r.json()["treatment"]

    db = get_session_factory()()
    try:
        from app.core.models import PatientTreatment

        treatment_row = db.get(PatientTreatment, treatment["id"])
        from app.stock.service import apply_treatment_consumption

        apply_treatment_consumption(db, treatment_row, actor_id=None)
        db.commit()
        count = (
            db.query(StockMovement)
            .filter(
                StockMovement.item_id == stock["id"],
                StockMovement.reason == "consumption",
            )
            .count()
        )
        assert count == 1  # no double deduction
    finally:
        db.close()

    # Now a treatment with less stock than needed: 1 left, need 3 -> clamp at 0
    patient2 = c.post(
        "/api/patients", json={"nom": "Autre", "prenom": "Patient", "telephone": "0777 00 00 00"}
    ).json()["patient"]
    r = c.post("/api/clinical/treatments", json={"patient_id": patient2["id"], "catalog_item_id": catalog["id"]})
    assert r.status_code == 201  # treatment recorded despite empty stock

    r = c.get(f"/api/stock/{stock['id']}/movements")
    moves = [m for m in r.json()["movements"] if m["reason"] == "consumption"]
    assert len(moves) == 2
    assert moves[0]["delta"] == "-1.00"  # clamped, with note
    assert "clamp" in moves[0]["note"]

    r = c.get("/api/stock")
    item = next(i for i in r.json()["items"] if i["id"] == stock["id"])
    assert item["stock_quantity"] == "0.00"
    assert item["is_low"] is True
