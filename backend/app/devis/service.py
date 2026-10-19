"""Devis (treatment plan quote) service. DentalPin-style status machine:
draft -> sent -> accepted | rejected | expired | cancelled."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import Devis, DevisItem, Patient

STATUSES = ("draft", "sent", "accepted", "rejected", "expired", "cancelled")
# Allowed transitions (draft can be edited; sent/accepted cannot go back).
TRANSITIONS = {
    "draft": {"sent", "cancelled"},
    "sent": {"accepted", "rejected", "cancelled"},
    "accepted": set(),
    "rejected": set(),
    "expired": set(),
    "cancelled": set(),
}


def _validate_items(db: OrmSession, items: list[dict]) -> list[dict]:
    from app.core.models import TreatmentCatalogItem

    clean: list[dict] = []
    for raw in items[:50]:
        if not isinstance(raw, dict):
            raise AppError("errors.invalid_devis_item", status_code=400, code="invalid_devis_item")
        label = str(raw.get("label", "")).strip()
        if not label:
            raise AppError("errors.invalid_devis_item", status_code=400, code="invalid_devis_item")
        qty = raw.get("quantity", 1)
        try:
            qty = max(1, int(qty))
        except (TypeError, ValueError):
            raise AppError("errors.invalid_devis_item", status_code=400, code="invalid_devis_item") from None
        try:
            from app.core.money import to_money

            price = to_money(raw.get("unit_price", 0))
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise AppError("errors.invalid_devis_item", status_code=400, code="invalid_devis_item") from None
        tooth = raw.get("tooth")
        if tooth not in (None, ""):
            try:
                tooth = int(tooth)
            except (TypeError, ValueError):
                raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth") from None
            permanent = 11 <= tooth <= 48
            deciduous = tooth in range(51, 86) and (tooth % 10) in range(1, 6)
            if not (permanent or deciduous):
                raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth")
        else:
            tooth = None
        catalog_item_id = raw.get("catalog_item_id")
        if catalog_item_id not in (None, ""):
            try:
                catalog_item_id = int(catalog_item_id)
            except (TypeError, ValueError):
                raise AppError("errors.invalid_devis_item", status_code=400, code="invalid_devis_item") from None
            item = db.get(TreatmentCatalogItem, catalog_item_id)
            if item is None:
                raise AppError("errors.catalog_item_not_found", status_code=404, code="catalog_item_not_found")
        else:
            catalog_item_id = None
        clean.append(
            {
                "catalog_item_id": catalog_item_id,
                "label": label[:160],
                "tooth": tooth,
                "quantity": qty,
                "unit_price": price,
            }
        )
    if not clean:
        raise AppError("errors.devis_empty", status_code=400, code="devis_empty")
    return clean


def create_devis(db: OrmSession, *, patient_id: int, items: list[dict], issue_date, due_date=None, notes: str = "", actor_id: int | None) -> Devis:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.is_active:
        raise AppError("errors.patient_not_found", status_code=404, code="patient_not_found")
    clean = _validate_items(db, items)
    if isinstance(issue_date, str):
        try:
            issue_date = date.fromisoformat(issue_date)
        except ValueError:
            raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
    if due_date not in (None, "") and isinstance(due_date, str):
        try:
            due_date = date.fromisoformat(due_date)
        except ValueError:
            raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
    else:
        due_date = None
    devis = Devis(
        patient_id=patient_id,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        notes=str(notes).strip()[:2000],
        created_by=actor_id,
    )
    db.add(devis)
    db.flush()
    for item in clean:
        db.add(
            DevisItem(
                devis_id=devis.id,
                catalog_item_id=item["catalog_item_id"],
                label=item["label"],
                tooth=item["tooth"],
                quantity=item["quantity"],
                unit_price=Decimal(str(item["unit_price"])),
                created_by=actor_id,
            )
        )
    db.flush()
    return devis


def get_devis_or_404(db: OrmSession, devis_id: int) -> Devis:
    row = db.get(Devis, devis_id)
    if row is None:
        raise AppError("errors.devis_not_found", status_code=404, code="devis_not_found")
    return row


def update_devis(db: OrmSession, row: Devis, *, items: list[dict], notes: str | None, due_date, actor_id: int | None) -> Devis:
    if row.status != "draft":
        raise AppError("errors.devis_not_editable", status_code=400, code="devis_not_editable")
    clean = _validate_items(db, items)
    if notes is not None:
        row.notes = str(notes).strip()[:2000]
    if due_date not in (None, ""):
        if isinstance(due_date, str):
            try:
                due_date = date.fromisoformat(due_date)
            except ValueError:
                raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
        row.due_date = due_date
    else:
        row.due_date = None
    row.items = []
    db.flush()
    for item in clean:
        row.items.append(
            DevisItem(
                catalog_item_id=item["catalog_item_id"],
                label=item["label"],
                tooth=item["tooth"],
                quantity=item["quantity"],
                unit_price=Decimal(str(item["unit_price"])),
                created_by=actor_id,
            )
        )
    row.updated_at = now_tz()
    db.flush()
    db.expire(row, ["items"])
    return row


def set_status(db: OrmSession, row: Devis, *, new_status: str) -> Devis:
    if new_status not in STATUSES:
        raise AppError("errors.invalid_status", status_code=400, code="invalid_status")
    allowed = TRANSITIONS.get(row.status, set())
    if new_status not in allowed:
        raise AppError(
            "errors.invalid_status",
            status_code=400,
            code="invalid_status",
            values={"from": row.status, "to": new_status},
        )
    row.status = new_status
    row.updated_at = now_tz()
    db.flush()
    return row


def list_devis(db: OrmSession, *, patient_id: int | None = None, status: str | None = None, limit: int = 100) -> list[Devis]:
    query = select(Devis).order_by(Devis.created_at.desc(), Devis.id.desc()).limit(limit)
    if patient_id is not None:
        query = query.where(Devis.patient_id == patient_id)
    if status in STATUSES:
        query = query.where(Devis.status == status)
    return list(db.execute(query).scalars().all())


def devis_total(row: Devis) -> str:
    total = sum((item.unit_price * item.quantity for item in row.items), Decimal("0"))
    return str(total)


def serialize_devis(row: Devis, *, include_items: bool = True) -> dict:
    data = {
        "id": row.id,
        "patient_id": row.patient_id,
        "status": row.status,
        "issue_date": row.issue_date.isoformat(),
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
    }
    if include_items:
        data["items"] = [
            {
                "id": item.id,
                "catalog_item_id": item.catalog_item_id,
                "label": item.label,
                "tooth": item.tooth,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "line_total": str(item.unit_price * item.quantity),
            }
            for item in row.items
        ]
        data["total"] = devis_total(row)
    return data
